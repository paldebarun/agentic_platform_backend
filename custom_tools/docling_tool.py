import httpx
import socket
import re
import os
import sys
import hashlib
from typing import Optional, Sequence, Tuple
from urllib.parse import urlparse
from datetime import datetime

from agno.media import File
from agno.tools import tool # Import only tool


from agno_agents.config import DOCLING_SERVICE_URL
from agno_agents.log import logger
from agno_agents.postgres_client import connection_scoped_client, POSTGRES_AVAILABLE

def _default_port_for_scheme(scheme: str) -> int:
    if scheme == "https":
        return 443
    return 80


# processed_files = set()


def _is_docling_service_available(service_url: str, timeout_seconds: float = 10.0, max_retries: int = 10) -> bool:
    """TCP reachability check with retries. This check happens ONLY at module import time.
    No connection checks are performed when tools are actually used."""
    import time

    if not service_url:
        logger.warning("DOCLING_SERVICE_URL is not configured")
        return False

    parsed = urlparse(service_url)
    host = parsed.hostname or service_url.replace("http://", "").replace("https://", "").split("/")[0]
    if not host:
        logger.warning(f"Invalid hostname in DOCLING_SERVICE_URL: {service_url}")
        return False
    port = parsed.port or _default_port_for_scheme(parsed.scheme or "http")

    logger.info(f"Checking Docling service availability at {host}:{port} (URL: {service_url})")

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting connection to Docling service (attempt {attempt + 1}/{max_retries})...")
            with socket.create_connection((host, port), timeout=timeout_seconds):
                logger.info(f"✓ Connection to Docling service successful at {host}:{port}")
                return True
        except OSError as e:
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)  # Exponential backoff: 2s, 4s, 6s, 8s, etc.
                logger.info(f"Connection failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.warning(f"✗ Connection to Docling service failed after {max_retries} attempts at {host}:{port}: {e}")
                return False
    logger.warning(f"✗ Connection to Docling service failed - unable to reach {host}:{port}")
    return False

def _ensure_images_table_exists():
    """
    Ensure the docling_images table exists in PostgreSQL.
    Creates the table if it doesn't exist.
    Also adds image_description and image_hash columns if they don't exist (for vision API analysis and deduplication).
    """
    if not POSTGRES_AVAILABLE:
        logger.warning("PostgreSQL not available, cannot create images table")
        return False
    
    try:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS docling_images (
            image_id VARCHAR(255) PRIMARY KEY,
            image_hash VARCHAR(64) UNIQUE NOT NULL,
            base64_data TEXT NOT NULL,
            image_type VARCHAR(50),
            source_file VARCHAR(500),
            image_description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        with connection_scoped_client() as client:
            client.ensure_table_exists(create_table_sql)
            
            # Add image_hash column if it doesn't exist (for existing tables)
            try:
                check_hash_column_sql = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='docling_images' AND column_name='image_hash'
                """
                result = client.execute_query(check_hash_column_sql, fetch=True)
                
                if not result:
                    # Column doesn't exist, add it
                    alter_sql = """
                    ALTER TABLE docling_images 
                    ADD COLUMN image_hash VARCHAR(64)
                    """
                    client.execute_query(alter_sql, fetch=False)
                    # Add unique constraint if possible
                    try:
                        client.execute_query("CREATE UNIQUE INDEX IF NOT EXISTS idx_docling_images_hash ON docling_images(image_hash)", fetch=False)
                    except Exception:
                        pass  # Index might already exist or constraint might fail
                    client.commit()
                    logger.info("Added image_hash column to docling_images table for content-based deduplication")
                else:
                    logger.debug("Column image_hash already exists")
            except Exception as e:
                logger.warning(f"Could not add image_hash column: {e}. Table may need manual migration.")
            
            # Add image_description column if it doesn't exist (for existing tables)
            try:
                check_column_sql = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='docling_images' AND column_name='image_description'
                """
                result = client.execute_query(check_column_sql, fetch=True)
                
                if not result:
                    # Column doesn't exist, add it
                    alter_sql = """
                    ALTER TABLE docling_images 
                    ADD COLUMN image_description TEXT
                    """
                    client.execute_query(alter_sql, fetch=False)
                    client.commit()
                    logger.info("Added image_description column to docling_images table")
                else:
                    logger.debug("Column image_description already exists")
            except Exception as e:
                logger.warning(f"Could not add image_description column: {e}. Table may need manual migration.")
            
            logger.info("docling_images table ensured/created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create docling_images table: {e}")
        return False

def _extract_and_store_images(text: str, source_file: str = "unknown") -> Tuple[str, int]:
    """
    Extract image tags from text, store base64 data in PostgreSQL, and replace with image ID references.
    
    Args:
        text: Text containing image tags like [Image](data:image/png;base64,...)
        source_file: Name of the source file (for tracking)
    
    Returns:
        Tuple of (cleaned_text, images_stored_count)
    """
    if not POSTGRES_AVAILABLE:
        logger.warning("PostgreSQL not available, removing image tags without storing")
        # Fallback to simple removal
        pattern = r'\[Image\]\s*\(data:image/[^)]+\)'
        cleaned_text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        pattern2 = r'\(data:image/[^)]+\)'
        cleaned_text = re.sub(pattern2, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
        return cleaned_text.strip(), 0
    
    # Ensure table exists
    if not _ensure_images_table_exists():
        logger.warning("Could not ensure images table exists, removing image tags without storing")
        pattern = r'\[Image\]\s*\(data:image/[^)]+\)'
        cleaned_text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        pattern2 = r'\(data:image/[^)]+\)'
        cleaned_text = re.sub(pattern2, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
        return cleaned_text.strip(), 0
    
    images_stored = 0
    cleaned_text = text
    
    def replace_image(match):
        nonlocal images_stored
        try:
            # Extract full match to parse manually for better handling of very long base64 strings
            full_match = match.group(0)
            
            # Extract image type (between data:image/ and ;base64,)
            type_match = re.search(r'data:image/([^;)]+);base64,', full_match, re.IGNORECASE)
            if not type_match:
                return ""
            
            image_type = type_match.group(1).strip()
            
            # Extract base64 data (everything after base64, until the closing )
            base64_start = full_match.find('base64,')
            if base64_start == -1:
                return ""
            
            base64_start += len('base64,')
            # Find the last closing parenthesis
            base64_end = full_match.rfind(')')
            if base64_end == -1 or base64_end <= base64_start:
                return ""
            
            base64_data = full_match[base64_start:base64_end]
            
            # Generate content-based hash for deduplication
            # Same image content = same hash = same ID (prevents redundant storage)
            image_hash = hashlib.sha256(base64_data.encode('utf-8')).hexdigest()
            image_id = f"img_{image_hash[:16]}"
            
            # Store image in PostgreSQL
            with connection_scoped_client() as client:
                # Check if image_hash column exists (for backward compatibility)
                try:
                    check_column_sql = """
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='docling_images' AND column_name='image_hash'
                    """
                    has_hash_column = bool(client.execute_query(check_column_sql, fetch=True))
                except Exception:
                    has_hash_column = False
                
                # Check if image with this hash already exists (only if hash column exists)
                existing = None
                if has_hash_column:
                    try:
                        check_existing_sql = """
                            SELECT image_id, source_file 
                            FROM docling_images 
                            WHERE image_hash = %s
                            LIMIT 1
                        """
                        existing = client.execute_query(check_existing_sql, params=(image_hash,), dict_cursor=True)
                    except Exception as e:
                        logger.warning(f"Could not check for existing image by hash: {e}. Proceeding with insert.")
                        existing = None
                
                if existing:
                    # Image already exists - reuse existing ID and update source_file if needed
                    existing_image_id = existing[0]['image_id']
                    existing_source = existing[0].get('source_file', '')
                    
                    # Update source_file to include current file if not already listed
                    # (allows tracking which files contain this image)
                    if source_file and source_file != existing_source:
                        # For now, just log - we could implement a comma-separated list or separate table
                        logger.debug(f"Image {existing_image_id} already exists from {existing_source}, also found in {source_file}")
                    
                    logger.info(f"Reusing existing image {existing_image_id} (hash: {image_hash[:16]}...) from {source_file}")
                    return f"[Image:{existing_image_id}]"
                
                # New image - prepare record
                record = {
                    "image_id": image_id,
                    "base64_data": base64_data,
                    "image_type": image_type,
                    "source_file": source_file,
                    "created_at": datetime.now()
                }
                
                # Add image_hash if column exists
                if has_hash_column:
                    record["image_hash"] = image_hash
                    # Use upsert on image_hash to handle race conditions
                    # If two threads process same image simultaneously, one will insert, other will update
                    upsert_key = "image_hash"
                else:
                    # Fallback: use image_id for upsert (though this won't deduplicate)
                    upsert_key = "image_id"
                    logger.debug("image_hash column not available, using image_id for upsert (no deduplication)")
                
                if client.insert_record("docling_images", record, upsert_key=upsert_key):
                    images_stored += 1
                    logger.info(f"Stored new image {image_id} ({image_type}, {len(base64_data)} chars) from {source_file}")
                    # Replace with reference
                    return f"[Image:{image_id}]"
                else:
                    logger.warning(f"Failed to store image {image_id}, removing tag")
                    return ""
        except Exception as e:
            logger.error(f"Error storing image: {e}")
            return ""
    
    # Pattern to match [Image](data:image/type;base64,base64data) - handles multi-line with DOTALL
    # Use non-greedy matching for image type, but greedy for base64 data until closing paren
    pattern = r'\[Image\]\s*\(data:image/[^)]+\)'
    
    # Replace all image tags with references
    cleaned_text = re.sub(pattern, replace_image, cleaned_text, flags=re.IGNORECASE | re.DOTALL)
    
    # Also handle standalone image data URLs without [Image] prefix
    pattern2 = r'\(data:image/[^)]+\)'
    cleaned_text = re.sub(pattern2, replace_image, cleaned_text, flags=re.IGNORECASE | re.DOTALL)
    
    # Clean up any extra whitespace/newlines left behind
    cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
    
    return cleaned_text.strip(), images_stored

# Now, create_docling_tools will return the standalone function directly, or None
def create_docling_tools() -> Optional[callable]:
    """Create Docling tools function if the service is reachable, otherwise return None."""
    if not _is_docling_service_available(DOCLING_SERVICE_URL):
        logger.warning(
            f"Docling service not reachable at {DOCLING_SERVICE_URL}. Skipping Docling tools."
        )
        return None
    return extract_document_content # Return the decorated function



@tool(
    instructions="Use this tool ONLY ONCE when files are uploaded and document content has not been extracted yet. Do NOT call this tool if document content is already available in the conversation."
)
async def extract_document_content(files: Optional[Sequence[File]] = None) -> str:
    if not files:
        return "No files provided for extraction."

 
    processed_hashes: set[str] = set()

    extracted_texts = []
    docling_url = DOCLING_SERVICE_URL

    async with httpx.AsyncClient(timeout=3600.0) as client:
        for file in files:
        
        #     file_hash = hashlib.sha256(file.content).hexdigest()

        #     if file_hash in processed_hashes:
        #         logger.debug(
        #             f"Skipping duplicate file in same call: {file.filename or file_hash[:8]}"
        #         )
        #         continue

        #     processed_hashes.add(file_hash)

            try:
                files_payload = {
                    "file": (file.filename or "document", file.content)
                }

                logger.info(f"Sending {file.filename or 'document'} to Docling service...")
                response = await client.post(docling_url, files=files_payload)

                if response.status_code != 200:
                    extracted_texts.append(
                        f"Error: HTTP {response.status_code} - {response.text[:200]}"
                    )
                    continue

                result = response.json()
                status = result.get("status")

                if status != "success" or "prediction" not in result:
                    extracted_texts.append(
                        f"Error: Docling extraction failed (status={status})"
                    )
                    continue

                extracted_text = result["prediction"].get("text", "")
                if not extracted_text:
                    extracted_texts.append("Error: Empty text returned by Docling")
                    continue

                metadata = result["prediction"].get("metadata", {})
                source_file = metadata.get("source_file", file.filename or "document")

                cleaned_text, images_stored = _extract_and_store_images(
                    extracted_text, source_file
                )

                if images_stored:
                    logger.info(f"Stored {images_stored} image(s) from {source_file}")

                extracted_texts.append(cleaned_text)

            except Exception as e:
                logger.exception(f"Error processing {file.filename}: {e}")
                extracted_texts.append(
                    f"Error processing {file.filename or 'document'}"
                )

    return "\n\n".join(extracted_texts)


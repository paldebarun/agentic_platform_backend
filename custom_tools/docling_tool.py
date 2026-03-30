import httpx
import socket
import re
import hashlib
from typing import Optional, Sequence, Tuple
from urllib.parse import urlparse
from datetime import datetime

from agno.media import File
from agno.tools import tool

from app_config import DOCLING_SERVICE_URL
from services.db_service import connection_scoped_client, POSTGRES_AVAILABLE


def _is_docling_service_available(
    service_url: str = "http://localhost:8082",
    timeout_seconds: float = 5.0,
    max_retries: int = 3
) -> bool:
    import time

    if not service_url:
        print("DOCLING_SERVICE_URL is not configured")
        return False

    parsed = urlparse(service_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8082

    print(f"Checking Docling service at {host}:{port}")

    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries}")
            with socket.create_connection((host, port), timeout=timeout_seconds):
                print("✓ Docling service reachable")
                return True
        except OSError as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                print(f"Retrying... {e}")
            else:
                print(f"✗ Failed to connect: {e}")
                return False

    return False


def _ensure_images_table_exists():
    if not POSTGRES_AVAILABLE:
        print("PostgreSQL not available")
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
            if not client:
                return False

            client.ensure_table_exists(create_table_sql)

            # check image_hash column
            try:
                result = client.execute_query(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='docling_images' AND column_name='image_hash'
                    """,
                    fetch=True
                )

                if not result:
                    client.execute_query(
                        "ALTER TABLE docling_images ADD COLUMN image_hash VARCHAR(64)"
                    )
                    client.execute_query(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_docling_images_hash ON docling_images(image_hash)"
                    )
                    client.commit()
                    print("Added image_hash column")

            except Exception as e:
                print(f"image_hash check failed: {e}")

            # check image_description column
            try:
                result = client.execute_query(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='docling_images' AND column_name='image_description'
                    """,
                    fetch=True
                )

                if not result:
                    client.execute_query(
                        "ALTER TABLE docling_images ADD COLUMN image_description TEXT"
                    )
                    client.commit()
                    print("Added image_description column")

            except Exception as e:
                print(f"image_description check failed: {e}")

        return True

    except Exception as e:
        print(f"Table creation failed: {e}")
        return False


def _extract_and_store_images(text: str, source_file: str = "unknown") -> Tuple[str, int]:

    if not POSTGRES_AVAILABLE:
        # fallback: strip images
        text = re.sub(r'\[Image\]\s*\(data:image/[^)]+\)', '', text, flags=re.DOTALL)
        text = re.sub(r'\(data:image/[^)]+\)', '', text, flags=re.DOTALL)
        return text.strip(), 0

    if not _ensure_images_table_exists():
        return text, 0

    images_stored = 0

    def replace_image(match):
        nonlocal images_stored

        try:
            full_match = match.group(0)

            type_match = re.search(r'data:image/([^;)]+);base64,', full_match)
            if not type_match:
                return ""

            image_type = type_match.group(1)

            base64_start = full_match.find('base64,') + len('base64,')
            base64_end = full_match.rfind(')')
            base64_data = full_match[base64_start:base64_end]

            image_hash = hashlib.sha256(base64_data.encode()).hexdigest()
            image_id = f"img_{image_hash[:16]}"

            with connection_scoped_client() as client:
                if not client:
                    return ""

                existing = client.execute_query(
                    "SELECT image_id FROM docling_images WHERE image_hash = %s LIMIT 1",
                    params=(image_hash,),
                    fetch=True,
                    dict_cursor=True
                )

                if existing:
                    return f"[Image:{existing[0]['image_id']}]"

                record = {
                    "image_id": image_id,
                    "image_hash": image_hash,
                    "base64_data": base64_data,
                    "image_type": image_type,
                    "source_file": source_file,
                    "created_at": datetime.now()
                }

                if client.insert_record("docling_images", record, upsert_key="image_hash"):
                    images_stored += 1
                    return f"[Image:{image_id}]"

                return ""

        except Exception as e:
            print(f"Image processing error: {e}")
            return ""

    text = re.sub(r'\[Image\]\s*\(data:image/[^)]+\)', replace_image, text, flags=re.DOTALL)
    text = re.sub(r'\(data:image/[^)]+\)', replace_image, text, flags=re.DOTALL)

    return text.strip(), images_stored


def create_docling_tools() -> Optional[callable]:
    if not _is_docling_service_available(DOCLING_SERVICE_URL):
        print(f"Docling service not reachable at {DOCLING_SERVICE_URL}")
        return None
    return extract_document_content


@tool(
    instructions="Use this tool ONLY ONCE when files are uploaded and document content has not been extracted yet."
)
async def extract_document_content(files: Optional[Sequence[File]] = None) -> str:

    if not files:
        return "No files provided"

    extracted_texts = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for file in files:
            try:
                response = await client.post(
                    DOCLING_SERVICE_URL,
                    files={"file": (file.filename or "document", file.content)}
                )

                if response.status_code != 200:
                    extracted_texts.append(f"HTTP {response.status_code}")
                    continue

                result = response.json()

                if result.get("status") != "success":
                    extracted_texts.append("Extraction failed")
                    continue

                text = result["prediction"].get("text", "")

                cleaned_text, _ = _extract_and_store_images(
                    text,
                    result["prediction"].get("metadata", {}).get("source_file", "unknown")
                )

                extracted_texts.append(cleaned_text)

            except Exception as e:
                print(f"Error processing file: {e}")
                extracted_texts.append("Processing error")

    return "\n\n".join(extracted_texts)
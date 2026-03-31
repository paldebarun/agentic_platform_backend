import uuid
from typing import List, Optional

import blake3
import httpx
from fastapi import UploadFile

from agno_agents.custom_tools.docling_extractor import _extract_and_store_images
from interfaces.agent_run.service import get_by_user_hash, insert
from interface.utils.config import DOCLING_SERVICE_URL
from interface.utils.log import logger


async def process_uploads_and_build_message(
    files: List[UploadFile],
    message: str,
    session_id: str,
    user_id: Optional[str],
    org_id: str,
    *,
    log_prefix: str = "send_message",
) -> tuple[List[str], str]:
    """
    Process uploaded files: hash, dedupe, extract, store in DB, then build
    message with document_id references. Returns (document_ids, message_with_docs).
    """
    document_ids: List[str] = []
    if not files:
        return (document_ids, message)

    logger.info(
        "%s: processing %d file(s), storage=postgres",
        log_prefix,
        len(files),
    )

    for upload in files:
        if not getattr(upload, "read", None):
            logger.warning("%s: skipping upload (no .read), type=%s", log_prefix, type(upload).__name__)
            continue
        try:
            content = await upload.read()
            await upload.seek(0)
        except Exception as exc:
            logger.warning("Failed reading upload for %s: %s", log_prefix, exc)
            continue
        content_hash = blake3.blake3(content).hexdigest()
        existing = get_by_user_hash(user_id, content_hash)
        if existing:
            logger.debug(
                "%s: reusing existing document hash=%s document_id=%s",
                log_prefix,
                content_hash[:16],
                existing["document_id"],
            )
            document_ids.append(existing["document_id"])
            continue

        filename = getattr(upload, "filename", None) or "document"
        logger.info("%s: file not in DB, extracting and storing for file=%s", log_prefix, filename)
        cleaned = await extract_document_content_bytes(content, filename)
        if cleaned.startswith("Error:"):
            logger.warning("%s: extraction failed for file=%s: %s", log_prefix, filename, cleaned[:200])
            continue

        document_id = str(uuid.uuid4())
        file_path_val: Optional[str] = None
        file_content_for_db: Optional[bytes] = content

        doc_id = insert(
            document_id=document_id,
            session_id=session_id,
            user_id=user_id,
            content_hash=content_hash,
            filename=filename,
            extracted_text=cleaned,
            file_path=file_path_val,
            org_id=None,
            file_content=file_content_for_db,
        )
        if doc_id:
            logger.info(
                "%s: stored document doc_id=%s filename=%s path=%s",
                log_prefix,
                doc_id,
                filename,
                file_path_val or "(db)",
            )
            document_ids.append(document_id)
        else:
            logger.error(
                "%s: failed to store document document_id=%s filename=%s",
                log_prefix,
                document_id,
                filename,
            )

    message_with_docs = message
    if document_ids:
        message_with_docs = (
            message
            + "\n\n[Attached documents]\n"
            + "\n".join(f"document_id: {doc_id}" for doc_id in document_ids)
        )
    return (document_ids, message_with_docs)


async def extract_document_content_bytes(content: bytes, filename: str) -> str:
    """
    Extract document text from raw file bytes using the Docling service.
    Uses the same Docling URL and _extract_and_store_images as the tool.
    Call this as a plain function (not an agent tool) for send_message flow.
    """
    docling_url = DOCLING_SERVICE_URL
    if not docling_url:
        logger.error("Docling service URL is not configured , value %s", DOCLING_SERVICE_URL)
        return "Error: Docling service is not configured (DOCLING_SERVICE_URL)."


    display_name = filename or "document"
    try:
        files_payload = {"file": (display_name, content)}
        logger.info("Sending %s to Docling service (bytes)...", display_name)
        async with httpx.AsyncClient(timeout=3600.0) as client:
            response = await client.post(docling_url, files=files_payload)
        if response.status_code != 200:
            logger.error(f"Error: HTTP {response.status_code} - {response.text[:200]}")
            return f"Error"
        result = response.json()
        status = result.get("status")
        if status != "success" or "prediction" not in result:
            return f"Error: Docling extraction failed (status={status})"
        extracted_text = result["prediction"].get("text", "")
        if not extracted_text:
            return "Error: Empty text returned by Docling"
        metadata = result["prediction"].get("metadata", {})
        source_file = metadata.get("source_file", display_name)
        cleaned_text, images_stored = _extract_and_store_images(extracted_text, source_file)
        if images_stored:
            logger.info("Stored %s image(s) from %s", images_stored, source_file)
        return cleaned_text
    except Exception as e:
        error_msg = f"Error processing {display_name}"
        logger.error(error_msg + " : " + str(e))
        return error_msg
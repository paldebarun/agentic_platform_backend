import uuid
from typing import List, Optional

import blake3
import httpx
from fastapi import UploadFile

from custom_tools.docling_tool import _extract_and_store_images
from interfaces.agent_run.service import get_by_user_hash, insert
from app_config import DOCLING_SERVICE_URL


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

    for upload in files:
        if not getattr(upload, "read", None):
            continue
        try:
            content = await upload.read()
            await upload.seek(0)
        except Exception:
            continue
        content_hash = blake3.blake3(content).hexdigest()
        existing = get_by_user_hash(user_id, content_hash)
        if existing:
            document_ids.append(existing["document_id"])
            continue

        filename = getattr(upload, "filename", None) or "document"
        cleaned = await extract_document_content_bytes(content, filename)
        if cleaned.startswith("Error:"):
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
            document_ids.append(document_id)

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
        return "Error: Docling service is not configured (DOCLING_SERVICE_URL)."


    display_name = filename or "document"
    try:
        files_payload = {"file": (display_name, content)}
        async with httpx.AsyncClient(timeout=3600.0) as client:
            response = await client.post(docling_url, files=files_payload)
        if response.status_code != 200:
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
        cleaned_text, _ = _extract_and_store_images(extracted_text, source_file)
        return cleaned_text
    except Exception as e:
        error_msg = f"Error processing {display_name}"
        return error_msg
from typing import List, Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from interfaces.agent_run.util import process_uploads_and_build_message
from app_config import AGENT_OS_BASE_URL
from interfaces.utils.id_validation import validate_uuid

router = APIRouter()


@router.post("/agents/{agent_id}/send_message")
async def send_message(
    agent_id: str,
    message: str = Form(..., description="User message text"),
    stream: str = Form("true", description="Whether to stream the response (SSE)"),
    session_id: str = Form(..., description="Session ID for the conversation"),
    user_id: Optional[str] = Form(None, description="User ID"),
    version: Optional[str] = Form(None, description="Agent version"),
    org_id: str = Form("default", description="Organization ID for blob storage path"),
    files: Optional[List[UploadFile]] = File(None, description="Optional files to extract and attach"),
):
    stream_val = stream
    session_id = validate_uuid(session_id, "session_id")
    user_id = (user_id or "").strip() or None
    version = (version or "").strip() or None
    org_id = (org_id or "default").strip() or "default"
    if files is None:
        files = []
    elif not isinstance(files, list):
        files = [files]

    if files and not session_id:
        raise HTTPException(
            status_code=400,
            detail="session_id is required when sending files",
        )

    document_ids, message_with_docs = await process_uploads_and_build_message(
        files, message, session_id, user_id, org_id, log_prefix="send_message"
    )

    # Forward to run endpoint (use configured API base URL)
    base = (AGENT_OS_BASE_URL or "").rstrip("/")

    run_url = f"{base}/agents/{agent_id}/runs"

    form_data = {
        "message": message_with_docs,
        "stream": stream_val,
        "session_id": session_id,
        "user_id": user_id or "",
    }
    if version:
        form_data["version"] = version

    async def stream_chunks():
        try:
            headers = {"Accept": "text/event-stream"}
            async with httpx.AsyncClient(timeout=3600.0) as client:
                async with client.stream(
                    "POST",
                    run_url,
                    data=form_data,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except httpx.HTTPStatusError as e:
            try:
                await e.response.aread()
            except Exception:
                pass
            raise
        except Exception:
            raise

    return StreamingResponse(
        stream_chunks(),
        media_type="text/event-stream",
    )
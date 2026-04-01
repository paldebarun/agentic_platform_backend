from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from interfaces.agent_run.util import process_uploads_and_build_message
from app_config import AGENT_OS_BASE_URL
from interfaces.utils.id_validation import validate_uuid

router = APIRouter()


@router.post("/teams/{team_id}/send_message")
async def send_team_message(
    team_id: str,
    request: Request,
    message: str = Form(..., description="User message text"),
    stream: str = Form("true", description="Whether to stream the response (SSE)"),
    session_id: str = Form(..., description="Session ID for the conversation"),
    user_id: Optional[str] = Form(None, description="User ID"),
    version: Optional[str] = Form(None, description="Team version"),
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

    print(
        "send_team_message: team_id=%s session_id=%s user_id=%s version=%s stream=%s files_count=%d",
        team_id,
        session_id or "(empty)",
        user_id or "(none)",
        version or "(none)",
        stream_val,
        len(files),
    )
    if files and not session_id:
        print("send_team_message: rejected - session_id required when sending files")
        raise HTTPException(
            status_code=400,
            detail="session_id is required when sending files",
        )

    document_ids, message_with_docs = await process_uploads_and_build_message(
        files, message, session_id, user_id, org_id, log_prefix="send_team_message"
    )

    base = (AGENT_OS_BASE_URL or "").rstrip("/")
    run_url = f"{base}/teams/{team_id}/runs"
    print(  
        "send_team_message: forwarding to team run endpoint url=%s docs_attached=%d",  
        run_url,  
        len(document_ids),  
    )  
  
    form_data = {  
        "message": message_with_docs,  
        "stream": stream_val,  
        "session_id": session_id,  
        "user_id": user_id or "",  
    }  
    if version:  
        form_data["version"] = version  
  
    # Stream response from team run (forward Authorization from incoming request)
    async def stream_chunks():
        try:
            headers = {"Accept": "text/event-stream"}
            auth = request.headers.get("Authorization")
            if auth:
                headers["Authorization"] = auth
            print("send_team_message: opening stream to %s", run_url)
            async with httpx.AsyncClient(timeout=3600.0) as client:
                async with client.stream(
                    "POST",
                    run_url,
                    data=form_data,
                    headers=headers,
                ) as response:  
                    response.raise_for_status()  
                    print(  
                        "send_team_message: stream started status=%s",  
                        response.status_code,  
                    )  
                    async for chunk in response.aiter_bytes():  
                        yield chunk  
            print("send_team_message: stream completed successfully")  
        except httpx.HTTPStatusError as e:
            err_body = ""
            try:
                body_bytes = await e.response.aread()
                err_body = (body_bytes.decode("utf-8", errors="replace") or "")[:500]
            except Exception:
                err_body = "(streaming response body not available)"
            print(
                "send_team_message: team run endpoint error status=%s response=%s",
                e.response.status_code,
                err_body,
            )
            raise  
        except Exception as e:  
            print("send_team_message: stream failed: %s", e)  
            raise  
  
    return StreamingResponse(  
        stream_chunks(),  
        media_type="text/event-stream",  
    )
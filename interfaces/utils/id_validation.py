"""
Validate session_id and document_id as UUIDs before URL/DB use.

Returns 400 if invalid so invalid strings never reach downstream or DB.
"""

import uuid

from fastapi import HTTPException


def validate_uuid(value: str, param_name: str = "id") -> str:
   
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"Invalid {param_name}: expected a UUID string")
    s = value.strip()
    if not s:
        raise HTTPException(status_code=400, detail=f"Invalid {param_name}: value is empty")
    try:
        uuid.UUID(str(s))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name}: must be a valid UUID (e.g. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)",
        )
    return s

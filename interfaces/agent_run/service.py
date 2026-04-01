"""
Extracted documents storage.

Stores document content hash, extracted text, and file_path (blob) or file_content in Postgres,
keyed by session_id and user_id for segregation. Used for send_message deduplication.
"""

from typing import Any, Dict, List, Optional

from services.db_service import PostgresClient, connection_scoped_client, POSTGRES_AVAILABLE

_EXTRACTED_DOCUMENTS_TABLE = "extracted_documents"
_table_initialized = False


def ensure_extracted_documents_table() -> None:
    global _table_initialized
    if _table_initialized:
        return
    if not POSTGRES_AVAILABLE:
        return
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {_EXTRACTED_DOCUMENTS_TABLE} (
        document_id UUID PRIMARY KEY,
        content_hash TEXT NOT NULL,
        session_id UUID NOT NULL,
        user_id TEXT NULL,
        filename TEXT NOT NULL,
        extracted_text TEXT NOT NULL,
        file_path TEXT NULL,
        org_id TEXT NULL,
        file_content BYTEA NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (session_id, user_id, content_hash)
    );
    CREATE INDEX IF NOT EXISTS idx_extracted_documents_session_user
        ON {_EXTRACTED_DOCUMENTS_TABLE} (session_id, user_id);
    CREATE INDEX IF NOT EXISTS idx_extracted_documents_hash
        ON {_EXTRACTED_DOCUMENTS_TABLE} (session_id, user_id, content_hash);
    """
    try:
        with connection_scoped_client() as client:
            client.ensure_table_exists(create_sql)
            _add_file_path_org_id_columns(client)
        _table_initialized = True
    except Exception:
        pass


def _add_file_path_org_id_columns(client: PostgresClient) -> None:
    """Add file_path and org_id columns if they don't exist (migration)."""
    for col in ("file_path", "org_id"):
        try:
            check = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """
            if not client.execute_query(check, params=(_EXTRACTED_DOCUMENTS_TABLE, col), fetch=True):
                with client.conn.cursor() as cur:
                    cur.execute(
                        f"ALTER TABLE {_EXTRACTED_DOCUMENTS_TABLE} ADD COLUMN {col} TEXT NULL"
                    )
                client.commit()
        except Exception:
            pass


def get_by_session_user_hash(
    session_id: str,
    user_id: Optional[str],
    content_hash: str,
) -> Optional[Dict[str, Any]]:
    """Return existing row if (session_id, user_id, content_hash) exists."""
    if not POSTGRES_AVAILABLE:
        return None
    ensure_extracted_documents_table()
    query = f"""
        SELECT document_id, extracted_text, filename, content_hash, file_path, org_id, created_at
        FROM {_EXTRACTED_DOCUMENTS_TABLE}
        WHERE session_id = %s AND (user_id IS NOT DISTINCT FROM %s) AND content_hash = %s
        LIMIT 1
    """
    try:
        with connection_scoped_client() as client:
            rows = client.execute_query(
                query,
                params=(session_id, user_id, content_hash),
                fetch=True,
                dict_cursor=True,
            ) or []
        if not rows:
            return None
        row = rows[0]
        out = {
            "document_id": str(row["document_id"]),
            "extracted_text": row["extracted_text"],
            "filename": row["filename"],
            "content_hash": row["content_hash"],
            "created_at": row["created_at"],
        }
        if "file_path" in row and row["file_path"]:
            out["file_path"] = row["file_path"]
        if "org_id" in row and row["org_id"]:
            out["org_id"] = row["org_id"]
        return out
    except Exception:
        return None


def get_by_user_hash(
    user_id: Optional[str],
    content_hash: str,
) -> Optional[Dict[str, Any]]:
    """Return existing row if (user_id, content_hash) exists (any session)."""
    if not POSTGRES_AVAILABLE:
        return None
    ensure_extracted_documents_table()
    query = f"""
        SELECT document_id, extracted_text, filename, content_hash, file_path, org_id, created_at
        FROM {_EXTRACTED_DOCUMENTS_TABLE}
        WHERE (user_id IS NOT DISTINCT FROM %s) AND content_hash = %s
        ORDER BY created_at DESC
        LIMIT 1
    """
    try:
        with connection_scoped_client() as client:
            rows = client.execute_query(
                query,
                params=(user_id, content_hash),
                fetch=True,
                dict_cursor=True,
            ) or []
        if not rows:
            return None
        row = rows[0]
        out = {
            "document_id": str(row["document_id"]),
            "extracted_text": row["extracted_text"],
            "filename": row["filename"],
            "content_hash": row["content_hash"],
            "created_at": row["created_at"],
        }
        if "file_path" in row and row["file_path"]:
            out["file_path"] = row["file_path"]
        if "org_id" in row and row["org_id"]:
            out["org_id"] = row["org_id"]
        return out
    except Exception:
        return None


def insert(
    document_id: str,
    session_id: str,
    user_id: Optional[str],
    content_hash: str,
    filename: str,
    extracted_text: str,
    *,
    file_path: Optional[str] = None,
    org_id: Optional[str] = None,
    file_content: Optional[bytes] = None,
) -> Optional[str]:
    """
    Insert a new extracted document. document_id must be provided (e.g. from blob upload).
    Returns document_id or None.
    """
    if not POSTGRES_AVAILABLE:
        return None
    ensure_extracted_documents_table()
    query = f"""
        INSERT INTO {_EXTRACTED_DOCUMENTS_TABLE}
        (document_id, content_hash, session_id, user_id, filename, extracted_text, file_path, org_id, file_content)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with connection_scoped_client() as client:
            with client.conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        document_id,
                        content_hash,
                        session_id,
                        user_id,
                        filename,
                        extracted_text,
                        file_path,
                        org_id,
                        file_content,
                    ),
                )
            client.commit()
        return document_id
    except Exception:
        return None


def get_by_document_id(document_id: str) -> Optional[Dict[str, Any]]:
    """Return row by document_id for retrieval by id (includes file_path for blob download)."""
    if not POSTGRES_AVAILABLE:
        return None
    ensure_extracted_documents_table()
    query = f"""
        SELECT document_id, session_id, user_id, filename, extracted_text, content_hash, file_path, org_id, created_at
        FROM {_EXTRACTED_DOCUMENTS_TABLE}
        WHERE document_id = %s
        LIMIT 1
    """
    try:
        with connection_scoped_client() as client:
            rows = client.execute_query(
                query,
                params=(document_id,),
                fetch=True,
                dict_cursor=True,
            ) or []
        if not rows:
            return None
        row = rows[0]
        out = {
            "document_id": str(row["document_id"]),
            "session_id": str(row["session_id"]),
            "user_id": row["user_id"],
            "filename": row["filename"],
            "extracted_text": row["extracted_text"],
            "content_hash": row["content_hash"],
            "created_at": row["created_at"],
        }
        if "file_path" in row and row["file_path"]:
            out["file_path"] = row["file_path"]
        if "org_id" in row and row["org_id"]:
            out["org_id"] = row["org_id"]
        return out
    except Exception:
        return None


def get_document_for_download(document_id: str) -> Optional[Dict[str, Any]]:
    """Return file_path (blob) or file_content (bytes) and filename for streaming download."""
    if not POSTGRES_AVAILABLE:
        return None
    ensure_extracted_documents_table()
    query = f"""
        SELECT filename, file_path, file_content, org_id
        FROM {_EXTRACTED_DOCUMENTS_TABLE}
        WHERE document_id = %s
        LIMIT 1
    """
    try:
        with connection_scoped_client() as client:
            rows = client.execute_query(
                query,
                params=(document_id,),
                fetch=True,
                dict_cursor=True,
            ) or []
        if not rows:
            return None
        row = rows[0]
        out: Dict[str, Any] = {"filename": row["filename"] or document_id}
        if row.get("file_path"):
            out["file_path"] = row["file_path"]
        if row.get("file_content") is not None:
            out["file_content"] = bytes(row["file_content"]) if isinstance(row["file_content"], memoryview) else row["file_content"]
        if row.get("org_id"):
            out["org_id"] = row["org_id"]
        return out if out.get("file_path") or out.get("file_content") else out
    except Exception:
        return None


def list_by_session_user(
    session_id: str,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List document metadata for a session (optionally filtered by user_id)."""
    if not POSTGRES_AVAILABLE:
        return []
    ensure_extracted_documents_table()
    if user_id is not None:
        query = f"""
            SELECT document_id, filename, content_hash, file_path, created_at
            FROM {_EXTRACTED_DOCUMENTS_TABLE}
            WHERE session_id = %s AND (user_id IS NOT DISTINCT FROM %s)
            ORDER BY created_at ASC
        """
        params: tuple = (session_id, user_id)
    else:
        query = f"""
            SELECT document_id, filename, content_hash, file_path, created_at
            FROM {_EXTRACTED_DOCUMENTS_TABLE}
            WHERE session_id = %s
            ORDER BY created_at ASC
        """
        params = (session_id,)
    try:
        with connection_scoped_client() as client:
            rows = client.execute_query(query, params=params, fetch=True, dict_cursor=True) or []
        return [
            {
                "document_id": str(r["document_id"]),
                "filename": r["filename"],
                "content_hash": r["content_hash"],
                "file_path": r.get("file_path"),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    except Exception:
        return []

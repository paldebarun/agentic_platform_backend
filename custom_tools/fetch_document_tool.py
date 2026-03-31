"""Tool to get document details by document_id (from extracted_documents store)."""

from agno.tools import tool
from interfaces.agent_run.service import get_by_document_id



@tool(instructions="Use this to fetch document details when the user message contains document_id (e.g. from [Attached documents]).")
def get_document(document_id: str) -> str:
    """
    Get document details by document_id.

    Args:
        document_id: UUID of the document (from attached documents in the message).

    Returns:
        Document details including filename and extracted_text, or an error message if not found.
    """
    print(f"get_document called with document_id: {document_id}")  
    doc = get_by_document_id(document_id.strip())
    if not doc:
        print(f"No document found for document_id={document_id}")
        return f"Error: No document found for document_id={document_id}"
    extracted = doc.get("extracted_text") or ""
    print(f"Extracted text: {extracted}")
    filename = doc.get("filename") or "document"
    file_path = doc.get("file_path") or ""
    print(f"Document found for document_id: {document_id}")
    print(f"Document details: {doc}")
    return f"document_id: {doc['document_id']}\nfilename: {filename}\nextracted_text:\n{extracted}\nfile_path: {file_path}"

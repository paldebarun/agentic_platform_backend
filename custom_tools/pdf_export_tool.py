import os
import uuid
from datetime import datetime

from agno.tools import tool
from markdown import markdown
from weasyprint import HTML


REPORTS_DIR = "./reports"


def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


@tool(
    name="generate_pdf_report",
    instructions="Use this tool to convert a markdown report into a downloadable PDF file and return its file path and URL."
)
def generate_pdf_report(markdown_text: str) -> str:
    """
    Convert markdown to PDF, store locally, and return file path + URL.
    """

    if not markdown_text:
        return "No content provided"

    try:
        _ensure_reports_dir()

        # Unique filename
        file_id = str(uuid.uuid4())[:8]
        filename = f"report_{file_id}.pdf"
        file_path = os.path.join(REPORTS_DIR, filename)

        # Convert markdown → HTML
        html_content = markdown(markdown_text)

        # Wrap with basic styling
        styled_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    padding: 20px;
                    line-height: 1.6;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                pre {{
                    background: #f4f4f4;
                    padding: 10px;
                    overflow-x: auto;
                }}
                code {{
                    background: #f4f4f4;
                    padding: 2px 4px;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF
        HTML(string=styled_html).write_pdf(file_path)

        # Return path (you can convert to URL later)
        return f"PDF generated successfully. File path: {file_path}"

    except Exception as e:
        print(f"PDF generation error: {e}")
        return "Failed to generate PDF"
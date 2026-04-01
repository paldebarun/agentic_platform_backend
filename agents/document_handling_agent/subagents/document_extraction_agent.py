from templates.agent_template import AGENT_TEMPLATE
from agents.document_handling_agent.config import DOCUMENT_EXTRACTION_INSTRUCTIONS


def create_document_extraction_agent():
    agent_wrapper = AGENT_TEMPLATE(
        name="Document Extraction Agent",
        tools=[],
        instructions=DOCUMENT_EXTRACTION_INSTRUCTIONS,
        markdown=False,
    )

    agent_wrapper.initialize()
    return agent_wrapper
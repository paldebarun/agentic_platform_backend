from templates.agent_template import AGENT_TEMPLATE
from agents.document_handling_agent.config import DOCUMENT_VALIDATION_INSTRUCTIONS


def create_document_validation_agent():
    agent_wrapper = AGENT_TEMPLATE(
        name="Document Validation Agent",
        tools=[],
        instructions=DOCUMENT_VALIDATION_INSTRUCTIONS,
        markdown=False,
    )

    agent_wrapper.initialize()
    return agent_wrapper
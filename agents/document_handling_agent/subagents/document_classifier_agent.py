from templates.agent_template import AGENT_TEMPLATE
from document_handling_agent.config import DOCUMENT_CLASSIFIER_INSTRUCTIONS


def create_document_classifier_agent():
    agent_wrapper = AGENT_TEMPLATE(
        name="Document Classifier Agent",
        tools=[],
        instructions=DOCUMENT_CLASSIFIER_INSTRUCTIONS,
        markdown=False,
    )

    agent_wrapper.initialize()
    return agent_wrapper
from agno.agent import Agent
from app_config import get_model
from prototype_agent.config import DOCUMENT_CLASSIFIER_INSTRUCTIONS


def create_document_classifier_agent() -> Agent:
    return Agent(
        name="Document Classifier Agent",
        model=get_model("worker"),
        tools=[],
        instructions=DOCUMENT_CLASSIFIER_INSTRUCTIONS,
        markdown=False,
    )
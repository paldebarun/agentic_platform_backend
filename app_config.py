import os
from agno.models.openai import OpenAIChat

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "localhost")
OLLAMA_PORT = os.environ.get("OLLAMA_PORT", "11434")
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "v1")
OLLAMA_PROTOCOL = os.environ.get("OLLAMA_PROTOCOL", "http")

OLLAMA_URL = f"{OLLAMA_PROTOCOL}://{OLLAMA_BASE_URL}:{OLLAMA_PORT}/{OLLAMA_ENDPOINT}"


def get_model(role: str = "worker"):
    model_map = {
        "fast": "phi3:latest",
        "worker": "mixtral:latest",
        "planner": "mixtral:latest",
    }

    return OpenAIChat(
        id=model_map.get(role, "phi3:latest"),
        api_key="ollama",
        base_url=OLLAMA_URL,  
        temperature=0,
    )
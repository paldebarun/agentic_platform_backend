import os
# from agno.models.openai import OpenAIChat
from agno.models.google import Gemini
from dotenv import load_dotenv


load_dotenv()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "localhost")
OLLAMA_PORT = os.environ.get("OLLAMA_PORT", "11434")
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "v1")
OLLAMA_PROTOCOL = os.environ.get("OLLAMA_PROTOCOL", "http")

OLLAMA_URL = f"{OLLAMA_PROTOCOL}://{OLLAMA_BASE_URL}:{OLLAMA_PORT}/{OLLAMA_ENDPOINT}"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

POSTGRES_USER=os.environ.get("POSTGRES_USER","admin")
POSTGRES_PASSWORD=os.environ.get("POSTGRES_PASSWORD","admin")
POSTGRESS_PORT=os.environ.get("POSTGRESS_PORT",5432)
POSTGRES_DB=os.environ.get("POSTGRES_DB","docling_db")
POSTGRES_HOST=os.environ.get("POSTGRES_HOST","localhost")

POSTGRES_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRESS_PORT}/{POSTGRES_DB}"

DOCLING_SERVICE_URL="http://localhost:8082"

# def get_model(role: str = "worker"):
#     model_map = {
#         "fast": "phi3:latest",
#         "worker": "mixtral:latest",
#         "planner": "mixtral:latest",
#     }

#     return OpenAIChat(
#         id=model_map.get(role, "phi3:latest"),
#         api_key="ollama",
#         base_url=OLLAMA_URL,  
#         temperature=0,
#     )

HOST=os.environ.get("HOST","localhost")
PORT=os.environ.get("PORT",8000)
ENVIRONMENT=os.environ.get("ENVIRONMENT","development")
BASE_PROTOCOL = os.environ.get("BASE_PROTOCOL", "http")

def get_model(role: str = "worker"):
    model_map = {
        "fast": "gemini-1.5-flash",
        "worker": "gemini-1.5-pro",
        "planner": "gemini-1.5-pro",
    }

    return Gemini(
        id=model_map.get(role, "gemini-1.5-flash"),
        api_key=GEMINI_API_KEY,
    )


AGENT_OS_BASE_URL = os.environ.get(
    "AGENT_OS_BASE_URL",
    f"{BASE_PROTOCOL}://{HOST}:{PORT}",
)
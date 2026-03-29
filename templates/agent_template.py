from agno.agent import Agent
from typing import Optional, List, Any
from backend.app_config import get_model


class AGENT_TEMPLATE:
    """Lightweight Agno Agent Template (Ollama/OpenAI-compatible)"""

    def __init__(
        self,
        model: Optional[Any] = None,  
        tools: Optional[List] = None,
        instructions: str = "",
        name: str = "",
        markdown: bool = False,
    ):
        self.name = name
        self.model = model or get_model("worker")   
        self.tools = tools or []
        self.instructions = instructions
        self.markdown = markdown
        self.agent = None

    def initialize(self):
        """Create agent (no async needed now)"""
        if self.agent:
            return

        self.agent = Agent(
            name=self.name,
            model=self.model,  
            tools=self.tools,
            instructions=self.instructions,
            markdown=self.markdown,
        )

    async def chat(self, message: str, stream: bool = False):
        if not self.agent:
            self.initialize()

        if stream:
            return await self.agent.aprint_response(message)
        else:
            return await self.agent.arun(message)
from agno.os import AgentOS
from typing import Optional, List


class AGENT_OS:
    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        agents: Optional[List] = None,
        teams: Optional[List] = None,
        interfaces: Optional[List] = None,
    ):
        self.name = name
        self.description = description
        self.agents = agents or []
        self.teams = teams or []
        self.interfaces = interfaces or []

        self.agent_os = AgentOS(
            name=self.name,   
            description=self.description,
            agents=self.agents,
            interfaces=self.interfaces,
            teams=self.teams,
        )

    def get_app(self):
        return self.agent_os.get_app()
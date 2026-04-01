"""
Agno Agents - Global Main Entry Point

Discovers and runs all agents from the /agents/ folder.
Each folder under /agents/ represents one agent that will appear in the Agno OS UI.
"""

import asyncio
import os
import json

import uvicorn

from agno.os import AgentOS
from agno.os.interfaces.agui import AGUI
# from fastapi.responses import JSONResponse

# from interface.utils.health import check_db, check_docling
from app_config import PORT,ENVIRONMENT,HOST
# from agno_agents.log import setup_logging
# from agno_agents.mcp_tools_configuration import log_mcp_tools_on_startup
# from interface.chat_title.controller import router as chat_title_router
# from interface.custom_agent_run.controller import router as custom_agent_run_router
# from interface.custom_team_run.controller import router as custom_team_run_router
# from interface.file_manager.controller import router as file_manager_router
# from interface.fs_nodes.controller import router as fs_nodes_router
# from interface.images.controller import router as images_router
# from agno_agents.Teams.file_organisation_team import file_organisation_team

# from agno_agents.Teams.document_processing import (
#     master_agent_team as document_processing_team,
# )
# from agno_agents.Teams.agentic_rag_team import (
#     master_agent_team as agentic_rag_team,
# )
# from agno_agents.Teams.structured_extraction_team import (
#     structured_extraction_team,
# )
# from agno_agents.Teams.researcher_team import (
#     researcher_team,
# )

# Import orchestrator agents from each agent folder
from agents.document_handling_agent.orchestrator_agent import (
    orchestrator_agent as document_handling_agent,
)
# from agno_agents.agents.rag_agent import rag_agent
# from agno_agents.Teams.brand_research_team import brand_research_team

# from agno_agents.Teams.brand_health_monitoring_team import brand_health_monitoring_team
# from agno_agents.Teams.sentiment_analysis_team import sentiment_analysis_team

all_agents = [
    document_handling_agent,
]

# all_teams = [
#     document_processing_team,
#     agentic_rag_team,
#     structured_extraction_team,
#     file_organisation_team,
#     researcher_team,
#     brand_research_team,
#     brand_health_monitoring_team,
#     sentiment_analysis_team,
# ]

all_interfaces = [
    AGUI(agent=document_handling_agent),
    # AGUI(agent=rfp_evaluation_agent),
    # AGUI(agent=invoice_parsing_agent),
    # AGUI(agent=pricebook_agent),
    # AGUI(agent=file_organiser_agent),
    # AGUI(team=document_processing_team),
    # AGUI(team=file_organisation_team),
    # AGUI(team=agentic_rag_team),
    # AGUI(team=structured_extraction_team),
    # AGUI(team=researcher_team),
    # AGUI(team=brand_research_team),
    # AGUI(team=brand_health_monitoring_team),
    # AGUI(team=sentiment_analysis_team),
]

global_agent_os = AgentOS(
    description="Multi-agent system with Contract Compliance, RFP Evaluation, Invoice Parsing, Pricebook Management, and File Organisation. RAG (ChromaDB) is available via the Agentic RAG team only.",
    agents=all_agents,
    # teams=all_teams,
    interfaces=all_interfaces,
)


app = global_agent_os.get_app()

# app.include_router(chat_title_router)
# app.include_router(custom_agent_run_router)
# app.include_router(custom_team_run_router)
# app.include_router(file_manager_router)
# app.include_router(fs_nodes_router)
# app.include_router(images_router)
# setup_logging(app)





# @app.get("/ready")
# async def ready():
#     """Readiness probe: DB (and optionally Docling) are reachable. Use for Kubernetes readinessProbe."""
#     db_ok, db_status = await asyncio.to_thread(check_db)
#     docling_ok, docling_status = await asyncio.to_thread(check_docling)
#     payload = {"database": db_status, "docling": docling_status}
#     if not db_ok and db_status != "not_configured":
#         payload["ready"] = False
#         return JSONResponse(content=payload, status_code=503)
#     payload["ready"] = True
#     return JSONResponse(content=payload, status_code=200)


# def _normalize_team_key(value: str) -> str:
#     return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


# team_fields_map: dict[str, dict] = {}
# for team in all_teams:
#     raw_team_id = str(
#         getattr(team, "id", None)
#         or getattr(team, "team_id", None)
#         or getattr(team, "name", "")
#     )
#     team_name = str(getattr(team, "name", ""))
#     metadata = getattr(team, "metadata", None)
#     description = getattr(team, "description", None)
#     category = metadata.get("category") if isinstance(metadata, dict) else None

#     fields: dict[str, str] = {}
#     if isinstance(description, str) and description.strip():
#         fields["description"] = description
#     if isinstance(category, str) and category.strip():
#         fields["category"] = category

#     if fields:
#         for key in {
#             raw_team_id,
#             team_name,
#             _normalize_team_key(raw_team_id),
#             _normalize_team_key(team_name),
#         }:
#             if key:
#                 team_fields_map[key] = fields


# @app.middleware("http")
# async def enrich_config_payload_with_category(request, call_next):
#     response = await call_next(request)
#     if request.url.path != "/config":
#         return response

#     try:
#         body = b""
#         async for chunk in response.body_iterator:
#             body += chunk

#         payload = json.loads(body.decode("utf-8"))
#         teams = payload.get("teams")

#         if isinstance(teams, list):
#             enriched_teams = []
#             for team_item in teams:
#                 if not isinstance(team_item, dict):
#                     enriched_teams.append(team_item)
#                     continue

#                 team_id = str(
#                     team_item.get("id")
#                     or team_item.get("team_id")
#                     or team_item.get("name")
#                     or ""
#                 )
#                 team_name = str(team_item.get("name") or "")
#                 source_fields = (
#                     team_fields_map.get(team_id)
#                     or team_fields_map.get(team_name)
#                     or team_fields_map.get(_normalize_team_key(team_id))
#                     or team_fields_map.get(_normalize_team_key(team_name))
#                     or {}
#                 )

#                 enriched_item = dict(team_item)
#                 resolved_description = (
#                     team_item.get("description")
#                     or source_fields.get("description")
#                 )
#                 resolved_category = (
#                     team_item.get("category")
#                     or source_fields.get("category")
#                 )

#                 if isinstance(resolved_description, str) and resolved_description.strip():
#                     enriched_item["description"] = resolved_description
#                 if isinstance(resolved_category, str) and resolved_category.strip():
#                     enriched_item["category"] = resolved_category
#                 enriched_teams.append(enriched_item)

#             payload["teams"] = enriched_teams

#         json_response = JSONResponse(content=payload, status_code=response.status_code)
#         for key, value in response.headers.items():
#             if key.lower() not in {"content-length", "content-type"}:
#                 json_response.headers[key] = value
#         return json_response
#     except Exception as e:
#         return response


# if os.environ.get("RUN_MAIN") != "true":
#     import threading
#     def _delayed() -> None:
#         import time
#         time.sleep(2)
#         _run_mcp_inspection()
#     threading.Thread(target=_delayed, daemon=True).start()


if __name__ == "__main__":
    host = HOST 
    port = PORT
    environment = ENVIRONMENT
    use_reload = environment != "production"

    print("\n" + "=" * 60)
    print("Agno Agents - Global Agent OS")
    print("=" * 60)
    print("Available Agents (%s):", len(all_agents))
    print("  1. Document Handling Agent")
    print("=" * 60 + "\n")

    # log_mcp_tools_on_startup()

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=use_reload,
        reload_dirs=[
            os.path.join(os.path.dirname(__file__), "agno_agents"),
            os.path.join(os.path.dirname(__file__), "interface"),
        ],
        reload_includes=["*.py"],
        log_level="info",
    )


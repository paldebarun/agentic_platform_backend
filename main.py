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
from fastapi.responses import JSONResponse

from interface.utils.health import check_db, check_docling
from agno_agents.config import SERVER_BASE_URL,PORT,ENVIRONMENT,HOST
from agno_agents.log import setup_logging, logger
from agno_agents.mcp_tools_configuration import log_mcp_tools_on_startup
from interface.chat_title.controller import router as chat_title_router
from interface.custom_agent_run.controller import router as custom_agent_run_router
from interface.custom_team_run.controller import router as custom_team_run_router
from interface.file_manager.controller import router as file_manager_router
from interface.fs_nodes.controller import router as fs_nodes_router
from interface.images.controller import router as images_router
from agno_agents.middlewares.keycloak_auth_dependency import KeycloakAuthMiddleware
from agno_agents.Teams.file_organisation_team import file_organisation_team

from agno_agents.Teams.document_processing import (
    master_agent_team as document_processing_team,
)
from agno_agents.Teams.agentic_rag_team import (
    master_agent_team as agentic_rag_team,
)
from agno_agents.Teams.structured_extraction_team import (
    structured_extraction_team,
)
from agno_agents.Teams.researcher_team import (
    researcher_team,
)

# Import orchestrator agents from each agent folder
from agno_agents.agents.contract_compliance.orchestrator import (
    orchestrator_agent as contract_compliance_agent,
)
from agno_agents.agents.rfp_evaluation.orchestrator import (
    orchestrator_agent as rfp_evaluation_agent,
)
from agno_agents.agents.invoice_parsing.orchestrator import (
    orchestrator_agent as invoice_parsing_agent,
)

from agno_agents.agents.catalogue_pricebook_inventory.orchestrator import (
    pricebook_agent as pricebook_agent,
)
from agno_agents.agents.file_organiser.agent import (
    file_organiser_agent,
)
from agno_agents.agents.sentiment_analysis.agent import (
    agent as sentiment_analysis_agent,
)
from agno_agents.agents.rag_agent import rag_agent
from agno_agents.Teams.brand_research_team import brand_research_team

from agno_agents.Teams.brand_health_monitoring_team import brand_health_monitoring_team
from agno_agents.Teams.sentiment_analysis_team import sentiment_analysis_team

all_agents = [
    contract_compliance_agent,
    rfp_evaluation_agent,
    invoice_parsing_agent,
    pricebook_agent,
    file_organiser_agent,
    sentiment_analysis_agent,
   
]

all_teams = [
    document_processing_team,
    agentic_rag_team,
    structured_extraction_team,
    file_organisation_team,
    researcher_team,
    brand_research_team,
    brand_health_monitoring_team,
    sentiment_analysis_team,
]

all_interfaces = [
    AGUI(agent=contract_compliance_agent),
    AGUI(agent=rfp_evaluation_agent),
    AGUI(agent=invoice_parsing_agent),
    AGUI(agent=pricebook_agent),
    AGUI(agent=file_organiser_agent),
    AGUI(team=document_processing_team),
    AGUI(team=file_organisation_team),
    AGUI(team=agentic_rag_team),
    AGUI(team=structured_extraction_team),
    AGUI(team=researcher_team),
    AGUI(team=brand_research_team),
    AGUI(team=brand_health_monitoring_team),
    AGUI(team=sentiment_analysis_team),
]

global_agent_os = AgentOS(
    description="Multi-agent system with Contract Compliance, RFP Evaluation, Invoice Parsing, Pricebook Management, and File Organisation. RAG (ChromaDB) is available via the Agentic RAG team only.",
    agents=all_agents,
    teams=all_teams,
    interfaces=all_interfaces,
)


app = global_agent_os.get_app()
app.add_middleware(
    KeycloakAuthMiddleware
)

app.include_router(chat_title_router)
app.include_router(custom_agent_run_router)
app.include_router(custom_team_run_router)
app.include_router(file_manager_router)
app.include_router(fs_nodes_router)
app.include_router(images_router)
setup_logging(app)


# app.add_middleware(
#     KeycloakAuthMiddleware
# )



@app.get("/ready")
async def ready():
    """Readiness probe: DB (and optionally Docling) are reachable. Use for Kubernetes readinessProbe."""
    db_ok, db_status = await asyncio.to_thread(check_db)
    docling_ok, docling_status = await asyncio.to_thread(check_docling)
    payload = {"database": db_status, "docling": docling_status}
    if not db_ok and db_status != "not_configured":
        payload["ready"] = False
        return JSONResponse(content=payload, status_code=503)
    payload["ready"] = True
    return JSONResponse(content=payload, status_code=200)


def _normalize_team_key(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


team_fields_map: dict[str, dict] = {}
for team in all_teams:
    raw_team_id = str(
        getattr(team, "id", None)
        or getattr(team, "team_id", None)
        or getattr(team, "name", "")
    )
    team_name = str(getattr(team, "name", ""))
    metadata = getattr(team, "metadata", None)
    description = getattr(team, "description", None)
    category = metadata.get("category") if isinstance(metadata, dict) else None

    fields: dict[str, str] = {}
    if isinstance(description, str) and description.strip():
        fields["description"] = description
    if isinstance(category, str) and category.strip():
        fields["category"] = category

    if fields:
        for key in {
            raw_team_id,
            team_name,
            _normalize_team_key(raw_team_id),
            _normalize_team_key(team_name),
        }:
            if key:
                team_fields_map[key] = fields


@app.middleware("http")
async def enrich_config_payload_with_category(request, call_next):
    response = await call_next(request)
    if request.url.path != "/config":
        return response

    try:
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        payload = json.loads(body.decode("utf-8"))
        teams = payload.get("teams")

        if isinstance(teams, list):
            enriched_teams = []
            for team_item in teams:
                if not isinstance(team_item, dict):
                    enriched_teams.append(team_item)
                    continue

                team_id = str(
                    team_item.get("id")
                    or team_item.get("team_id")
                    or team_item.get("name")
                    or ""
                )
                team_name = str(team_item.get("name") or "")
                source_fields = (
                    team_fields_map.get(team_id)
                    or team_fields_map.get(team_name)
                    or team_fields_map.get(_normalize_team_key(team_id))
                    or team_fields_map.get(_normalize_team_key(team_name))
                    or {}
                )

                enriched_item = dict(team_item)
                resolved_description = (
                    team_item.get("description")
                    or source_fields.get("description")
                )
                resolved_category = (
                    team_item.get("category")
                    or source_fields.get("category")
                )

                if isinstance(resolved_description, str) and resolved_description.strip():
                    enriched_item["description"] = resolved_description
                if isinstance(resolved_category, str) and resolved_category.strip():
                    enriched_item["category"] = resolved_category
                enriched_teams.append(enriched_item)

            payload["teams"] = enriched_teams

        json_response = JSONResponse(content=payload, status_code=response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in {"content-length", "content-type"}:
                json_response.headers[key] = value
        return json_response
    except Exception as e:
        logger.warning("Config payload enrichment failed: %s", e, exc_info=True)
        return response


# def _run_mcp_inspection() -> None:
#     """Run MCP tools inspection at module load (synchronous)."""
#     from agno_agents.mcp_tools_configuration import create_mcp_tools
#     import asyncio

#     logger.info("=" * 70)
#     logger.info("MCP TOOLS INSPECTION (at module load)")
#     logger.info("=" * 70)
#     try:
#         mcp_tools = create_mcp_tools()
#         if mcp_tools is None:
#             logger.info("MCP tools not created")
#             return
#         logger.info("MCP tools instance: %s", type(mcp_tools).__name__)
#         attrs = [a for a in dir(mcp_tools) if not a.startswith("_")]
#         logger.info("Public attributes: %s", attrs)
#         for attr in ("functions", "tools", "initialized", "server_params", "transport"):
#             if hasattr(mcp_tools, attr):
#                 val = getattr(mcp_tools, attr)
#                 logger.info("  .%s = %s: %s", attr, type(val).__name__, repr(val)[:200])
#         async def _inspect() -> None:
#             logger.info("-" * 70)
#             logger.info("Connecting to MCP server...")
#             async with mcp_tools:
#                 logger.info("CONNECTED. Inspecting mcp_tools.")
#                 for attr in dir(mcp_tools):
#                     if attr.startswith("__"):
#                         continue
#                     try:
#                         val = getattr(mcp_tools, attr)
#                         if callable(val):
#                             logger.info("  .%s() -> %s", attr, "async" if asyncio.iscoroutinefunction(val) else "method")
#                         else:
#                             logger.info("  .%s = %s", attr, repr(val)[:200])
#                     except Exception as e:
#                         logger.info("  .%s -> ERROR: %s", attr, e)
#         try:
#             loop = asyncio.get_running_loop()
#             asyncio.create_task(_inspect())
#         except RuntimeError:
#             asyncio.run(_inspect())
#     except Exception as e:
#         logger.error("MCP inspection failed: %s", e, exc_info=True)
#     logger.info("=" * 70)


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

    logger.info("\n" + "=" * 60)
    logger.info("Agno Agents - Global Agent OS")
    logger.info("=" * 60)
    logger.info("Available Agents (%s):", len(all_agents))
    logger.info("  1. Contract Compliance OS")
    logger.info("  2. RFP & Vendor Evaluation OS")
    logger.info("  3. Invoice Parsing Agent")
    logger.info("  4. Pricebook Management Agent")
    logger.info("  5. File Organiser Agent")
    logger.info("  RAG (ChromaDB): via Agentic RAG team only")
    logger.info("MCP Server: %s", SERVER_BASE_URL)
    logger.info("Server starting... (ENV=%s, reload=%s)", environment, use_reload)
    logger.info("AGUI endpoint: http://%s:%s/agui", host, port)
    logger.info("Status: http://%s:%s/status", host, port)
    logger.info("Config: http://%s:%s/config", host, port)
    logger.info("Press Ctrl+C to stop the server")
    logger.info("=" * 60 + "\n")

    log_mcp_tools_on_startup()

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

main.py
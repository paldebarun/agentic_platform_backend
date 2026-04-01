"""
Contract Compliance OS - Main Orchestration

Multi-agent system for contract compliance tracking and monitoring.
Uses Python-level orchestration pipeline instead of agent-as-tool pattern.
"""

from custom_tools.docling_tool import create_docling_tools
from custom_tools.image_retrieval_tool import create_image_retrieval_tools
from custom_tools.fetch_document_tool import get_document
from agno.agent import Agent
from agno.os.interfaces.agui import AGUI
from templates.agent_os_template import AGENT_OS
from app_config import get_model
from config import ORCHESTRATOR_INSTRUCTIONS
from utils.agno_db import get_agno_db
from workflow_pipeline import document_processing_workflow
from agno.tools.workflow import WorkflowTools
# from custom_tools.get_document_tool import get_document
from subagents.document_classifier_agent import (
    create_document_classifier_agent
)

from subagents.document_extraction_agent import (
    create_document_extraction_agent
)

from subagents.document_validation_agent import (
    create_document_validation_agent
)

# Create all specialized agents (for reference, but not used as tools)
# chunking_agent = create_chunking_agent()


document_classifier_agent=create_document_classifier_agent()
document_extraction_agent=create_document_extraction_agent()
document_validation_agent=create_document_validation_agent()
  



workflow_tools = WorkflowTools(  
    workflow=document_processing_workflow,  
    enable_think=True,  
    enable_analyze=True,  
    add_few_shot=True,  
    async_mode=True, 
     # Optional: provide examples  
)  

# Create Docling tools - will be None if Docling service is unavailable
docling_tools = create_docling_tools()

# Create image retrieval tools - will be None if PostgreSQL is unavailable
image_retrieval_tools = create_image_retrieval_tools()

tools_list = [
    workflow_tools,
    docling_tools,
    get_document,
]

if image_retrieval_tools:
    tools_list.extend(image_retrieval_tools)

tools_list = [t for t in tools_list if t is not None]



orchestrator_agent = Agent(
    name="Contract Compliance Query Interface",
    model=get_model("planner"),
    tools=tools_list,
    instructions=ORCHESTRATOR_INSTRUCTIONS,
    markdown=False,
    description="Multi-agent system for contract compliance tracking, SLA monitoring, obligation tracking, and risk assessment. This agent orchestrates the contract compliance analysis pipeline and provides query interface for compliance insights.",
    send_media_to_model=False,  # AGUI extracts text automatically
    db=get_agno_db(),
    add_history_to_context=True,
    cache_session=True,
)


# def _format_compliance_report(report: dict) -> str:
#     """Format compliance report for display"""
#     if report.get("status") == "error":
#         error_msg = f"Error occured while generating compliance report"
#         return error_msg
    
#     summary = report.get("summary", {})
#     analysis = report.get("compliance_analysis", {})
    
#     formatted = f"""
# **Contract Analysis Summary:**
# - Total Clauses: {summary.get('total_clauses', 0)}
# - Total Obligations: {summary.get('total_obligations', 0)}
# - Total SLAs: {summary.get('total_slas', 0)}
# - Total Penalties: {summary.get('total_penalties', 0)}

# **Compliance Status:**
# - Risk Score: {analysis.get('risk_score', 'N/A')}
# - Risk Level: {analysis.get('risk_level', 'N/A')}
# - Alerts: {len(analysis.get('alerts', []))}
# - Recommendations: {len(analysis.get('recommendations', []))}
# """
    
#     if analysis.get('alerts'):
#         formatted += "\n**Active Alerts:**\n"
#         for alert in analysis.get('alerts', [])[:5]:  # Show first 5
#             formatted += f"- {alert.get('title', 'Alert')}: {alert.get('description', '')[:100]}...\n"
    
#     if analysis.get('recommendations'):
#         formatted += "\n**Recommendations:**\n"
#         for rec in analysis.get('recommendations', [])[:5]:  # Show first 5
#             formatted += f"- {rec}\n"
    
#     return formatted


# Create AgentOS instance
# Only expose the orchestrator agent in the UI - sub-agents are used internally by the pipeline
contract_compliance_os = AGENT_OS(
    name="Document analyser OS",
    description="AI-driven document orchestration system that processes documents using tool-based pipelines, including text extraction, image analysis, and document classification. Designed for scalable, multi-modal document understanding and intelligent query handling.",
    agents=[orchestrator_agent],  # Only expose the main orchestrator agent
    interfaces=[AGUI(agent=orchestrator_agent)],

)


app = contract_compliance_os.get_app()
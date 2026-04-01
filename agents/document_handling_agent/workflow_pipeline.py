from agno.workflow import Workflow, Step
from agno.workflow.types import StepInput, StepOutput

from datetime import datetime
import json
from typing import Any

from utils.agno_db import get_agno_db

# Your agents
from .subagents.document_classifier_agent import (
    create_document_classifier_agent,
)

from .subagents.document_extraction_agent import (
    create_document_extraction_agent,
)

from .subagents.document_validation_agent import (
    create_document_validation_agent,
)


# -----------------------------
# Utility
# -----------------------------
def _to_json_serializable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_json_serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_serializable(v) for v in value]
    return value


# -----------------------------
# STEP 1: Classification
# -----------------------------
async def classification_step(step_input: StepInput) -> StepOutput:
    print("Classification Step Started")

    document_text = (
        step_input.input.get("input_data")
        if isinstance(step_input.input, dict)
        else step_input.input
    )

    if not document_text:
        raise RuntimeError("No document text provided")

    response_content = ""

    async for chunk in create_document_classifier_agent().arun(
        document_text, stream=True
    ):
        if hasattr(chunk, "content") and chunk.content:
            response_content += str(chunk.content)

    print(f"Classification response: {response_content}")

    parsed = json.loads(response_content)

    return StepOutput(content=parsed, success=True)


# -----------------------------
# STEP 2: Extraction
# -----------------------------
async def extraction_step(step_input: StepInput) -> StepOutput:
    print("Extraction Step Started")

    document_text = (
        step_input.input.get("input_data")
        if isinstance(step_input.input, dict)
        else step_input.input
    )

    classification = step_input.previous_step_outputs["classification_step"].content

    prompt = f"""
Document Type: {classification.get("document_type")}
Document Summary: {classification.get("summary")}

Document Text:
{document_text}
"""

    response_content = ""

    async for chunk in create_document_extraction_agent().arun(
        prompt, stream=True
    ):
        if hasattr(chunk, "content") and chunk.content:
            response_content += str(chunk.content)

    print(f"Extraction response: {response_content}")

    parsed = json.loads(response_content)

    return StepOutput(content=parsed, success=True)


# -----------------------------
# STEP 3: Validation
# -----------------------------
async def validation_step(step_input: StepInput) -> StepOutput:
    print("Validation Step Started")

    extracted_data = step_input.previous_step_outputs["extraction_step"].content

    prompt = f"""
Validate the following extracted document data:

{json.dumps(extracted_data, indent=2)}
"""

    response_content = ""

    async for chunk in create_document_validation_agent().arun(
        prompt, stream=True
    ):
        if hasattr(chunk, "content") and chunk.content:
            response_content += str(chunk.content)

    print(f"Validation response: {response_content}")

    parsed = json.loads(response_content)

    return StepOutput(content=parsed, success=True)


# -----------------------------
# STEP 4: Final Output
# -----------------------------
async def finalize_step(step_input: StepInput) -> StepOutput:
    print("Finalize Step Started")

    classification = step_input.previous_step_outputs["classification_step"].content
    extraction = step_input.previous_step_outputs["extraction_step"].content
    validation = step_input.previous_step_outputs["validation_step"].content

    final_output = {
        "document_type": classification.get("document_type"),
        "summary": classification.get("summary"),
        "extracted_data": extraction.get("extracted_fields"),
        "validation": validation,
        "metadata": {
            "processed_at": datetime.now().isoformat(),
            "pipeline": "document_processing_workflow",
        },
    }

    print(f"Final Output: {final_output}")

    return StepOutput(
        content=_to_json_serializable(final_output),
        success=True,
    )


# -----------------------------
# WORKFLOW
# -----------------------------
document_processing_workflow = Workflow(
    name="Document_Processing_Workflow",
    description="End-to-end document processing: classification → extraction → validation",
    steps=[
        Step(name="classification_step", executor=classification_step),
        Step(name="extraction_step", executor=extraction_step),
        Step(name="validation_step", executor=validation_step),
        Step(name="finalize_step", executor=finalize_step),
    ],
    stream_events=True,
    stream_executor_events=True,
    db=get_agno_db(),
)
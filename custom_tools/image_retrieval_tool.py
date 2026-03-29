"""
Image Retrieval Tool

Allows agents to retrieve base64 images from PostgreSQL database by image ID.
"""

import re
import json
import asyncio
from typing import Optional, List
import base64
from agno.tools import tool
from services.db_service import connection_scoped_client, POSTGRES_AVAILABLE
from gemini_adapter import GeminiModel



# =========================
# GLOBALS / CACHING
# =========================

_has_description_column: Optional[bool] = None


# def get_openai_client() -> AsyncOpenAI:
#     global _openai_client
#     if not _openai_client:
#         _openai_client = AsyncOpenAI(
#             api_key=OPENAI_API_KEY,
#             base_url=OPENAI_BASE_URL,
#         )
#     return _openai_client


def _ensure_image_description_column():
    """Ensure image_description column exists (called lazily)."""
    global _has_description_column

    if not POSTGRES_AVAILABLE:
        return False

    if _has_description_column is True:
        return True

    try:
        with connection_scoped_client() as client:
            result = client.execute_query(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='docling_images' AND column_name='image_description'
                """,
                fetch=True,
            )

            if not result:
                client.execute_query(
                    "ALTER TABLE docling_images ADD COLUMN image_description TEXT",
                    fetch=False,
                )
                client.commit()
                print("Added image_description column")

            _has_description_column = True
            return True

    except Exception as e:
        print(f"Failed to ensure column: {e}")
        return False


# =========================
# ASYNC DB WRAPPER
# =========================

async def run_db(fn):
    return await asyncio.to_thread(fn)


# =========================
# VISION API (GEMINI)
# =========================


_gemini_model: Optional[GeminiModel] = None


def get_gemini_model() -> GeminiModel:
    global _gemini_model
    if not _gemini_model:
        _gemini_model = GeminiModel("gemini-1.5-pro")
    return _gemini_model


async def _analyze_image_with_vision_api(base64_data: str, image_type: str) -> Optional[str]:
    try:
        model = get_gemini_model()

        # Gemini expects bytes or inline base64
        try:
            image_bytes = base64.b64decode(base64_data)
        except Exception:
            return None

        prompt = (
            "Analyze this image and provide a detailed description. "
            "Include text, charts, diagrams, and key insights."
        )

        # assuming your GeminiModel supports async call
        response = await model.generate(
    prompt=prompt,
    images=[image_bytes]
)

        if response:
            if isinstance(response, str):
                return response.strip()
            if hasattr(response, "text"):
                return response.text.strip()
            return str(response).strip()

        return None

    except Exception as e:
        print(f"Gemini vision error: {e}")
        return None


# =========================
# TOOLS
# =========================

@tool(name="get_image_description")
async def get_image_description(image_id: str) -> str:
    await run_db(_ensure_image_description_column)

    if not POSTGRES_AVAILABLE:
        return "PostgreSQL not available"

    def db_logic():
        with connection_scoped_client() as client:
            query = """
                SELECT image_id, image_type, source_file, created_at,
                       image_description, base64_data
                FROM docling_images
                WHERE image_id = %s
            """
            return client.execute_query(query, params=(image_id,), dict_cursor=True)

    results = await run_db(db_logic)

    if not results:
        return "Image not found"

    image = results[0]

    if image.get("image_description"):
        return json.dumps(image, default=str)

    if not image.get("base64_data"):
        return "No image data available"

    desc = await _analyze_image_with_vision_api(image["base64_data"], image["image_type"])

    if not desc:
        return "Vision analysis failed"

    async def update_db():
        def inner():
            with connection_scoped_client() as client:
                client.execute_query(
                    "UPDATE docling_images SET image_description=%s WHERE image_id=%s",
                    params=(desc, image_id),
                    fetch=False,
                )
                client.commit()

        return await run_db(inner)

    await update_db()

    image["image_description"] = desc
    return json.dumps(image, default=str)


@tool(name="get_image_by_id")
def get_image_by_id(image_id: str, include_base64: bool = False) -> str:
    _ensure_image_description_column()

    if not POSTGRES_AVAILABLE:
        return "PostgreSQL not available"

    with connection_scoped_client() as client:
        result = client.execute_query(
            """
            SELECT * FROM docling_images WHERE image_id = %s
            """,
            params=(image_id,),
            dict_cursor=True,
        )

    if not result:
        return "Image not found"

    data = result[0]

    if not include_base64:
        data.pop("base64_data", None)

    return json.dumps(data, default=str)


@tool(name="get_images_batch")
def get_images_batch(image_ids: List[str], include_base64: bool = False, max_total_size: int = 100000) -> str:
    _ensure_image_description_column()

    if not POSTGRES_AVAILABLE:
        return "PostgreSQL not available"

    if not image_ids:
        return "No image IDs provided"

    with connection_scoped_client() as client:
        placeholders = ",".join(["%s"] * len(image_ids))
        results = client.execute_query(
            f"""
            SELECT *, LENGTH(base64_data) as base64_length
            FROM docling_images
            WHERE image_id IN ({placeholders})
            """,
            params=tuple(image_ids),
            dict_cursor=True,
        )

    total_size = sum(r.get("base64_length") or 0 for r in results)

    if include_base64 and total_size > max_total_size:
        include_base64 = False

    for r in results:
        if not include_base64:
            r.pop("base64_data", None)

    return json.dumps(
        {
            "count": len(results),
            "total_size": total_size,
            "images": results,
        },
        default=str,
    )


@tool(name="list_image_ids_in_text")
def list_image_ids_in_text(text: str) -> str:
    pattern = r'\[\s*Image\s*:\s*([^\]\s]+)\s*\]'
    matches = re.findall(pattern, text, re.IGNORECASE)

    return json.dumps(
        {
            "count": len(set(matches)),
            "image_ids": list(set(matches)),
        }
    )


@tool(name="get_images_by_text_and_source_file")
def get_images_by_text_and_source_file(text: str, source_file: str) -> str:
    pattern = r'\[\s*Image\s*:\s*([^\]\s]+)\s*\]'
    ids = list(set(re.findall(pattern, text, re.IGNORECASE)))

    if not ids:
        return json.dumps({"image_ids": []})

    with connection_scoped_client() as client:
        placeholders = ",".join(["%s"] * len(ids))
        results = client.execute_query(
            f"""
            SELECT image_id FROM docling_images
            WHERE image_id IN ({placeholders}) AND source_file = %s
            """,
            params=tuple(ids) + (source_file,),
            dict_cursor=True,
        )

    return json.dumps([r["image_id"] for r in results])


# =========================
# FACTORY
# =========================

def create_image_retrieval_tools() -> Optional[List]:
    if not POSTGRES_AVAILABLE:
        print("Postgres unavailable")
        return None

    return [
        get_image_description,
        get_image_by_id,
        get_images_batch,
        list_image_ids_in_text,
        get_images_by_text_and_source_file,
    ]
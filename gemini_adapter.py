import asyncio
import os
from typing import Any, List, Optional

from google import genai
from google.genai import types


class GeminiModel:
    def __init__(self, model_name: str):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

    async def generate(self, prompt: str, images: Optional[List[bytes]] = None) -> str:
        def _run() -> str:
            contents: List[Any] = [prompt]
            if images:
                for image_bytes in images:
                    contents.append(
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/png",
                        )
                    )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
            )
            return (response.text or "").strip()

        return await asyncio.to_thread(_run)

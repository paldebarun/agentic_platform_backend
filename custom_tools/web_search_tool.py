import os
from typing import Optional

from agno.tools import tool
from tavily import TavilyClient
from app_config import TAVILY_API_KEY


def _get_tavily_client() -> Optional[TavilyClient]:
    if not TAVILY_API_KEY:
        print("TAVILY_API_KEY not set")
        return None
    return TavilyClient(api_key=TAVILY_API_KEY)


@tool(
    name="web_search_tool",
    instructions="""
Use this tool to perform web searches for research or up-to-date information by generating a relevant query and returning 3–5 high-quality, authoritative, and directly relevant URLs.
"""
)
async def search_web(query: str, num_results: int = 5) -> str:
    """
    Search the web using Tavily and return structured results.
    """

    client = _get_tavily_client()
    if not client:
        return "Search service unavailable"

    try:
        response = client.search(
            query=query,
            max_results=num_results
        )

        results = response.get("results", [])

        if not results:
            return "No results found"

        formatted_results = []

        for idx, r in enumerate(results, start=1):
            title = r.get("title", "No title")
            url = r.get("url", "")
            content = r.get("content", "")

            formatted_results.append(
                f"[Result {idx}]\n"
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Snippet: {content}\n"
            )

        return "\n\n".join(formatted_results)

    except Exception as e:
        print(f"Search error: {e}")
        return "Search failed"
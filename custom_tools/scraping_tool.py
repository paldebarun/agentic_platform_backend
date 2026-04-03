import asyncio
from typing import List

from agno.tools import tool

from services.crawl_service import CrawlerService  


@tool(
    name="scraping_tool",
    instructions="Use this tool to scrape and extract markdown content from a list of URLs (depth=2) for research and analysis."
)
async def crawl_websites(urls: List[str], depth: int = 2) -> str:
    """
    Crawl multiple URLs up to a given depth and return markdown content for each.
    """

    if not urls:
        return "No URLs provided"

    crawler_service = CrawlerService()

    all_results = []

    try:
        # Crawl each URL sequentially (safe for rate limits)
        for url in urls:
            try:
                crawl_response = await crawler_service.recursive_crawl_with_task(
                    start_url=url,
                    max_depth=depth
                )

                # Extract markdown reports
                for item in crawl_response.results:
                    markdown = item.get("report", "")
                    if markdown:
                        all_results.append({
                            "url": item.get("metadata", {}).get("url", url),
                            "markdown": markdown
                        })

            except Exception as e:
                print(f"Error crawling {url}: {e}")
                continue

        if not all_results:
            return "No content extracted"

        # Convert to string format (LLM-friendly)
        formatted_output = []

        for idx, item in enumerate(all_results, start=1):
            formatted_output.append(
                f"[Document {idx}]\n"
                f"URL: {item['url']}\n"
                f"Content:\n{item['markdown']}\n"
            )

        return "\n\n".join(formatted_output)

    except Exception as e:
        print(f"Crawl tool error: {e}")
        return "Crawling failed"
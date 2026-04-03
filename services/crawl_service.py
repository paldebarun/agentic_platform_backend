from collections import deque
from typing import Dict, List
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler


class CrawlerService:

    async def crawl_url(self, crawler, url: str) -> Dict:
        """
        Crawl a single URL and return cleaned result.
        """
        result = await crawler.arun(url=url, bypass_cache=True)

        # Clean metadata
        metadata = {k: v or "" for k, v in (result.metadata or {}).items()}

        # Filter valid links
        links = {"internal": [], "external": []}
        if result.links:
            for link_type in ["internal", "external"]:
                links[link_type] = [
                    l for l in result.links.get(link_type, [])
                    if l.get("href") and l["href"].startswith(("http://", "https://"))
                ]

        return {
            "url": result.url,
            "markdown": result.markdown,
            "metadata": metadata,
            "links": links
        }

    async def recursive_crawl(self, start_url: str, max_depth: int = 2) -> List[Dict]:
        """
        Crawl a website recursively up to a given depth.
        Returns list of pages with markdown.
        """
        visited = set()
        queue = deque([(start_url, 0)])
        results = []

        async with AsyncWebCrawler(verbose=False) as crawler:
            while queue:
                current_url, depth = queue.popleft()

                if current_url in visited or depth > max_depth:
                    continue

                visited.add(current_url)

                try:
                    page = await self.crawl_url(crawler, current_url)
                    results.append(page)

                    # Add internal links for next depth
                    for link in page["links"]["internal"]:
                        href = link.get("href")
                        if (
                            href
                            and self._is_internal_link(href, start_url)
                            and href not in visited
                        ):
                            queue.append((href, depth + 1))

                except Exception:
                    continue

        return results

    def _is_internal_link(self, link: str, base_url: str) -> bool:
        return urlparse(link).netloc == urlparse(base_url).netloc
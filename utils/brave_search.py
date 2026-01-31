# This project was developed with assistance from AI tools.
"""
Brave Search API client for web search.

Provides access to:
- Web search with rich results
- News search
- Image search (if enabled)

API Documentation: https://brave.com/search/api/
"""
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from config import config

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SearchResult:
    """Individual web search result."""
    title: str
    url: str
    description: str
    age: str | None = None  # e.g., "2 hours ago"
    
    def format_line(self) -> str:
        """Format as a single result entry."""
        lines = [f"**{self.title}**"]
        if self.age:
            lines[0] += f" ({self.age})"
        lines.append(f"  {self.url}")
        if self.description:
            # Truncate long descriptions
            desc = self.description[:200] + "..." if len(self.description) > 200 else self.description
            lines.append(f"  {desc}")
        return "\n".join(lines)


@dataclass
class SearchResponse:
    """Web search response with results."""
    query: str
    total_results: int | None
    results: list[SearchResult]
    
    def format_display(self) -> str:
        """Format search results for chat display."""
        if not self.results:
            return f"No results found for: {self.query}"
        
        count_str = f"About {self.total_results:,} results" if self.total_results else f"{len(self.results)} results"
        lines = [f"Web search results for \"{self.query}\" ({count_str}):\n"]
        
        for i, result in enumerate(self.results, 1):
            lines.append(f"{i}. {result.format_line()}")
            lines.append("")  # Empty line between results
        
        return "\n".join(lines).rstrip()


# =============================================================================
# API Client
# =============================================================================

class BraveSearchClient:
    """Client for Brave Search API."""
    
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """
        Initialize Brave Search client.
        
        Args:
            api_key: Brave Search API key (defaults to config)
            base_url: API base URL (defaults to config)
        """
        self.api_key = api_key or config.BRAVE_SEARCH_API_KEY
        self.base_url = (base_url or config.BRAVE_SEARCH_BASE_URL).rstrip("/")
        
        if not self.api_key:
            raise ValueError("Brave Search API key is required")
        
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-Subscription-Token": self.api_key,
                "Accept": "application/json",
            },
            timeout=30.0,
        )
    
    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make an API request."""
        try:
            response = self._client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Brave Search API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Brave Search request failed: {e}")
            raise
    
    def search(
        self,
        query: str,
        count: int = 5,
        freshness: str | None = None,
        safesearch: str = "moderate",
    ) -> SearchResponse:
        """
        Search the web.
        
        Args:
            query: Search query
            count: Number of results (1-20, default 5)
            freshness: Filter by age - "pd" (past day), "pw" (past week), 
                      "pm" (past month), "py" (past year), or None for any
            safesearch: Content filter - "off", "moderate", or "strict"
            
        Returns:
            SearchResponse with results
        """
        params = {
            "q": query,
            "count": min(max(count, 1), 20),  # Clamp to 1-20
            "safesearch": safesearch,
        }
        
        if freshness:
            params["freshness"] = freshness
        
        result = self._request("/web/search", params)
        return self._parse_search_response(query, result)
    
    def _parse_search_response(self, query: str, result: dict) -> SearchResponse:
        """Parse search API response."""
        web = result.get("web", {})
        raw_results = web.get("results", [])
        
        results = []
        for item in raw_results:
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
                age=item.get("age"),
            ))
        
        return SearchResponse(
            query=query,
            total_results=web.get("totalResults"),
            results=results,
        )
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# =============================================================================
# Module-level functions
# =============================================================================

def is_available() -> bool:
    """Check if Brave Search API is configured and available."""
    return bool(config.BRAVE_SEARCH_API_KEY)


# Singleton instance
_client: BraveSearchClient | None = None


def get_brave_search_client() -> BraveSearchClient:
    """
    Get or create the singleton Brave Search client.
    
    Raises:
        ValueError: If API key is not configured
    """
    global _client
    if _client is None:
        if not is_available():
            raise ValueError("Brave Search API key not configured")
        _client = BraveSearchClient()
    return _client

# This project was developed with assistance from AI tools.
"""Web search tool - Brave Search integration."""
import logging

from langchain_core.tools import tool

from prompts import TOOL_WEB_SEARCH
from utils.brave_search import get_brave_search_client

from . import ToolContext

logger = logging.getLogger(__name__)


def create_tools(context: ToolContext) -> list:
    """Create web search tools."""
    
    @tool(description=TOOL_WEB_SEARCH)
    def web_search(query: str, count: int = 5, freshness: str | None = None) -> str:
        """Search the web for current information."""
        try:
            client = get_brave_search_client()
            result = client.search(query=query, count=count, freshness=freshness)
            return result.format_display()
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return f"Unable to perform web search: {str(e)}"
    
    return [web_search]

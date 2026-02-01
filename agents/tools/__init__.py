# This project was developed with assistance from AI tools.
"""
Chat agent tools module.

Tools are organized by domain and conditionally loaded based on configuration.
Each tool module provides a `create_tools(context)` function that returns
a list of LangChain tools.
"""
from dataclasses import dataclass
from typing import Callable

from config import config


@dataclass
class ToolContext:
    """
    Context passed to tool factories for accessing agent state and services.
    
    This allows tools to access user-specific data without coupling
    to the ChatAgent class directly.
    """
    # User identification
    get_user_id: Callable[[], str | None]
    get_thread_id: Callable[[], str | None]
    
    # Service accessors (lazy-loaded)
    get_rag_manager: Callable[[], object | None]
    get_facts_store: Callable[[], object | None]
    get_conversation_memory: Callable[[], object | None]
    
    # Download state (for report downloads)
    set_pending_download: Callable[[dict], None]


def get_all_tools(context: ToolContext, anonymous: bool = False) -> list:
    """
    Get all available tools based on configuration and authentication state.
    
    Args:
        context: Tool context for accessing agent state
        anonymous: If True, only include public tools (no user-specific tools)
        
    Returns:
        List of LangChain tools
    """
    tools = []
    
    # Knowledge base - always available
    from .knowledge import create_tools as create_knowledge_tools
    tools.extend(create_knowledge_tools(context))
    
    # User-specific tools - authenticated only
    if not anonymous:
        from .memory import create_tools as create_memory_tools
        from .documents import create_tools as create_document_tools
        tools.extend(create_memory_tools(context))
        tools.extend(create_document_tools(context))
    
    # Property tools - when BatchData API configured
    from utils.batchdata import is_available as batchdata_available
    if batchdata_available():
        from .property import create_tools as create_property_tools
        tools.extend(create_property_tools(context))
    
    # Web search - when Brave API configured
    from utils.brave_search import is_available as brave_available
    if brave_available():
        from .search import create_tools as create_search_tools
        tools.extend(create_search_tools(context))
    
    # Economic data - when FRED API configured
    from utils.fred import is_available as fred_available
    if fred_available():
        from .economic import create_tools as create_economic_tools
        tools.extend(create_economic_tools(context))
    
    return tools

# This project was developed with assistance from AI tools.
"""Economic data tools - FRED (Federal Reserve Economic Data) integration."""
import logging

from langchain_core.tools import tool

from prompts import TOOL_FRED_GET_SERIES, TOOL_FRED_MORTGAGE_RATES, TOOL_FRED_SEARCH
from utils.fred import get_fred_client

from . import ToolContext

logger = logging.getLogger(__name__)


def create_tools(context: ToolContext) -> list:
    """Create economic data tools."""
    
    @tool(description=TOOL_FRED_GET_SERIES)
    def fred_get_series(
        series_id: str,
        limit: int = 1,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Get economic data from FRED."""
        try:
            client = get_fred_client()
            if limit == 1 and not start_date and not end_date:
                result = client.get_latest_value(series_id)
                if result:
                    return result.format_latest()
                return f"No data found for series {series_id}."
            else:
                result = client.get_observations(
                    series_id,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )
                if result:
                    return result.format_display()
                return f"No data found for series {series_id}."
        except Exception as e:
            logger.warning(f"FRED get_series failed: {e}")
            return f"Unable to retrieve economic data: {str(e)}"
    
    @tool(description=TOOL_FRED_SEARCH)
    def fred_search_series(search_text: str, limit: int = 5) -> str:
        """Search for FRED economic data series."""
        try:
            client = get_fred_client()
            result = client.search_series(search_text, limit=limit)
            return result.format_display()
        except Exception as e:
            logger.warning(f"FRED search failed: {e}")
            return f"Unable to search economic data series: {str(e)}"
    
    @tool(description=TOOL_FRED_MORTGAGE_RATES)
    def fred_mortgage_rates() -> str:
        """Get current mortgage interest rates from FRED."""
        try:
            client = get_fred_client()
            return client.get_mortgage_rates()
        except Exception as e:
            logger.warning(f"FRED mortgage rates failed: {e}")
            return f"Unable to retrieve mortgage rates: {str(e)}"
    
    return [fred_get_series, fred_search_series, fred_mortgage_rates]

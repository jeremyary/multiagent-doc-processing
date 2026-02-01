# This project was developed with assistance from AI tools.
"""Property data tools - BatchData.io integration."""
import logging

from langchain_core.tools import tool

from prompts import (
    TOOL_GEOCODE_ADDRESS,
    TOOL_PROPERTY_LOOKUP,
    TOOL_SEARCH_PROPERTIES,
    TOOL_VERIFY_ADDRESS,
)
from utils.batchdata import get_batchdata_client

from . import ToolContext

logger = logging.getLogger(__name__)


def create_tools(context: ToolContext) -> list:
    """Create property data tools."""
    
    @tool(description=TOOL_VERIFY_ADDRESS)
    def verify_property_address(street: str, city: str, state: str, zip_code: str) -> str:
        """Verify and standardize a property address."""
        try:
            client = get_batchdata_client()
            result = client.verify_address(street, city, state, zip_code)
            if result and result.is_valid:
                return result.format_display()
            return "Address could not be verified."
        except Exception as e:
            logger.warning(f"Address verification failed: {e}")
            return f"Unable to verify address: {str(e)}"
    
    @tool(description=TOOL_PROPERTY_LOOKUP)
    def get_property_details(street: str, city: str, state: str, zip_code: str | None = None) -> str:
        """Get detailed property information for a specific address."""
        try:
            client = get_batchdata_client()
            result = client.lookup_property(street, city, state, zip_code)
            if result:
                return result.format_display()
            return "No property data found for this address."
        except Exception as e:
            logger.warning(f"Property lookup failed: {e}")
            return f"Unable to retrieve property details: {str(e)}"
    
    @tool(description=TOOL_SEARCH_PROPERTIES)
    def search_properties(
        query: str | None = None,
        city: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        property_type: str | None = None,
        min_beds: int | None = None,
        max_beds: int | None = None,
        limit: int = 10,
    ) -> str:
        """Search for properties matching specific criteria."""
        if not any([query, city, state, zip_code]):
            return "Please provide a location query, city/state, or ZIP code to search."
        
        try:
            client = get_batchdata_client()
            results = client.search_properties(
                query=query,
                city=city,
                state=state,
                zip_code=zip_code,
                min_price=min_price,
                max_price=max_price,
                property_type=property_type,
                min_beds=min_beds,
                max_beds=max_beds,
                limit=limit,
            )
            if not results:
                return "No properties found matching your criteria."
            
            lines = [f"Found {len(results)} properties:"]
            for i, prop in enumerate(results, 1):
                lines.append(f"{i}. {prop.format_line()}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Property search failed: {e}")
            return f"Unable to search properties: {str(e)}"
    
    @tool(description=TOOL_GEOCODE_ADDRESS)
    def geocode_address(address: str) -> str:
        """Convert an address to geographic coordinates."""
        try:
            client = get_batchdata_client()
            result = client.geocode_address(address)
            if result:
                return result.format_display()
            return "Could not geocode this address."
        except Exception as e:
            logger.warning(f"Geocoding failed: {e}")
            return f"Unable to geocode address: {str(e)}"
    
    return [verify_property_address, get_property_details, search_properties, geocode_address]

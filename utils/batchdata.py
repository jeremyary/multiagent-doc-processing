# This project was developed with assistance from AI tools.
"""
BatchData.io API client for property and address data.

Provides access to:
- Address verification (USPS standardization)
- Property lookup (details, valuation, history)
- Comparable property search
- Geocoding

API Documentation: https://developer.batchdata.com/docs
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
class VerifiedAddress:
    """Verified and standardized address."""
    street: str
    city: str
    state: str
    zip_code: str
    zip_plus4: str | None = None
    county: str | None = None
    is_valid: bool = False
    
    def format_display(self) -> str:
        """Format address for chat display."""
        full_zip = f"{self.zip_code}-{self.zip_plus4}" if self.zip_plus4 else self.zip_code
        result = f"Address verified: {self.street}, {self.city}, {self.state} {full_zip}"
        if self.county:
            result += f" (County: {self.county})"
        return result


@dataclass
class GeocodedAddress:
    """Geocoded address with coordinates."""
    full_address: str
    latitude: float
    longitude: float
    accuracy: str | None = None
    
    def format_display(self) -> str:
        """Format geocode result for chat display."""
        lines = [
            f"Coordinates for {self.full_address}:",
            f"  Latitude: {self.latitude}",
            f"  Longitude: {self.longitude}",
        ]
        if self.accuracy:
            lines.append(f"  Accuracy: {self.accuracy}")
        return "\n".join(lines)


@dataclass
class PropertyDetails:
    """Detailed property information."""
    street: str
    city: str
    state: str
    zip_code: str | None = None
    beds: int | None = None
    baths: float | None = None
    building_sqft: int | None = None
    lot_sqft: int | None = None
    year_built: int | None = None
    estimated_value: int | None = None
    equity_percent: float | None = None
    last_sale_price: int | None = None
    last_sale_date: str | None = None
    owner_name: str | None = None
    
    def format_display(self) -> str:
        """Format property details for chat display."""
        addr = f"{self.street}, {self.city}, {self.state}"
        if self.zip_code:
            addr += f" {self.zip_code}"
        
        lines = [f"Property: {addr}"]
        
        if self.beds is not None:
            lines.append(f"  Beds: {self.beds}")
        if self.baths is not None:
            lines.append(f"  Baths: {self.baths}")
        
        if self.building_sqft:
            lines.append(f"  Building Sq Ft: {self.building_sqft:,}")
        else:
            lines.append("  Building Sq Ft: Not available")
        
        if self.year_built:
            lines.append(f"  Year Built: {self.year_built}")
        
        if self.lot_sqft:
            lines.append(f"  Lot Size: {self.lot_sqft:,} sqft")
        
        if self.estimated_value:
            lines.append(f"  Estimated Value: ${self.estimated_value:,}")
        
        if self.equity_percent is not None:
            lines.append(f"  Equity: {self.equity_percent:.1f}%")
        
        if self.last_sale_price and self.last_sale_date:
            lines.append(f"  Last Sale: ${self.last_sale_price:,} ({self.last_sale_date})")
        
        if self.owner_name:
            lines.append(f"  Owner: {self.owner_name}")
        
        return "\n".join(lines)


@dataclass
class PropertySummary:
    """Summary property info for search results."""
    street: str
    city: str
    state: str
    zip_code: str | None = None
    beds: int | None = None
    baths: float | None = None
    building_sqft: int | None = None
    year_built: int | None = None
    estimated_value: int | None = None
    
    def format_line(self) -> str:
        """Format as single-line summary."""
        addr = f"{self.street}, {self.city}, {self.state}"
        if self.zip_code:
            addr += f" {self.zip_code}"
        
        details = []
        if self.beds is not None:
            details.append(f"{self.beds} bed")
        if self.baths is not None:
            details.append(f"{self.baths} bath")
        if self.building_sqft:
            details.append(f"{self.building_sqft:,} sqft")
        if self.year_built:
            details.append(f"Built {self.year_built}")
        
        price = f"${self.estimated_value:,}" if self.estimated_value else "N/A"
        
        detail_str = " / ".join(details) if details else "No details"
        return f"{addr}\n   {detail_str} - {price}"


# =============================================================================
# API Client
# =============================================================================

class BatchDataClient:
    """Client for BatchData.io property data API."""
    
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """
        Initialize BatchData client.
        
        Args:
            api_key: BatchData API key (defaults to config)
            base_url: API base URL (defaults to config)
        """
        self.api_key = api_key or config.BATCHDATA_API_KEY
        self.base_url = (base_url or config.BATCHDATA_BASE_URL).rstrip("/")
        
        if not self.api_key:
            raise ValueError("BatchData API key is required")
        
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make an API request."""
        try:
            response = self._client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"BatchData API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"BatchData request failed: {e}")
            raise
    
    # =========================================================================
    # High-level methods (return parsed models)
    # =========================================================================
    
    def verify_address(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str,
    ) -> VerifiedAddress | None:
        """
        Verify and standardize an address using USPS standards.
        
        Returns:
            VerifiedAddress object or None if verification failed
        """
        result = self._request(
            "POST",
            "/address/verify",
            json={
                "requests": [{
                    "street": street,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                }]
            }
        )
        return self._parse_verified_address(result)
    
    def lookup_property(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: str | None = None,
    ) -> PropertyDetails | None:
        """
        Get detailed property information by address.
        
        Returns:
            PropertyDetails object or None if not found
        """
        address_query = f"{street}, {city}, {state}"
        if zip_code:
            address_query += f" {zip_code}"
        
        result = self._request(
            "POST",
            "/property/search",
            json={
                "searchCriteria": {"query": address_query},
                "options": {"skip": 0, "take": 1},
            }
        )
        
        properties = self._parse_property_list(result)
        if not properties:
            return None
        
        # Convert summary to full details
        prop = properties[0]
        return PropertyDetails(
            street=prop.street,
            city=prop.city,
            state=prop.state,
            zip_code=prop.zip_code,
            beds=prop.beds,
            baths=prop.baths,
            building_sqft=prop.building_sqft,
            year_built=prop.year_built,
            estimated_value=prop.estimated_value,
            # These fields come from the raw response, need to extract separately
            **self._extract_extra_property_details(result)
        )
    
    def search_properties(
        self,
        query: str | None = None,
        city: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        property_type: str | None = None,
        min_beds: int | None = None,
        max_beds: int | None = None,
        min_sqft: int | None = None,
        max_sqft: int | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> list[PropertySummary]:
        """
        Search for properties matching criteria.
        
        Returns:
            List of PropertySummary objects
        """
        search_criteria: dict[str, Any] = {}
        
        # Location query
        if query:
            search_criteria["query"] = query
        elif city and state:
            search_criteria["query"] = f"{city}, {state}"
        elif zip_code:
            search_criteria["query"] = zip_code
        
        # Valuation filters
        if min_price is not None or max_price is not None:
            search_criteria["valuation"] = {"estimatedValue": {}}
            if min_price is not None:
                search_criteria["valuation"]["estimatedValue"]["min"] = min_price
            if max_price is not None:
                search_criteria["valuation"]["estimatedValue"]["max"] = max_price
        
        # Property type
        if property_type:
            search_criteria["propertyType"] = property_type
        
        # Bedroom filters
        if min_beds is not None or max_beds is not None:
            search_criteria["bedrooms"] = {}
            if min_beds is not None:
                search_criteria["bedrooms"]["min"] = min_beds
            if max_beds is not None:
                search_criteria["bedrooms"]["max"] = max_beds
        
        # Square footage filters
        if min_sqft is not None or max_sqft is not None:
            search_criteria["buildingSqft"] = {}
            if min_sqft is not None:
                search_criteria["buildingSqft"]["min"] = min_sqft
            if max_sqft is not None:
                search_criteria["buildingSqft"]["max"] = max_sqft
        
        result = self._request("POST", "/property/search", json={
            "searchCriteria": search_criteria,
            "options": {"skip": skip, "take": limit},
        })
        
        return self._parse_property_list(result)
    
    def geocode_address(self, address: str) -> GeocodedAddress | None:
        """
        Convert an address to latitude/longitude coordinates.
        
        Returns:
            GeocodedAddress object or None if geocoding failed
        """
        result = self._request(
            "POST",
            "/address/geocode",
            json={"requests": [{"address": address}]}
        )
        return self._parse_geocoded_address(result)
    
    # =========================================================================
    # Response parsing methods
    # =========================================================================
    
    def _parse_verified_address(self, result: dict) -> VerifiedAddress | None:
        """Parse address verification response."""
        addresses = result.get("results", {}).get("addresses", [])
        if not addresses:
            return None
        
        addr = addresses[0]
        meta = addr.get("meta", {})
        is_valid = meta.get("verified") or addr.get("addressValidity") == "Valid"
        
        return VerifiedAddress(
            street=addr.get("street", ""),
            city=addr.get("city", ""),
            state=addr.get("state", ""),
            zip_code=addr.get("zip", ""),
            zip_plus4=addr.get("zipPlus4"),
            county=addr.get("county"),
            is_valid=is_valid,
        )
    
    def _parse_geocoded_address(self, result: dict) -> GeocodedAddress | None:
        """Parse geocode response."""
        # Note: BatchData uses "result" not "results" for geocode
        addresses = result.get("result", {}).get("addresses", [])
        if not addresses:
            return None
        
        geo = addresses[0]
        lat = geo.get("latitude")
        lng = geo.get("longitude")
        
        if lat is None or lng is None:
            return None
        
        return GeocodedAddress(
            full_address=geo.get("fullAddress", ""),
            latitude=lat,
            longitude=lng,
            accuracy=geo.get("geoStatus"),
        )
    
    def _parse_property_list(self, result: dict) -> list[PropertySummary]:
        """Parse property search response into list of summaries."""
        properties = result.get("results", {}).get("properties", [])
        parsed = []
        
        for prop in properties:
            addr = prop.get("address", {})
            listing = prop.get("listing", {})
            valuation = prop.get("valuation", {})
            
            parsed.append(PropertySummary(
                street=addr.get("street", ""),
                city=addr.get("city", ""),
                state=addr.get("state", ""),
                zip_code=addr.get("zip"),
                beds=listing.get("bedroomCount"),
                baths=listing.get("bathroomCount"),
                building_sqft=listing.get("buildingSqft") or listing.get("livingArea"),
                year_built=listing.get("yearBuilt"),
                estimated_value=valuation.get("estimatedValue"),
            ))
        
        return parsed
    
    def _extract_extra_property_details(self, result: dict) -> dict[str, Any]:
        """Extract additional property details not in PropertySummary."""
        properties = result.get("results", {}).get("properties", [])
        if not properties:
            return {}
        
        prop = properties[0]
        listing = prop.get("listing", {})
        valuation = prop.get("valuation", {})
        deed_history = prop.get("deedHistory", [])
        owner = prop.get("owner", {})
        
        extra = {
            "lot_sqft": listing.get("lotSizeSquareFeet"),
            "equity_percent": valuation.get("equityPercent"),
            "owner_name": owner.get("fullName"),
        }
        
        # Last sale from deed history
        if deed_history:
            last_sale = deed_history[-1]
            extra["last_sale_price"] = last_sale.get("salePrice")
            sale_date = last_sale.get("saleDate") or last_sale.get("recordingDate") or ""
            extra["last_sale_date"] = sale_date[:10] if sale_date else None
        
        return extra
    
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
    """Check if BatchData API is configured and available."""
    return bool(config.BATCHDATA_API_KEY)


# Singleton instance
_client: BatchDataClient | None = None


def get_batchdata_client() -> BatchDataClient:
    """
    Get or create the singleton BatchData client.
    
    Raises:
        ValueError: If API key is not configured
    """
    global _client
    if _client is None:
        if not is_available():
            raise ValueError("BatchData API key not configured")
        _client = BatchDataClient()
    return _client

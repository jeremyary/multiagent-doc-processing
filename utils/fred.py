# This project was developed with assistance from AI tools.
"""
FRED API client for Federal Reserve Economic Data.

Provides access to economic data series including:
- Mortgage interest rates (30-year, 15-year)
- Federal Funds Rate
- Housing data (starts, permits, prices)
- Inflation (CPI) and unemployment data

API Documentation: https://fred.stlouisfed.org/docs/api/fred/
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from config import config

logger = logging.getLogger(__name__)


# =============================================================================
# Common Series IDs (for reference and convenience)
# =============================================================================
SERIES_MORTGAGE_30Y = "MORTGAGE30US"  # 30-Year Fixed Rate Mortgage Average
SERIES_MORTGAGE_15Y = "MORTGAGE15US"  # 15-Year Fixed Rate Mortgage Average
SERIES_FED_FUNDS = "FEDFUNDS"  # Federal Funds Rate
SERIES_PRIME_RATE = "DPRIME"  # Bank Prime Loan Rate
SERIES_CPI = "CPIAUCSL"  # Consumer Price Index (Inflation)
SERIES_UNEMPLOYMENT = "UNRATE"  # Unemployment Rate
SERIES_HOUSING_STARTS = "HOUST"  # Housing Starts
SERIES_CASE_SHILLER = "CSUSHPISA"  # Case-Shiller Home Price Index
SERIES_MEDIAN_HOME_PRICE = "MSPUS"  # Median Sales Price of Houses Sold


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class SeriesInfo:
    """Information about a FRED data series."""
    id: str
    title: str
    frequency: str
    units: str
    seasonal_adjustment: str | None = None
    last_updated: str | None = None
    notes: str | None = None
    
    def format_line(self) -> str:
        """Format as a single-line summary."""
        return f"**{self.id}**: {self.title} ({self.frequency}, {self.units})"
    
    def format_display(self) -> str:
        """Format for detailed display."""
        lines = [
            f"**{self.title}**",
            f"  Series ID: {self.id}",
            f"  Frequency: {self.frequency}",
            f"  Units: {self.units}",
        ]
        if self.seasonal_adjustment:
            lines.append(f"  Seasonal Adjustment: {self.seasonal_adjustment}")
        if self.last_updated:
            lines.append(f"  Last Updated: {self.last_updated}")
        if self.notes:
            # Truncate long notes
            notes = self.notes[:200] + "..." if len(self.notes) > 200 else self.notes
            lines.append(f"  Notes: {notes}")
        return "\n".join(lines)


@dataclass
class Observation:
    """A single data observation."""
    date: str
    value: float | None
    
    def format_line(self) -> str:
        """Format as date: value."""
        if self.value is None:
            return f"{self.date}: N/A"
        return f"{self.date}: {self.value:,.2f}"


@dataclass
class SeriesObservations:
    """Series data with observations."""
    series_id: str
    title: str
    units: str
    observations: list[Observation]
    
    def format_display(self) -> str:
        """Format observations for display."""
        if not self.observations:
            return f"No observations available for {self.series_id}."
        
        lines = [f"**{self.title}** ({self.series_id})"]
        lines.append(f"Units: {self.units}\n")
        
        # Show observations
        for obs in self.observations:
            lines.append(f"  {obs.format_line()}")
        
        return "\n".join(lines)
    
    @property
    def latest(self) -> Observation | None:
        """Get the most recent observation."""
        if not self.observations:
            return None
        return self.observations[-1]
    
    def format_latest(self) -> str:
        """Format just the latest value."""
        if not self.observations:
            return f"No data available for {self.series_id}."
        
        latest = self.observations[-1]
        if latest.value is None:
            return f"{self.title}: Data not available"
        return f"{self.title}: {latest.value:,.2f} {self.units} (as of {latest.date})"


@dataclass
class SearchResult:
    """A series search result."""
    series: list[SeriesInfo]
    total_count: int
    
    def format_display(self) -> str:
        """Format search results for display."""
        if not self.series:
            return "No series found matching your search."
        
        lines = [f"Found {self.total_count} series (showing {len(self.series)}):\n"]
        for i, s in enumerate(self.series, 1):
            lines.append(f"{i}. {s.format_line()}")
        
        return "\n".join(lines)


# =============================================================================
# API Client
# =============================================================================

class FREDClient:
    """Client for the FRED API."""
    
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """
        Initialize FRED client.
        
        Args:
            api_key: FRED API key (defaults to config)
            base_url: API base URL (defaults to config)
        """
        self.api_key = api_key or config.FRED_API_KEY
        self.base_url = (base_url or config.FRED_BASE_URL).rstrip("/")
        
        if not self.api_key:
            raise ValueError("FRED API key is required")
        
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=30.0,
        )
    
    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make an API request."""
        params = params or {}
        params["api_key"] = self.api_key
        params["file_type"] = "json"
        
        try:
            response = self._client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"FRED API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"FRED request failed: {e}")
            raise
    
    def get_series(self, series_id: str) -> SeriesInfo | None:
        """
        Get information about a data series.
        
        Args:
            series_id: The FRED series ID (e.g., "MORTGAGE30US")
            
        Returns:
            SeriesInfo or None if not found
        """
        try:
            result = self._request("/series", {"series_id": series_id})
            seriess = result.get("seriess", [])
            if not seriess:
                return None
            
            s = seriess[0]
            return SeriesInfo(
                id=s.get("id", series_id),
                title=s.get("title", ""),
                frequency=s.get("frequency", ""),
                units=s.get("units", ""),
                seasonal_adjustment=s.get("seasonal_adjustment"),
                last_updated=s.get("last_updated"),
                notes=s.get("notes"),
            )
        except Exception as e:
            logger.warning(f"Failed to get series {series_id}: {e}")
            return None
    
    def get_observations(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        sort_order: str = "asc",
    ) -> SeriesObservations | None:
        """
        Get observations (data values) for a series.
        
        Args:
            series_id: The FRED series ID
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            limit: Maximum observations to return
            sort_order: "asc" or "desc"
            
        Returns:
            SeriesObservations or None if series not found
        """
        params = {"series_id": series_id, "sort_order": sort_order}
        
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date
        if limit:
            params["limit"] = limit
        
        try:
            result = self._request("/series/observations", params)
            
            observations = []
            for obs in result.get("observations", []):
                value_str = obs.get("value", ".")
                value = None if value_str == "." else float(value_str)
                observations.append(Observation(
                    date=obs.get("date", ""),
                    value=value,
                ))
            
            # Get series info for title and units
            series_info = self.get_series(series_id)
            title = series_info.title if series_info else series_id
            units = series_info.units if series_info else ""
            
            return SeriesObservations(
                series_id=series_id,
                title=title,
                units=units,
                observations=observations,
            )
        except Exception as e:
            logger.warning(f"Failed to get observations for {series_id}: {e}")
            return None
    
    def get_latest_value(self, series_id: str) -> SeriesObservations | None:
        """
        Get the most recent observation for a series.
        
        Args:
            series_id: The FRED series ID
            
        Returns:
            SeriesObservations with just the latest value
        """
        return self.get_observations(series_id, sort_order="desc", limit=1)
    
    def search_series(
        self,
        search_text: str,
        limit: int = 10,
        order_by: str = "popularity",
    ) -> SearchResult:
        """
        Search for data series.
        
        Args:
            search_text: Keywords to search for
            limit: Maximum results to return
            order_by: Sort order - "popularity", "search_rank", "series_id", 
                     "title", "units", "frequency"
            
        Returns:
            SearchResult with matching series
        """
        params = {
            "search_text": search_text,
            "limit": limit,
            "order_by": order_by,
        }
        
        try:
            result = self._request("/series/search", params)
            
            series = []
            for s in result.get("seriess", []):
                series.append(SeriesInfo(
                    id=s.get("id", ""),
                    title=s.get("title", ""),
                    frequency=s.get("frequency", ""),
                    units=s.get("units", ""),
                    seasonal_adjustment=s.get("seasonal_adjustment"),
                    last_updated=s.get("last_updated"),
                ))
            
            return SearchResult(
                series=series,
                total_count=result.get("count", len(series)),
            )
        except Exception as e:
            logger.warning(f"Failed to search series: {e}")
            return SearchResult(series=[], total_count=0)
    
    def get_mortgage_rates(self) -> str:
        """
        Get current mortgage rate data (convenience method).
        
        Returns:
            Formatted string with 30-year and 15-year mortgage rates
        """
        lines = ["**Current Mortgage Rates (FRED)**\n"]
        
        rate_30 = self.get_latest_value(SERIES_MORTGAGE_30Y)
        if rate_30 and rate_30.latest and rate_30.latest.value is not None:
            lines.append(f"30-Year Fixed: {rate_30.latest.value:.2f}% (as of {rate_30.latest.date})")
        else:
            lines.append("30-Year Fixed: Data unavailable")
        
        rate_15 = self.get_latest_value(SERIES_MORTGAGE_15Y)
        if rate_15 and rate_15.latest and rate_15.latest.value is not None:
            lines.append(f"15-Year Fixed: {rate_15.latest.value:.2f}% (as of {rate_15.latest.date})")
        else:
            lines.append("15-Year Fixed: Data unavailable")
        
        lines.append("\nSource: Federal Reserve Bank of St. Louis (FRED)")
        return "\n".join(lines)
    
    def get_key_economic_indicators(self) -> str:
        """
        Get key economic indicators (convenience method).
        
        Returns:
            Formatted string with key economic data
        """
        lines = ["**Key Economic Indicators (FRED)**\n"]
        
        indicators = [
            (SERIES_FED_FUNDS, "Federal Funds Rate"),
            (SERIES_PRIME_RATE, "Bank Prime Rate"),
            (SERIES_CPI, "Consumer Price Index"),
            (SERIES_UNEMPLOYMENT, "Unemployment Rate"),
        ]
        
        for series_id, label in indicators:
            obs = self.get_latest_value(series_id)
            if obs and obs.latest and obs.latest.value is not None:
                lines.append(f"{label}: {obs.latest.value:,.2f} {obs.units} (as of {obs.latest.date})")
            else:
                lines.append(f"{label}: Data unavailable")
        
        lines.append("\nSource: Federal Reserve Bank of St. Louis (FRED)")
        return "\n".join(lines)
    
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
    """Check if FRED API is configured and available."""
    return bool(config.FRED_API_KEY)


# Singleton instance
_client: FREDClient | None = None


def get_fred_client() -> FREDClient:
    """
    Get or create the singleton FRED client.
    
    Raises:
        ValueError: If API key is not configured
    """
    global _client
    if _client is None:
        if not is_available():
            raise ValueError("FRED API key not configured")
        _client = FREDClient()
    return _client

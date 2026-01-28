"""
Market data models.

This module defines the data structures for representing markets,
their trading hours, and related configuration.
"""

from datetime import time, datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
import json
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, computed_field


class LunchBreak(BaseModel):
    """Lunch break period for markets that close midday."""
    
    start: time = Field(..., description="Lunch break start time (local)")
    end: time = Field(..., description="Lunch break end time (local)")
    
    @computed_field
    @property
    def duration_minutes(self) -> int:
        """Calculate lunch break duration in minutes."""
        start_minutes = self.start.hour * 60 + self.start.minute
        end_minutes = self.end.hour * 60 + self.end.minute
        return end_minutes - start_minutes
    
    def is_during_lunch(self, check_time: time) -> bool:
        """Check if a given time falls within the lunch break."""
        return self.start <= check_time < self.end


class TradingHours(BaseModel):
    """Trading hours configuration for a market."""
    
    open: time = Field(..., description="Market open time (local)")
    close: time = Field(..., description="Market close time (local)")
    lunch_break: Optional[LunchBreak] = Field(
        None, description="Lunch break if applicable"
    )
    
    @computed_field
    @property
    def has_lunch_break(self) -> bool:
        """Check if the market has a lunch break."""
        return self.lunch_break is not None
    
    @computed_field
    @property
    def total_trading_minutes(self) -> int:
        """Calculate total trading minutes (excluding lunch break)."""
        open_minutes = self.open.hour * 60 + self.open.minute
        close_minutes = self.close.hour * 60 + self.close.minute
        total = close_minutes - open_minutes
        
        if self.lunch_break:
            total -= self.lunch_break.duration_minutes
        
        return total
    
    @computed_field
    @property
    def morning_session_end(self) -> Optional[time]:
        """Get the end of the morning session (start of lunch break)."""
        if self.lunch_break:
            return self.lunch_break.start
        return None
    
    @computed_field
    @property
    def afternoon_session_start(self) -> Optional[time]:
        """Get the start of the afternoon session (end of lunch break)."""
        if self.lunch_break:
            return self.lunch_break.end
        return None
    
    def is_trading_time(self, check_time: time) -> bool:
        """
        Check if a given time is within trading hours.
        
        Args:
            check_time: Time to check (local market time)
            
        Returns:
            True if market is open at this time
        """
        # Must be within open/close bounds
        if not (self.open <= check_time < self.close):
            return False
        
        # Check if during lunch break
        if self.lunch_break and self.lunch_break.is_during_lunch(check_time):
            return False
        
        return True
    
    def get_session(self, check_time: time) -> str:
        """
        Get the current session name for a given time.
        
        Args:
            check_time: Time to check (local market time)
            
        Returns:
            Session name: 'pre_market', 'morning', 'lunch', 'afternoon', 'post_market', 'closed'
        """
        if check_time < self.open:
            return "pre_market"
        
        if check_time >= self.close:
            return "post_market"
        
        if self.lunch_break:
            if check_time < self.lunch_break.start:
                return "morning"
            elif check_time < self.lunch_break.end:
                return "lunch"
            else:
                return "afternoon"
        
        return "regular"


class Market(BaseModel):
    """
    Market configuration model.
    
    Represents a trading market with its configuration including
    trading hours, timezone, settlement cycle, and cut-off times.
    """
    
    code: str = Field(..., description="Market code (e.g., JP, HK, SG)")
    name: str = Field(..., description="Full market/country name")
    exchange_name: str = Field(..., description="Exchange name")
    exchange_calendar_code: str = Field(
        ..., description="Code for exchange_calendars library (e.g., XTKS)"
    )
    timezone: str = Field(..., description="IANA timezone (e.g., Asia/Tokyo)")
    trading_hours: TradingHours = Field(..., description="Standard trading hours")
    settlement_cycle: int = Field(
        default=1, 
        ge=0, 
        le=5,
        description="Settlement cycle in days (1 for T+1, 2 for T+2)"
    )
    currency: str = Field(..., description="Local currency code (e.g., JPY)")
    depository_cut_off: Optional[time] = Field(
        None, description="Depository instruction cut-off time (local)"
    )
    
    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Ensure market code is uppercase and 2 characters."""
        v = v.upper().strip()
        if len(v) != 2:
            raise ValueError("Market code must be exactly 2 characters")
        return v
    
    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate that timezone is a valid IANA timezone."""
        try:
            ZoneInfo(v)
        except KeyError:
            raise ValueError(f"Invalid IANA timezone: {v}")
        return v
    
    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Ensure currency code is uppercase and 3 characters."""
        v = v.upper().strip()
        if len(v) != 3:
            raise ValueError("Currency code must be exactly 3 characters")
        return v
    
    @computed_field
    @property
    def settlement_cycle_label(self) -> str:
        """Human-readable settlement cycle label (e.g., 'T+1')."""
        return f"T+{self.settlement_cycle}"
    
    @computed_field
    @property
    def has_lunch_break(self) -> bool:
        """Check if the market has a lunch break."""
        return self.trading_hours.has_lunch_break
    
    def get_timezone_info(self) -> ZoneInfo:
        """Get the ZoneInfo object for this market's timezone."""
        return ZoneInfo(self.timezone)
    
    def get_current_local_time(self) -> datetime:
        """Get the current time in the market's local timezone."""
        return datetime.now(self.get_timezone_info())
    
    def is_trading_now(self) -> bool:
        """
        Check if the market is currently in trading hours.
        
        Note: This only checks time, not whether today is a trading day.
        Use CalendarService to check if today is a holiday.
        """
        local_now = self.get_current_local_time()
        return self.trading_hours.is_trading_time(local_now.time())
    
    def get_current_session(self) -> str:
        """Get the current trading session."""
        local_now = self.get_current_local_time()
        return self.trading_hours.get_session(local_now.time())
    
    def is_before_cut_off(self, check_time: Optional[time] = None) -> bool:
        """
        Check if a time is before the depository cut-off.
        
        Args:
            check_time: Time to check (local). If None, uses current time.
            
        Returns:
            True if before cut-off, False if after or no cut-off defined
        """
        if self.depository_cut_off is None:
            return True  # No cut-off defined, always valid
        
        if check_time is None:
            check_time = self.get_current_local_time().time()
        
        return check_time < self.depository_cut_off
    
    def __str__(self) -> str:
        return f"{self.name} ({self.code}) - {self.exchange_name}"
    
    def __repr__(self) -> str:
        return f"Market(code='{self.code}', name='{self.name}')"
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "JP",
                "name": "Japan",
                "exchange_name": "Tokyo Stock Exchange",
                "exchange_calendar_code": "XTKS",
                "timezone": "Asia/Tokyo",
                "trading_hours": {
                    "open": "09:00",
                    "close": "15:00",
                    "lunch_break": {"start": "11:30", "end": "12:30"},
                },
                "settlement_cycle": 1,
                "currency": "JPY",
                "depository_cut_off": "14:00",
            }
        }


class MarketRepository:
    """
    Repository for loading and managing market configurations.
    
    Loads market data from JSON file and provides lookup methods.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the repository.
        
        Args:
            config_path: Path to markets.json. If None, uses default location.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "data" / "markets.json"
        
        self._config_path = config_path
        self._markets: Dict[str, Market] = {}
        self._load_markets()
    
    def _load_markets(self) -> None:
        """Load markets from JSON configuration file."""
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Markets configuration file not found: {self._config_path}"
            )
        
        with open(self._config_path, "r") as f:
            data = json.load(f)
        
        for market_data in data.get("markets", []):
            market = Market.model_validate(market_data)
            self._markets[market.code] = market
    
    def get(self, code: str) -> Optional[Market]:
        """
        Get a market by its code.
        
        Args:
            code: Market code (e.g., 'JP', 'HK')
            
        Returns:
            Market object or None if not found
        """
        return self._markets.get(code.upper())
    
    def get_or_raise(self, code: str) -> Market:
        """
        Get a market by its code, raising an error if not found.
        
        Args:
            code: Market code (e.g., 'JP', 'HK')
            
        Returns:
            Market object
            
        Raises:
            ValueError: If market code is not found
        """
        market = self.get(code)
        if market is None:
            raise ValueError(
                f"Unknown market code: {code}. "
                f"Available markets: {', '.join(self.list_codes())}"
            )
        return market
    
    def list_all(self) -> List[Market]:
        """Get all available markets."""
        return list(self._markets.values())
    
    def list_codes(self) -> List[str]:
        """Get all available market codes."""
        return sorted(self._markets.keys())
    
    def list_for_dropdown(self) -> List[tuple]:
        """
        Get markets formatted for UI dropdown.
        
        Returns:
            List of (display_name, code) tuples
        """
        return [
            (f"{m.name} ({m.code}) - {m.exchange_name}", m.code)
            for m in sorted(self._markets.values(), key=lambda x: x.name)
        ]
    
    def __len__(self) -> int:
        return len(self._markets)
    
    def __contains__(self, code: str) -> bool:
        return code.upper() in self._markets
    
    def __iter__(self):
        return iter(self._markets.values())


# Singleton instance for easy access
_market_repository: Optional[MarketRepository] = None


def get_market_repository() -> MarketRepository:
    """
    Get the singleton MarketRepository instance.
    
    Returns:
        MarketRepository instance
    """
    global _market_repository
    if _market_repository is None:
        _market_repository = MarketRepository()
    return _market_repository


def get_market(code: str) -> Market:
    """
    Convenience function to get a market by code.
    
    Args:
        code: Market code (e.g., 'JP', 'HK')
        
    Returns:
        Market object
        
    Raises:
        ValueError: If market code is not found
    """
    return get_market_repository().get_or_raise(code)

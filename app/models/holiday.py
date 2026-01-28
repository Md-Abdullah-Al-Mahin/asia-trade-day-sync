"""
Holiday calendar models.

This module defines data structures for representing holidays
and provides a HolidayCalendar class to manage and query holidays
using the `holidays` and `exchange_calendars` libraries.
"""

from datetime import date as date_type, timedelta
from enum import Enum
from typing import Optional, List, Dict, Set
from pydantic import BaseModel, Field, field_validator, computed_field

import holidays as holidays_lib
import exchange_calendars as xcals

from app.config import EXCHANGE_CALENDAR_CODES


class HolidayType(str, Enum):
    """Type of holiday/closure."""
    
    FULL_DAY = "full_day"
    HALF_DAY = "half_day"
    SPECIAL_CLOSURE = "special_closure"  # e.g., typhoon
    WEEKEND = "weekend"


class HolidaySource(str, Enum):
    """Source of holiday data."""
    
    EXCHANGE_CALENDAR = "exchange_calendar"  # From exchange_calendars library
    PUBLIC_HOLIDAY = "public_holiday"  # From holidays library
    MANUAL = "manual"  # Manually configured


class Holiday(BaseModel):
    """
    Holiday calendar entry.
    
    Represents a single holiday or market closure for a specific market.
    """
    
    market_code: str = Field(..., description="Market code (e.g., JP, HK)")
    date: date_type = Field(..., description="Holiday date")
    name: str = Field(..., description="Holiday name")
    holiday_type: HolidayType = Field(
        default=HolidayType.FULL_DAY, description="Type of holiday"
    )
    affects_trading: bool = Field(
        default=True, description="Whether trading is affected"
    )
    affects_settlement: bool = Field(
        default=True, description="Whether settlement is affected"
    )
    source: HolidaySource = Field(
        default=HolidaySource.EXCHANGE_CALENDAR,
        description="Source of holiday data"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    
    @field_validator("market_code")
    @classmethod
    def validate_market_code(cls, v: str) -> str:
        """Ensure market code is uppercase."""
        return v.upper().strip()
    
    @computed_field
    @property
    def is_weekend(self) -> bool:
        """Check if this holiday falls on a weekend."""
        return self.date.weekday() >= 5
    
    @computed_field
    @property
    def day_of_week(self) -> str:
        """Get the day of week name."""
        return self.date.strftime("%A")
    
    @computed_field
    @property
    def formatted_date(self) -> str:
        """Get formatted date string (YYYY-MM-DD)."""
        return self.date.isoformat()
    
    def __str__(self) -> str:
        return f"{self.date} - {self.name} ({self.market_code})"
    
    def __repr__(self) -> str:
        return f"Holiday(date={self.date}, name='{self.name}', market='{self.market_code}')"
    
    def __hash__(self) -> int:
        return hash((self.market_code, self.date))
    
    def __eq__(self, other) -> bool:
        if isinstance(other, Holiday):
            return self.market_code == other.market_code and self.date == other.date
        return False
    
    class Config:
        json_schema_extra = {
            "example": {
                "market_code": "JP",
                "date": "2026-01-01",
                "name": "New Year's Day",
                "holiday_type": "full_day",
                "affects_trading": True,
                "affects_settlement": True,
                "source": "exchange_calendar",
                "notes": None,
            }
        }


# Mapping of market codes to holidays library country codes
MARKET_TO_COUNTRY_CODE: Dict[str, str] = {
    "JP": "JP",  # Japan
    "HK": "HK",  # Hong Kong
    "SG": "SG",  # Singapore
    "IN": "IN",  # India
    "AU": "AU",  # Australia
    "KR": "KR",  # South Korea
    "TW": "TW",  # Taiwan
    "CN": "CN",  # China
}


class HolidayCalendar:
    """
    Holiday calendar manager for a specific market.
    
    Combines data from exchange_calendars (trading holidays) and
    holidays library (public holidays) to provide comprehensive
    holiday information.
    """
    
    def __init__(self, market_code: str):
        """
        Initialize the holiday calendar for a market.
        
        Args:
            market_code: Market code (e.g., 'JP', 'HK')
        """
        self.market_code = market_code.upper()
        self._exchange_calendar = self._load_exchange_calendar()
        self._public_holidays = self._load_public_holidays()
        self._manual_holidays: Dict[date_type, Holiday] = {}
    
    def _load_exchange_calendar(self):
        """Load the exchange calendar for this market."""
        calendar_code = EXCHANGE_CALENDAR_CODES.get(self.market_code)
        if calendar_code is None:
            raise ValueError(
                f"No exchange calendar code found for market: {self.market_code}"
            )
        return xcals.get_calendar(calendar_code)
    
    def _load_public_holidays(self):
        """Load public holidays for this market's country."""
        country_code = MARKET_TO_COUNTRY_CODE.get(self.market_code)
        if country_code is None:
            return None
        
        try:
            return holidays_lib.country_holidays(country_code)
        except NotImplementedError:
            # Country not supported by holidays library
            return None
    
    def is_trading_day(self, check_date: date_type) -> bool:
        """
        Check if a date is a trading day.
        
        Args:
            check_date: Date to check
            
        Returns:
            True if the market is open for trading
        """
        # Check manual holidays first
        if check_date in self._manual_holidays:
            holiday = self._manual_holidays[check_date]
            if holiday.affects_trading:
                return False
        
        # Use exchange calendar for authoritative trading day info
        return self._exchange_calendar.is_session(check_date)
    
    def is_settlement_day(self, check_date: date_type) -> bool:
        """
        Check if a date is a settlement day.
        
        Settlement typically follows trading days, but some holidays
        may affect settlement differently.
        
        Args:
            check_date: Date to check
            
        Returns:
            True if settlement can occur on this date
        """
        # Check manual holidays first
        if check_date in self._manual_holidays:
            holiday = self._manual_holidays[check_date]
            if holiday.affects_settlement:
                return False
        
        # Generally, settlement days align with trading days
        return self.is_trading_day(check_date)
    
    def get_holiday(self, check_date: date_type) -> Optional[Holiday]:
        """
        Get holiday information for a specific date.
        
        Args:
            check_date: Date to check
            
        Returns:
            Holiday object if date is a holiday, None otherwise
        """
        # Check manual holidays first
        if check_date in self._manual_holidays:
            return self._manual_holidays[check_date]
        
        # Check if it's a weekend
        if check_date.weekday() >= 5:
            return Holiday(
                market_code=self.market_code,
                date=check_date,
                name="Weekend",
                holiday_type=HolidayType.WEEKEND,
                affects_trading=True,
                affects_settlement=True,
                source=HolidaySource.EXCHANGE_CALENDAR,
            )
        
        # Check exchange calendar
        if not self._exchange_calendar.is_session(check_date):
            # It's not a trading day - find the holiday name
            holiday_name = self._get_holiday_name(check_date)
            return Holiday(
                market_code=self.market_code,
                date=check_date,
                name=holiday_name,
                holiday_type=HolidayType.FULL_DAY,
                affects_trading=True,
                affects_settlement=True,
                source=HolidaySource.EXCHANGE_CALENDAR,
            )
        
        return None
    
    def _get_holiday_name(self, check_date: date_type) -> str:
        """Get the name of a holiday from available sources."""
        # Try public holidays library first
        if self._public_holidays and check_date in self._public_holidays:
            return self._public_holidays.get(check_date)
        
        # Default name
        return "Market Holiday"
    
    def get_holidays_in_range(
        self, 
        start_date: date_type, 
        end_date: date_type,
        include_weekends: bool = False
    ) -> List[Holiday]:
        """
        Get all holidays within a date range.
        
        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            include_weekends: Whether to include weekends
            
        Returns:
            List of Holiday objects
        """
        holidays = []
        current = start_date
        
        while current <= end_date:
            holiday = self.get_holiday(current)
            if holiday:
                if include_weekends or holiday.holiday_type != HolidayType.WEEKEND:
                    holidays.append(holiday)
            current += timedelta(days=1)
        
        return holidays
    
    def get_non_trading_days_in_range(
        self,
        start_date: date_type,
        end_date: date_type
    ) -> List[date_type]:
        """
        Get all non-trading days within a date range.
        
        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            
        Returns:
            List of dates that are not trading days
        """
        non_trading = []
        current = start_date
        
        while current <= end_date:
            if not self.is_trading_day(current):
                non_trading.append(current)
            current += timedelta(days=1)
        
        return non_trading
    
    def get_trading_days_in_range(
        self,
        start_date: date_type,
        end_date: date_type
    ) -> List[date_type]:
        """
        Get all trading days within a date range.
        
        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            
        Returns:
            List of dates that are trading days
        """
        trading = []
        current = start_date
        
        while current <= end_date:
            if self.is_trading_day(current):
                trading.append(current)
            current += timedelta(days=1)
        
        return trading
    
    def get_next_trading_day(self, from_date: date_type) -> date_type:
        """
        Get the next trading day after a given date.
        
        Args:
            from_date: Starting date (exclusive)
            
        Returns:
            Next trading day
        """
        check_date = from_date + timedelta(days=1)
        max_iterations = 30  # Safety limit
        
        for _ in range(max_iterations):
            if self.is_trading_day(check_date):
                return check_date
            check_date += timedelta(days=1)
        
        raise ValueError(
            f"Could not find next trading day within {max_iterations} days of {from_date}"
        )
    
    def get_previous_trading_day(self, from_date: date_type) -> date_type:
        """
        Get the previous trading day before a given date.
        
        Args:
            from_date: Starting date (exclusive)
            
        Returns:
            Previous trading day
        """
        check_date = from_date - timedelta(days=1)
        max_iterations = 30  # Safety limit
        
        for _ in range(max_iterations):
            if self.is_trading_day(check_date):
                return check_date
            check_date -= timedelta(days=1)
        
        raise ValueError(
            f"Could not find previous trading day within {max_iterations} days of {from_date}"
        )
    
    def add_manual_holiday(self, holiday: Holiday) -> None:
        """
        Add a manual holiday override.
        
        Useful for special closures like typhoon days.
        
        Args:
            holiday: Holiday to add
        """
        if holiday.market_code != self.market_code:
            raise ValueError(
                f"Holiday market code {holiday.market_code} does not match "
                f"calendar market code {self.market_code}"
            )
        self._manual_holidays[holiday.date] = holiday
    
    def remove_manual_holiday(self, date: date_type) -> bool:
        """
        Remove a manual holiday override.
        
        Args:
            date: Date to remove
            
        Returns:
            True if holiday was removed, False if not found
        """
        if date in self._manual_holidays:
            del self._manual_holidays[date]
            return True
        return False
    
    def count_trading_days_between(
        self,
        start_date: date_type,
        end_date: date_type
    ) -> int:
        """
        Count the number of trading days between two dates.
        
        Args:
            start_date: Start date (exclusive)
            end_date: End date (exclusive)
            
        Returns:
            Number of trading days
        """
        return len(self.get_trading_days_in_range(
            start_date + timedelta(days=1),
            end_date - timedelta(days=1)
        ))
    
    def __repr__(self) -> str:
        return f"HolidayCalendar(market_code='{self.market_code}')"


# Cache for HolidayCalendar instances
_calendar_cache: Dict[str, HolidayCalendar] = {}


def get_holiday_calendar(market_code: str) -> HolidayCalendar:
    """
    Get a HolidayCalendar instance for a market (cached).
    
    Args:
        market_code: Market code (e.g., 'JP', 'HK')
        
    Returns:
        HolidayCalendar instance
    """
    market_code = market_code.upper()
    if market_code not in _calendar_cache:
        _calendar_cache[market_code] = HolidayCalendar(market_code)
    return _calendar_cache[market_code]


def get_common_trading_days(
    market_a: str,
    market_b: str,
    start_date: date_type,
    end_date: date_type
) -> List[date_type]:
    """
    Get dates that are trading days in both markets.
    
    Args:
        market_a: First market code
        market_b: Second market code
        start_date: Start of range (inclusive)
        end_date: End of range (inclusive)
        
    Returns:
        List of common trading days
    """
    cal_a = get_holiday_calendar(market_a)
    cal_b = get_holiday_calendar(market_b)
    
    common_days = []
    current = start_date
    
    while current <= end_date:
        if cal_a.is_trading_day(current) and cal_b.is_trading_day(current):
            common_days.append(current)
        current += timedelta(days=1)
    
    return common_days


def get_common_holidays(
    market_a: str,
    market_b: str,
    start_date: date_type,
    end_date: date_type,
    include_weekends: bool = False
) -> List[date_type]:
    """
    Get dates that are holidays in both markets.
    
    Args:
        market_a: First market code
        market_b: Second market code
        start_date: Start of range (inclusive)
        end_date: End of range (inclusive)
        include_weekends: Whether to include weekends
        
    Returns:
        List of common holiday dates
    """
    cal_a = get_holiday_calendar(market_a)
    cal_b = get_holiday_calendar(market_b)
    
    common_holidays = []
    current = start_date
    
    while current <= end_date:
        if not include_weekends and current.weekday() >= 5:
            current += timedelta(days=1)
            continue
            
        if not cal_a.is_trading_day(current) and not cal_b.is_trading_day(current):
            common_holidays.append(current)
        current += timedelta(days=1)
    
    return common_holidays

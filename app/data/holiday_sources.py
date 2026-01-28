"""
Holiday Data Sources Manager.

This module integrates multiple holiday data sources:
1. exchange_calendars - Exchange-specific trading holidays
2. holidays library - Public/bank holidays by country
3. Manual overrides - For special closures (typhoons, etc.)

Provides a unified interface for querying holiday information.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

import holidays as holidays_lib
import exchange_calendars as xcals

from app.config import EXCHANGE_CALENDAR_CODES


class HolidaySourceType(str, Enum):
    """Source of holiday data."""
    
    EXCHANGE_CALENDAR = "exchange_calendar"
    PUBLIC_HOLIDAY = "public_holiday"
    MANUAL_OVERRIDE = "manual_override"
    WEEKEND = "weekend"


@dataclass
class HolidayInfo:
    """Detailed holiday information from all sources."""
    
    date: date
    market_code: str
    name: str
    source: HolidaySourceType
    is_full_day: bool = True
    affects_trading: bool = True
    affects_settlement: bool = True
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "market_code": self.market_code,
            "name": self.name,
            "source": self.source.value,
            "is_full_day": self.is_full_day,
            "affects_trading": self.affects_trading,
            "affects_settlement": self.affects_settlement,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "HolidayInfo":
        """Create from dictionary."""
        return cls(
            date=date.fromisoformat(data["date"]),
            market_code=data["market_code"],
            name=data["name"],
            source=HolidaySourceType(data["source"]),
            is_full_day=data.get("is_full_day", True),
            affects_trading=data.get("affects_trading", True),
            affects_settlement=data.get("affects_settlement", True),
            notes=data.get("notes")
        )


@dataclass
class ManualOverride:
    """A manual holiday override entry."""
    
    date: date
    market_code: str
    name: str
    reason: str
    is_closure: bool = True  # True = closed, False = override to open
    affects_trading: bool = True
    affects_settlement: bool = True
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date.isoformat(),
            "market_code": self.market_code,
            "name": self.name,
            "reason": self.reason,
            "is_closure": self.is_closure,
            "affects_trading": self.affects_trading,
            "affects_settlement": self.affects_settlement,
            "created_at": self.created_at or date.today().isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ManualOverride":
        """Create from dictionary."""
        return cls(
            date=date.fromisoformat(data["date"]),
            market_code=data["market_code"],
            name=data["name"],
            reason=data["reason"],
            is_closure=data.get("is_closure", True),
            affects_trading=data.get("affects_trading", True),
            affects_settlement=data.get("affects_settlement", True),
            created_at=data.get("created_at", "")
        )


# Mapping of market codes to holidays library country codes
MARKET_TO_COUNTRY: Dict[str, str] = {
    "JP": "JP",
    "HK": "HK",
    "SG": "SG",
    "IN": "IN",
    "AU": "AU",
    "KR": "KR",
    "TW": "TW",
    "CN": "CN",
}

# Common holiday name mappings for better display
HOLIDAY_NAME_MAPPINGS: Dict[str, str] = {
    # Japan
    "元日": "New Year's Day",
    "成人の日": "Coming of Age Day",
    "建国記念の日": "National Foundation Day",
    "天皇誕生日": "Emperor's Birthday",
    "春分の日": "Vernal Equinox Day",
    "昭和の日": "Showa Day",
    "憲法記念日": "Constitution Memorial Day",
    "みどりの日": "Greenery Day",
    "こどもの日": "Children's Day",
    "海の日": "Marine Day",
    "山の日": "Mountain Day",
    "敬老の日": "Respect for the Aged Day",
    "秋分の日": "Autumnal Equinox Day",
    "スポーツの日": "Sports Day",
    "文化の日": "Culture Day",
    "勤労感謝の日": "Labor Thanksgiving Day",
    
    # China
    "春节": "Chinese New Year",
    "清明节": "Qingming Festival",
    "劳动节": "Labor Day",
    "端午节": "Dragon Boat Festival",
    "中秋节": "Mid-Autumn Festival",
    "国庆节": "National Day",
    
    # Korea
    "설날": "Lunar New Year",
    "추석": "Chuseok",
}


class ExchangeCalendarSource:
    """
    Exchange calendar data source using exchange_calendars library.
    
    Provides accurate trading day information for each exchange.
    """
    
    def __init__(self):
        self._calendars: Dict[str, xcals.ExchangeCalendar] = {}
    
    def _get_calendar(self, market_code: str) -> xcals.ExchangeCalendar:
        """Get or create calendar for a market."""
        if market_code not in self._calendars:
            calendar_code = EXCHANGE_CALENDAR_CODES.get(market_code.upper())
            if not calendar_code:
                raise ValueError(f"No exchange calendar for market: {market_code}")
            self._calendars[market_code] = xcals.get_calendar(calendar_code)
        return self._calendars[market_code]
    
    def is_trading_day(self, market_code: str, check_date: date) -> bool:
        """Check if date is a trading day."""
        try:
            calendar = self._get_calendar(market_code)
            return calendar.is_session(check_date)
        except Exception:
            return False
    
    def get_non_trading_days(
        self, 
        market_code: str, 
        start_date: date, 
        end_date: date
    ) -> List[date]:
        """Get all non-trading days in range (excluding weekends by default)."""
        calendar = self._get_calendar(market_code)
        non_trading = []
        
        current = start_date
        while current <= end_date:
            if not calendar.is_session(current):
                non_trading.append(current)
            current += timedelta(days=1)
        
        return non_trading
    
    def get_exchange_holidays(
        self,
        market_code: str,
        start_date: date,
        end_date: date
    ) -> List[HolidayInfo]:
        """Get exchange holidays (non-trading days that aren't weekends)."""
        holidays = []
        non_trading = self.get_non_trading_days(market_code, start_date, end_date)
        
        for d in non_trading:
            if d.weekday() < 5:  # Not a weekend
                holidays.append(HolidayInfo(
                    date=d,
                    market_code=market_code,
                    name="Exchange Holiday",
                    source=HolidaySourceType.EXCHANGE_CALENDAR,
                    is_full_day=True,
                    affects_trading=True,
                    affects_settlement=True
                ))
        
        return holidays


class PublicHolidaySource:
    """
    Public holiday data source using the holidays library.
    
    Provides country-level public/bank holidays.
    """
    
    def __init__(self):
        self._country_holidays: Dict[str, holidays_lib.HolidayBase] = {}
    
    def _get_country_holidays(self, country_code: str, year: int) -> holidays_lib.HolidayBase:
        """Get holidays for a country and year."""
        key = f"{country_code}_{year}"
        if key not in self._country_holidays:
            try:
                self._country_holidays[key] = holidays_lib.country_holidays(
                    country_code, years=year
                )
            except NotImplementedError:
                # Country not supported
                self._country_holidays[key] = {}
        return self._country_holidays[key]
    
    def get_holiday_name(self, market_code: str, check_date: date) -> Optional[str]:
        """Get the public holiday name for a date."""
        country_code = MARKET_TO_COUNTRY.get(market_code.upper())
        if not country_code:
            return None
        
        country_holidays = self._get_country_holidays(country_code, check_date.year)
        
        if check_date in country_holidays:
            name = country_holidays.get(check_date)
            # Try to translate if needed
            return HOLIDAY_NAME_MAPPINGS.get(name, name)
        
        return None
    
    def get_public_holidays(
        self,
        market_code: str,
        start_date: date,
        end_date: date
    ) -> List[HolidayInfo]:
        """Get all public holidays in a date range."""
        country_code = MARKET_TO_COUNTRY.get(market_code.upper())
        if not country_code:
            return []
        
        holidays = []
        
        # Get holidays for all years in range
        years = set()
        current = start_date
        while current <= end_date:
            years.add(current.year)
            current += timedelta(days=365)
        years.add(end_date.year)
        
        for year in years:
            country_holidays = self._get_country_holidays(country_code, year)
            
            for holiday_date, holiday_name in country_holidays.items():
                if start_date <= holiday_date <= end_date:
                    translated_name = HOLIDAY_NAME_MAPPINGS.get(holiday_name, holiday_name)
                    holidays.append(HolidayInfo(
                        date=holiday_date,
                        market_code=market_code,
                        name=translated_name,
                        source=HolidaySourceType.PUBLIC_HOLIDAY,
                        is_full_day=True,
                        affects_trading=True,
                        affects_settlement=True
                    ))
        
        # Sort by date
        holidays.sort(key=lambda h: h.date)
        return holidays
    
    def is_public_holiday(self, market_code: str, check_date: date) -> bool:
        """Check if a date is a public holiday."""
        return self.get_holiday_name(market_code, check_date) is not None


class ManualOverrideSource:
    """
    Manual override data source for special closures.
    
    Handles typhoon days, special closures, and corrections to
    the automated holiday data.
    """
    
    def __init__(self, overrides_file: Optional[Path] = None):
        if overrides_file is None:
            overrides_file = Path(__file__).parent / "manual_overrides.json"
        
        self._overrides_file = overrides_file
        self._overrides: Dict[str, Dict[date, ManualOverride]] = {}
        self._load_overrides()
    
    def _load_overrides(self) -> None:
        """Load overrides from JSON file."""
        if not self._overrides_file.exists():
            return
        
        try:
            with open(self._overrides_file, "r") as f:
                data = json.load(f)
            
            for override_data in data.get("overrides", []):
                override = ManualOverride.from_dict(override_data)
                market = override.market_code.upper()
                
                if market not in self._overrides:
                    self._overrides[market] = {}
                
                self._overrides[market][override.date] = override
        except Exception as e:
            print(f"Warning: Could not load manual overrides: {e}")
    
    def save_overrides(self) -> None:
        """Save overrides to JSON file."""
        all_overrides = []
        for market_overrides in self._overrides.values():
            for override in market_overrides.values():
                all_overrides.append(override.to_dict())
        
        data = {
            "version": "1.0.0",
            "description": "Manual holiday overrides for special closures",
            "overrides": all_overrides
        }
        
        with open(self._overrides_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def add_override(self, override: ManualOverride) -> None:
        """Add a manual override."""
        market = override.market_code.upper()
        
        if market not in self._overrides:
            self._overrides[market] = {}
        
        self._overrides[market][override.date] = override
        self.save_overrides()
    
    def remove_override(self, market_code: str, override_date: date) -> bool:
        """Remove a manual override."""
        market = market_code.upper()
        
        if market in self._overrides and override_date in self._overrides[market]:
            del self._overrides[market][override_date]
            self.save_overrides()
            return True
        
        return False
    
    def get_override(self, market_code: str, check_date: date) -> Optional[ManualOverride]:
        """Get override for a specific date."""
        market = market_code.upper()
        return self._overrides.get(market, {}).get(check_date)
    
    def has_closure_override(self, market_code: str, check_date: date) -> bool:
        """Check if there's a closure override for a date."""
        override = self.get_override(market_code, check_date)
        return override is not None and override.is_closure
    
    def get_all_overrides(
        self,
        market_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[ManualOverride]:
        """Get all overrides for a market, optionally filtered by date range."""
        market = market_code.upper()
        overrides = list(self._overrides.get(market, {}).values())
        
        if start_date:
            overrides = [o for o in overrides if o.date >= start_date]
        if end_date:
            overrides = [o for o in overrides if o.date <= end_date]
        
        return sorted(overrides, key=lambda o: o.date)


class HolidayDataManager:
    """
    Unified holiday data manager combining all sources.
    
    Provides a single interface to query holiday information
    from exchange calendars, public holidays, and manual overrides.
    """
    
    def __init__(self):
        self.exchange_source = ExchangeCalendarSource()
        self.public_source = PublicHolidaySource()
        self.manual_source = ManualOverrideSource()
    
    def is_trading_day(self, market_code: str, check_date: date) -> bool:
        """
        Check if a date is a trading day, considering all sources.
        
        Priority:
        1. Manual override (highest)
        2. Exchange calendar
        """
        # Check manual override first
        override = self.manual_source.get_override(market_code, check_date)
        if override:
            if override.is_closure:
                return False  # Manual closure
            else:
                return True  # Manual override to open
        
        # Fall back to exchange calendar
        return self.exchange_source.is_trading_day(market_code, check_date)
    
    def get_holiday_info(
        self, 
        market_code: str, 
        check_date: date
    ) -> Optional[HolidayInfo]:
        """
        Get detailed holiday information for a date.
        
        Combines information from all sources.
        """
        market_code = market_code.upper()
        
        # Check manual override first
        override = self.manual_source.get_override(market_code, check_date)
        if override and override.is_closure:
            return HolidayInfo(
                date=check_date,
                market_code=market_code,
                name=override.name,
                source=HolidaySourceType.MANUAL_OVERRIDE,
                is_full_day=True,
                affects_trading=override.affects_trading,
                affects_settlement=override.affects_settlement,
                notes=override.reason
            )
        
        # Check if it's a weekend
        if check_date.weekday() >= 5:
            return HolidayInfo(
                date=check_date,
                market_code=market_code,
                name="Weekend",
                source=HolidaySourceType.WEEKEND,
                is_full_day=True,
                affects_trading=True,
                affects_settlement=True
            )
        
        # Check if it's an exchange holiday
        if not self.exchange_source.is_trading_day(market_code, check_date):
            # Try to get the public holiday name
            holiday_name = self.public_source.get_holiday_name(market_code, check_date)
            
            return HolidayInfo(
                date=check_date,
                market_code=market_code,
                name=holiday_name or "Market Holiday",
                source=HolidaySourceType.EXCHANGE_CALENDAR if not holiday_name 
                       else HolidaySourceType.PUBLIC_HOLIDAY,
                is_full_day=True,
                affects_trading=True,
                affects_settlement=True
            )
        
        return None
    
    def get_holidays_in_range(
        self,
        market_code: str,
        start_date: date,
        end_date: date,
        include_weekends: bool = False
    ) -> List[HolidayInfo]:
        """
        Get all holidays in a date range.
        
        Args:
            market_code: Market code
            start_date: Start of range
            end_date: End of range
            include_weekends: Whether to include weekends
            
        Returns:
            List of HolidayInfo objects
        """
        holidays = []
        seen_dates: Set[date] = set()
        
        current = start_date
        while current <= end_date:
            holiday = self.get_holiday_info(market_code, current)
            
            if holiday and current not in seen_dates:
                if include_weekends or holiday.source != HolidaySourceType.WEEKEND:
                    holidays.append(holiday)
                    seen_dates.add(current)
            
            current += timedelta(days=1)
        
        return holidays
    
    def get_upcoming_holidays(
        self,
        market_code: str,
        days_ahead: int = 30,
        include_weekends: bool = False
    ) -> List[HolidayInfo]:
        """Get upcoming holidays."""
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        return self.get_holidays_in_range(
            market_code, today, end_date, include_weekends
        )
    
    def add_special_closure(
        self,
        market_code: str,
        closure_date: date,
        name: str,
        reason: str
    ) -> None:
        """
        Add a special closure (e.g., typhoon day).
        
        Args:
            market_code: Market code
            closure_date: Date of closure
            name: Name of the closure
            reason: Reason for closure
        """
        override = ManualOverride(
            date=closure_date,
            market_code=market_code.upper(),
            name=name,
            reason=reason,
            is_closure=True,
            affects_trading=True,
            affects_settlement=True
        )
        self.manual_source.add_override(override)
    
    def remove_special_closure(self, market_code: str, closure_date: date) -> bool:
        """Remove a special closure."""
        return self.manual_source.remove_override(market_code, closure_date)
    
    def get_holiday_summary(
        self,
        market_code: str,
        year: int
    ) -> Dict:
        """
        Get a summary of holidays for a market in a year.
        
        Returns:
            Dictionary with holiday statistics and list
        """
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        
        holidays = self.get_holidays_in_range(market_code, start, end, include_weekends=False)
        
        by_source = {
            HolidaySourceType.EXCHANGE_CALENDAR: [],
            HolidaySourceType.PUBLIC_HOLIDAY: [],
            HolidaySourceType.MANUAL_OVERRIDE: [],
        }
        
        for h in holidays:
            if h.source in by_source:
                by_source[h.source].append(h)
        
        return {
            "market_code": market_code,
            "year": year,
            "total_holidays": len(holidays),
            "by_source": {
                "exchange": len(by_source[HolidaySourceType.EXCHANGE_CALENDAR]),
                "public": len(by_source[HolidaySourceType.PUBLIC_HOLIDAY]),
                "manual": len(by_source[HolidaySourceType.MANUAL_OVERRIDE]),
            },
            "holidays": holidays
        }
    
    def compare_markets(
        self,
        market_a: str,
        market_b: str,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Compare holidays between two markets.
        
        Returns:
            Dictionary with comparison data
        """
        holidays_a = self.get_holidays_in_range(market_a, start_date, end_date)
        holidays_b = self.get_holidays_in_range(market_b, start_date, end_date)
        
        dates_a = {h.date for h in holidays_a}
        dates_b = {h.date for h in holidays_b}
        
        common = dates_a & dates_b
        only_a = dates_a - dates_b
        only_b = dates_b - dates_a
        
        return {
            "market_a": market_a,
            "market_b": market_b,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_a": len(holidays_a),
                "total_b": len(holidays_b),
                "common": len(common),
                "only_a": len(only_a),
                "only_b": len(only_b)
            },
            "common_dates": sorted([d.isoformat() for d in common]),
            "only_in_a": sorted([d.isoformat() for d in only_a]),
            "only_in_b": sorted([d.isoformat() for d in only_b])
        }


# Singleton instance
_holiday_manager: Optional[HolidayDataManager] = None


def get_holiday_manager() -> HolidayDataManager:
    """Get the singleton HolidayDataManager instance."""
    global _holiday_manager
    if _holiday_manager is None:
        _holiday_manager = HolidayDataManager()
    return _holiday_manager


def print_holiday_report(market_code: str, year: int = 2026):
    """Print a holiday report for a market."""
    manager = get_holiday_manager()
    summary = manager.get_holiday_summary(market_code, year)
    
    print("=" * 60)
    print(f"HOLIDAY REPORT: {market_code} - {year}")
    print("=" * 60)
    print(f"\nTotal holidays: {summary['total_holidays']}")
    print(f"  - Exchange holidays: {summary['by_source']['exchange']}")
    print(f"  - Public holidays: {summary['by_source']['public']}")
    print(f"  - Manual overrides: {summary['by_source']['manual']}")
    print("\nHoliday List:")
    print("-" * 60)
    
    for h in summary["holidays"]:
        source_icon = {
            HolidaySourceType.EXCHANGE_CALENDAR: "📈",
            HolidaySourceType.PUBLIC_HOLIDAY: "🏛️",
            HolidaySourceType.MANUAL_OVERRIDE: "✋",
        }.get(h.source, "📅")
        
        print(f"  {h.date} ({h.date.strftime('%a')}) {source_icon} {h.name}")
    
    print("=" * 60)

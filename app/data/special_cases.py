"""
Special Cases Handler for Asian Markets.

This module documents and handles special market scenarios:
1. Typhoon closures (HK, TW)
2. Lunar New Year variations
3. Half-day trading sessions
4. Post-holiday settlement adjustments

These cases require special handling beyond standard holiday calendars.
"""

import json
from datetime import date, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from app.data.holiday_sources import (
    get_holiday_manager,
    ManualOverride,
    HolidayInfo,
    HolidaySourceType,
)


# =============================================================================
# 1. TYPHOON CLOSURES (HK, TW)
# =============================================================================

class TyphoonSignal(str, Enum):
    """Typhoon warning signal levels."""
    
    # Hong Kong Observatory signals
    HK_SIGNAL_1 = "T1"      # Standby - Markets OPEN
    HK_SIGNAL_3 = "T3"      # Strong Wind - Markets OPEN
    HK_SIGNAL_8 = "T8"      # Gale/Storm - Markets CLOSED
    HK_SIGNAL_9 = "T9"      # Increasing Gale - Markets CLOSED
    HK_SIGNAL_10 = "T10"    # Hurricane - Markets CLOSED
    
    # Taiwan Central Weather Bureau signals
    TW_SEA = "TW_SEA"           # Sea Warning - Markets OPEN
    TW_LAND = "TW_LAND"         # Land Warning - Markets may close
    TW_LAND_SEA = "TW_LAND_SEA" # Both warnings - Markets likely CLOSED


@dataclass
class TyphoonClosure:
    """Represents a typhoon-related market closure."""
    
    date: date
    market_code: str  # HK or TW
    signal: TyphoonSignal
    typhoon_name: str
    announced_time: Optional[time] = None
    is_full_day: bool = True
    morning_session_open: bool = False
    afternoon_session_open: bool = False
    notes: str = ""
    
    @property
    def closure_type(self) -> str:
        """Get human-readable closure type."""
        if self.is_full_day:
            return "Full day closure"
        elif not self.morning_session_open and self.afternoon_session_open:
            return "Morning session closed"
        elif self.morning_session_open and not self.afternoon_session_open:
            return "Afternoon session closed"
        else:
            return "Partial closure"
    
    def to_manual_override(self) -> ManualOverride:
        """Convert to ManualOverride for holiday system."""
        return ManualOverride(
            date=self.date,
            market_code=self.market_code,
            name=f"Typhoon {self.typhoon_name} ({self.signal.value})",
            reason=f"Typhoon closure - {self.closure_type}. {self.notes}",
            is_closure=True,
            affects_trading=True,
            affects_settlement=True,
        )


# Typhoon closure rules by market
TYPHOON_RULES: Dict[str, Dict] = {
    "HK": {
        "name": "Hong Kong",
        "authority": "Hong Kong Observatory",
        "website": "https://www.hko.gov.hk",
        "rules": [
            {
                "signal": TyphoonSignal.HK_SIGNAL_8,
                "market_action": "CLOSED",
                "description": "Market closes when Signal 8 is hoisted before 9:00 AM",
                "settlement_impact": "Settlement delayed by one business day"
            },
            {
                "signal": TyphoonSignal.HK_SIGNAL_9,
                "market_action": "CLOSED",
                "description": "Market remains closed",
                "settlement_impact": "Settlement delayed"
            },
            {
                "signal": TyphoonSignal.HK_SIGNAL_10,
                "market_action": "CLOSED", 
                "description": "Market remains closed",
                "settlement_impact": "Settlement delayed"
            },
        ],
        "reopening_rules": [
            "If Signal 8 lowered before 9:00 AM → Morning session opens normally",
            "If Signal 8 lowered before 12:00 PM → Afternoon session opens at 1:00 PM",
            "If Signal 8 lowered after 12:00 PM → Market closed for the day",
        ],
        "notes": "HKEX monitors signals and announces closures via official channels"
    },
    "TW": {
        "name": "Taiwan",
        "authority": "Central Weather Bureau",
        "website": "https://www.cwb.gov.tw",
        "rules": [
            {
                "signal": TyphoonSignal.TW_LAND,
                "market_action": "MAY_CLOSE",
                "description": "Market may close if government declares work suspension",
                "settlement_impact": "Settlement follows government announcement"
            },
            {
                "signal": TyphoonSignal.TW_LAND_SEA,
                "market_action": "LIKELY_CLOSED",
                "description": "Market likely closed if both warnings active",
                "settlement_impact": "Settlement delayed"
            },
        ],
        "reopening_rules": [
            "Market follows Directorate-General of Personnel Administration announcements",
            "If work suspension lifted by 10:00 AM → Market may open for afternoon",
        ],
        "notes": "TWSE follows government work suspension announcements"
    }
}


def get_typhoon_rules(market_code: str) -> Optional[Dict]:
    """Get typhoon closure rules for a market."""
    return TYPHOON_RULES.get(market_code.upper())


def add_typhoon_closure(
    closure_date: date,
    market_code: str,
    signal: TyphoonSignal,
    typhoon_name: str,
    notes: str = ""
) -> TyphoonClosure:
    """
    Add a typhoon closure to the system.
    
    Args:
        closure_date: Date of closure
        market_code: HK or TW
        signal: Typhoon signal level
        typhoon_name: Name of the typhoon
        notes: Additional notes
        
    Returns:
        TyphoonClosure object
    """
    closure = TyphoonClosure(
        date=closure_date,
        market_code=market_code.upper(),
        signal=signal,
        typhoon_name=typhoon_name,
        notes=notes
    )
    
    # Add to holiday system
    manager = get_holiday_manager()
    manager.manual_source.add_override(closure.to_manual_override())
    
    return closure


# =============================================================================
# 2. LUNAR NEW YEAR VARIATIONS
# =============================================================================

@dataclass
class LunarNewYearInfo:
    """Lunar New Year information for a specific year."""
    
    year: int
    lunar_new_year_date: date  # First day of Lunar New Year
    market_closures: Dict[str, List[date]] = field(default_factory=dict)
    
    def get_closure_dates(self, market_code: str) -> List[date]:
        """Get closure dates for a market."""
        return self.market_closures.get(market_code.upper(), [])


# Lunar New Year dates and typical market closures
# Note: These are approximate - actual closures vary by year and market
LUNAR_NEW_YEAR_DATA: Dict[int, Dict] = {
    2024: {
        "date": date(2024, 2, 10),
        "animal": "Dragon",
        "closures": {
            "CN": [date(2024, 2, 9), date(2024, 2, 10), date(2024, 2, 11), 
                   date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14),
                   date(2024, 2, 15), date(2024, 2, 16), date(2024, 2, 17)],
            "HK": [date(2024, 2, 10), date(2024, 2, 12), date(2024, 2, 13)],
            "TW": [date(2024, 2, 8), date(2024, 2, 9), date(2024, 2, 10),
                   date(2024, 2, 11), date(2024, 2, 12), date(2024, 2, 13), date(2024, 2, 14)],
            "SG": [date(2024, 2, 10), date(2024, 2, 12)],
            "KR": [date(2024, 2, 9), date(2024, 2, 10), date(2024, 2, 11), date(2024, 2, 12)],
        }
    },
    2025: {
        "date": date(2025, 1, 29),
        "animal": "Snake",
        "closures": {
            "CN": [date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
                   date(2025, 1, 31), date(2025, 2, 1), date(2025, 2, 2),
                   date(2025, 2, 3), date(2025, 2, 4)],
            "HK": [date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31)],
            "TW": [date(2025, 1, 27), date(2025, 1, 28), date(2025, 1, 29),
                   date(2025, 1, 30), date(2025, 1, 31)],
            "SG": [date(2025, 1, 29), date(2025, 1, 30)],
            "KR": [date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30)],
        }
    },
    2026: {
        "date": date(2026, 2, 17),
        "animal": "Horse",
        "closures": {
            "CN": [date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
                   date(2026, 2, 19), date(2026, 2, 20), date(2026, 2, 21),
                   date(2026, 2, 22), date(2026, 2, 23), date(2026, 2, 24)],
            "HK": [date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19)],
            "TW": [date(2026, 2, 14), date(2026, 2, 16), date(2026, 2, 17),
                   date(2026, 2, 18), date(2026, 2, 19), date(2026, 2, 20)],
            "SG": [date(2026, 2, 17), date(2026, 2, 18)],
            "KR": [date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18)],
        }
    },
    2027: {
        "date": date(2027, 2, 6),
        "animal": "Goat",
        "closures": {
            "CN": [date(2027, 2, 5), date(2027, 2, 6), date(2027, 2, 7),
                   date(2027, 2, 8), date(2027, 2, 9), date(2027, 2, 10),
                   date(2027, 2, 11)],
            "HK": [date(2027, 2, 6), date(2027, 2, 8), date(2027, 2, 9)],
            "TW": [date(2027, 2, 5), date(2027, 2, 6), date(2027, 2, 7),
                   date(2027, 2, 8), date(2027, 2, 9)],
            "SG": [date(2027, 2, 6), date(2027, 2, 8)],
            "KR": [date(2027, 2, 5), date(2027, 2, 6), date(2027, 2, 8)],
        }
    },
}


def get_lunar_new_year_info(year: int) -> Optional[LunarNewYearInfo]:
    """Get Lunar New Year information for a year."""
    data = LUNAR_NEW_YEAR_DATA.get(year)
    if not data:
        return None
    
    return LunarNewYearInfo(
        year=year,
        lunar_new_year_date=data["date"],
        market_closures=data["closures"]
    )


def get_lny_closure_dates(market_code: str, year: int) -> List[date]:
    """Get Lunar New Year closure dates for a market."""
    info = get_lunar_new_year_info(year)
    if not info:
        return []
    return info.get_closure_dates(market_code)


def is_lunar_new_year_period(check_date: date) -> bool:
    """Check if a date falls within Lunar New Year period (±2 weeks of LNY)."""
    info = get_lunar_new_year_info(check_date.year)
    if not info:
        return False
    
    lny = info.lunar_new_year_date
    return (lny - timedelta(days=7)) <= check_date <= (lny + timedelta(days=14))


# =============================================================================
# 3. HALF-DAY TRADING SESSIONS
# =============================================================================

@dataclass
class HalfDaySession:
    """Represents a half-day trading session."""
    
    date: date
    market_code: str
    reason: str
    morning_open: time
    morning_close: time
    afternoon_open: Optional[time] = None  # None = no afternoon session
    afternoon_close: Optional[time] = None
    
    @property
    def is_morning_only(self) -> bool:
        """Check if only morning session is open."""
        return self.afternoon_open is None
    
    @property
    def total_trading_minutes(self) -> int:
        """Calculate total trading minutes."""
        from datetime import datetime
        
        morning_mins = (
            datetime.combine(self.date, self.morning_close) -
            datetime.combine(self.date, self.morning_open)
        ).seconds // 60
        
        if self.afternoon_open and self.afternoon_close:
            afternoon_mins = (
                datetime.combine(self.date, self.afternoon_close) -
                datetime.combine(self.date, self.afternoon_open)
            ).seconds // 60
        else:
            afternoon_mins = 0
        
        return morning_mins + afternoon_mins


# Common half-day sessions by market
HALF_DAY_PATTERNS: Dict[str, Dict] = {
    "JP": {
        "name": "Tokyo Stock Exchange",
        "patterns": [
            {
                "occasion": "Last trading day of year",
                "description": "Market closes at 15:00 (normal hours)",
                "typical_dates": "Last business day of December",
                "morning_close": time(11, 30),
                "afternoon_close": time(15, 0),
            },
            {
                "occasion": "First trading day of year",  
                "description": "Opening ceremony, normal trading hours",
                "typical_dates": "First business day of January (usually Jan 4)",
                "morning_close": time(11, 30),
                "afternoon_close": time(15, 0),
            },
        ],
        "notes": "Japan rarely has half-day sessions"
    },
    "HK": {
        "name": "Hong Kong Stock Exchange",
        "patterns": [
            {
                "occasion": "Christmas Eve",
                "description": "Morning session only",
                "typical_dates": "December 24",
                "morning_close": time(12, 0),
                "afternoon_close": None,
            },
            {
                "occasion": "New Year's Eve",
                "description": "Morning session only (if trading day)",
                "typical_dates": "December 31",
                "morning_close": time(12, 0),
                "afternoon_close": None,
            },
            {
                "occasion": "Lunar New Year's Eve",
                "description": "Morning session only",
                "typical_dates": "Day before Lunar New Year",
                "morning_close": time(12, 0),
                "afternoon_close": None,
            },
        ],
        "notes": "HKEX announces half-day sessions in advance"
    },
    "SG": {
        "name": "Singapore Exchange",
        "patterns": [
            {
                "occasion": "Christmas Eve",
                "description": "Market closes early at 12:00",
                "typical_dates": "December 24",
                "morning_close": time(12, 0),
                "afternoon_close": None,
            },
            {
                "occasion": "New Year's Eve",
                "description": "Market closes early at 12:00",
                "typical_dates": "December 31",
                "morning_close": time(12, 0),
                "afternoon_close": None,
            },
        ],
        "notes": "SGX typically has few half-day sessions"
    },
    "AU": {
        "name": "Australian Securities Exchange",
        "patterns": [
            {
                "occasion": "Christmas Eve",
                "description": "Early close at 14:10 AEDT",
                "typical_dates": "December 24",
                "morning_close": time(14, 10),
                "afternoon_close": None,
            },
            {
                "occasion": "New Year's Eve",
                "description": "Early close at 14:10 AEDT",
                "typical_dates": "December 31",
                "morning_close": time(14, 10),
                "afternoon_close": None,
            },
        ],
        "notes": "ASX announces early closes in advance"
    },
}


def get_half_day_patterns(market_code: str) -> Optional[Dict]:
    """Get half-day session patterns for a market."""
    return HALF_DAY_PATTERNS.get(market_code.upper())


def get_known_half_days(market_code: str, year: int) -> List[HalfDaySession]:
    """
    Get known half-day sessions for a market in a year.
    
    Note: This returns commonly known half-days. Always verify with
    official exchange announcements.
    """
    market = market_code.upper()
    patterns = HALF_DAY_PATTERNS.get(market, {}).get("patterns", [])
    half_days = []
    
    for pattern in patterns:
        # Generate potential dates based on pattern
        # Note: Check "Lunar New Year" BEFORE "New Year's Eve" to avoid false match
        if "Christmas Eve" in pattern["occasion"]:
            potential_date = date(year, 12, 24)
        elif "Lunar New Year" in pattern["occasion"]:
            lny_info = get_lunar_new_year_info(year)
            if lny_info:
                potential_date = lny_info.lunar_new_year_date - timedelta(days=1)
            else:
                continue
        elif "New Year's Eve" in pattern["occasion"]:
            potential_date = date(year, 12, 31)
        else:
            continue
        
        # Skip weekends
        if potential_date.weekday() >= 5:
            continue
        
        half_days.append(HalfDaySession(
            date=potential_date,
            market_code=market,
            reason=pattern["occasion"],
            morning_open=time(9, 30),  # Default, varies by market
            morning_close=pattern.get("morning_close", time(12, 0)),
            afternoon_open=None if pattern.get("afternoon_close") is None else time(13, 0),
            afternoon_close=pattern.get("afternoon_close"),
        ))
    
    return half_days


# =============================================================================
# 4. POST-HOLIDAY SETTLEMENT ADJUSTMENTS
# =============================================================================

@dataclass
class SettlementAdjustment:
    """Represents a settlement date adjustment after holidays."""
    
    original_settlement_date: date
    adjusted_settlement_date: date
    market_code: str
    reason: str
    holiday_period: str
    additional_days: int
    
    @property
    def delay_description(self) -> str:
        """Get human-readable delay description."""
        if self.additional_days == 1:
            return "1 business day delay"
        return f"{self.additional_days} business days delay"


# Settlement adjustment rules
SETTLEMENT_ADJUSTMENT_RULES: Dict[str, Dict] = {
    "CN": {
        "name": "China",
        "rules": [
            {
                "period": "Lunar New Year",
                "description": "Extended closure (7-9 days) causes significant settlement delays",
                "typical_delay": "2-3 business days after reopening",
                "recommendation": "Avoid trades requiring settlement during LNY period"
            },
            {
                "period": "National Day Golden Week",
                "description": "Extended closure (7 days) causes settlement delays",
                "typical_delay": "1-2 business days after reopening",
                "recommendation": "Plan trades to settle before or well after the break"
            },
        ],
        "depository": "CSDC (China Securities Depository and Clearing)",
        "notes": "China has the longest holiday closures among major Asian markets"
    },
    "HK": {
        "name": "Hong Kong",
        "rules": [
            {
                "period": "Lunar New Year",
                "description": "3-day closure, potential backlog",
                "typical_delay": "Usually T+2 resumes normally",
                "recommendation": "Allow buffer for cross-border settlements with China"
            },
            {
                "period": "Typhoon closure",
                "description": "Unplanned closure may delay settlements",
                "typical_delay": "1 business day per closure day",
                "recommendation": "Monitor weather forecasts during typhoon season (Jun-Oct)"
            },
        ],
        "depository": "CCASS (Central Clearing And Settlement System)",
        "notes": "Stock Connect settlements follow both HK and mainland schedules"
    },
    "JP": {
        "name": "Japan",
        "rules": [
            {
                "period": "New Year (Shogatsu)",
                "description": "Markets closed Dec 31 - Jan 3",
                "typical_delay": "Minimal, usually resumes normally",
                "recommendation": "Complete year-end settlements by Dec 30"
            },
            {
                "period": "Golden Week",
                "description": "Multiple holidays late April - early May",
                "typical_delay": "May cause 1 day delay for cross-market trades",
                "recommendation": "Plan around consecutive holidays"
            },
        ],
        "depository": "JASDEC (Japan Securities Depository Center)",
        "notes": "Japan has reliable post-holiday settlement processing"
    },
    "KR": {
        "name": "Korea",
        "rules": [
            {
                "period": "Lunar New Year (Seollal)",
                "description": "3-day closure",
                "typical_delay": "Usually resumes normally",
                "recommendation": "Standard T+2 applies after holiday"
            },
            {
                "period": "Chuseok",
                "description": "3-day closure for Korean Thanksgiving",
                "typical_delay": "Usually resumes normally",
                "recommendation": "Plan for extended weekend effect"
            },
        ],
        "depository": "KSD (Korea Securities Depository)",
        "notes": "Korea has efficient post-holiday settlement"
    },
    "TW": {
        "name": "Taiwan",
        "rules": [
            {
                "period": "Lunar New Year",
                "description": "Extended closure (5-7 days)",
                "typical_delay": "1-2 business days after reopening",
                "recommendation": "Allow extra buffer for settlements"
            },
            {
                "period": "Typhoon closure",
                "description": "Unplanned closure delays settlements",
                "typical_delay": "1 business day per closure day",
                "recommendation": "Monitor DGPA announcements during typhoon season"
            },
        ],
        "depository": "TDCC (Taiwan Depository & Clearing Corporation)",
        "notes": "Taiwan follows government work suspension announcements"
    },
}


def get_settlement_adjustment_rules(market_code: str) -> Optional[Dict]:
    """Get settlement adjustment rules for a market."""
    return SETTLEMENT_ADJUSTMENT_RULES.get(market_code.upper())


def estimate_post_holiday_settlement(
    market_code: str,
    trade_date: date,
    normal_settlement_days: int = 2
) -> SettlementAdjustment:
    """
    Estimate settlement date considering post-holiday adjustments.
    
    Args:
        market_code: Market code
        trade_date: Date of trade
        normal_settlement_days: Normal T+N settlement cycle
        
    Returns:
        SettlementAdjustment with estimated dates
    """
    from app.data.holiday_sources import get_holiday_manager
    
    manager = get_holiday_manager()
    market = market_code.upper()
    
    # Calculate normal settlement date
    settlement_date = trade_date
    business_days_counted = 0
    
    while business_days_counted < normal_settlement_days:
        settlement_date += timedelta(days=1)
        if manager.is_trading_day(market, settlement_date):
            business_days_counted += 1
    
    # Check for holiday period impact
    holiday_period = ""
    additional_delay = 0
    
    # Check if trade is before major holiday
    if is_lunar_new_year_period(trade_date):
        holiday_period = "Lunar New Year"
        # Count closure days
        lny_info = get_lunar_new_year_info(trade_date.year)
        if lny_info:
            closures = lny_info.get_closure_dates(market)
            # If settlement would fall during or right after closures
            closure_impact = sum(1 for c in closures if trade_date < c <= settlement_date)
            if closure_impact > 2:
                additional_delay = 1  # Add buffer for processing backlog
    
    # Apply additional delay
    final_settlement = settlement_date
    for _ in range(additional_delay):
        final_settlement += timedelta(days=1)
        while not manager.is_trading_day(market, final_settlement):
            final_settlement += timedelta(days=1)
    
    return SettlementAdjustment(
        original_settlement_date=settlement_date,
        adjusted_settlement_date=final_settlement,
        market_code=market,
        reason=f"Post-{holiday_period} adjustment" if holiday_period else "No adjustment needed",
        holiday_period=holiday_period or "None",
        additional_days=additional_delay
    )


# =============================================================================
# UNIFIED SPECIAL CASES INTERFACE
# =============================================================================

class SpecialCasesManager:
    """
    Unified manager for all special market cases.
    
    Provides a single interface to check and handle:
    - Typhoon closures
    - Lunar New Year variations
    - Half-day sessions
    - Post-holiday settlement adjustments
    """
    
    def __init__(self):
        self.holiday_manager = get_holiday_manager()
    
    def check_special_conditions(
        self,
        market_code: str,
        check_date: date
    ) -> Dict:
        """
        Check all special conditions for a market on a date.
        
        Returns comprehensive status of special conditions.
        """
        market = market_code.upper()
        
        conditions = {
            "date": check_date.isoformat(),
            "market_code": market,
            "is_typhoon_season": self._is_typhoon_season(check_date),
            "is_lunar_new_year_period": is_lunar_new_year_period(check_date),
            "is_half_day": self._check_half_day(market, check_date),
            "warnings": [],
            "recommendations": []
        }
        
        # Typhoon season warning (Jun-Oct for HK/TW)
        if conditions["is_typhoon_season"] and market in ["HK", "TW"]:
            conditions["warnings"].append(
                f"Typhoon season - monitor {TYPHOON_RULES[market]['authority']} for warnings"
            )
            conditions["recommendations"].append(
                "Consider settlement buffer for potential unplanned closures"
            )
        
        # Lunar New Year warning
        if conditions["is_lunar_new_year_period"]:
            lny_info = get_lunar_new_year_info(check_date.year)
            if lny_info:
                closures = lny_info.get_closure_dates(market)
                if closures:
                    conditions["warnings"].append(
                        f"Lunar New Year period - {len(closures)} closure days expected"
                    )
                    conditions["recommendations"].append(
                        "Plan trades to settle before or well after LNY period"
                    )
        
        # Half-day warning
        if conditions["is_half_day"]:
            conditions["warnings"].append(
                "Half-day trading session - reduced trading hours"
            )
            conditions["recommendations"].append(
                "Complete trades before market close"
            )
        
        return conditions
    
    def _is_typhoon_season(self, check_date: date) -> bool:
        """Check if date is during typhoon season (June-October)."""
        return 6 <= check_date.month <= 10
    
    def _check_half_day(self, market_code: str, check_date: date) -> bool:
        """Check if date is a known half-day session."""
        half_days = get_known_half_days(market_code, check_date.year)
        return any(hd.date == check_date for hd in half_days)
    
    def get_cross_market_warnings(
        self,
        market_a: str,
        market_b: str,
        trade_date: date,
        settlement_date: date
    ) -> List[str]:
        """
        Get warnings for cross-market settlement.
        
        Considers both markets' special conditions.
        """
        warnings = []
        
        # Check each market
        for market in [market_a.upper(), market_b.upper()]:
            conditions = self.check_special_conditions(market, trade_date)
            
            # Add market-specific warnings
            for warning in conditions["warnings"]:
                warnings.append(f"[{market}] {warning}")
        
        # Cross-market specific warnings
        if market_a.upper() in ["HK", "CN"] or market_b.upper() in ["HK", "CN"]:
            if is_lunar_new_year_period(trade_date):
                warnings.append(
                    "[HK-CN] Stock Connect settlements follow both HK and mainland schedules during LNY"
                )
        
        return warnings
    
    def get_trading_calendar_summary(
        self,
        market_code: str,
        year: int
    ) -> Dict:
        """
        Get comprehensive trading calendar summary for a year.
        
        Includes holidays, half-days, and special periods.
        """
        market = market_code.upper()
        
        # Get holiday summary
        holiday_summary = self.holiday_manager.get_holiday_summary(market, year)
        
        # Get half-days
        half_days = get_known_half_days(market, year)
        
        # Get LNY info
        lny_info = get_lunar_new_year_info(year)
        lny_closures = lny_info.get_closure_dates(market) if lny_info else []
        
        return {
            "market_code": market,
            "year": year,
            "total_holidays": holiday_summary["total_holidays"],
            "half_day_sessions": len(half_days),
            "half_days": [
                {
                    "date": hd.date.isoformat(),
                    "reason": hd.reason,
                    "morning_close": hd.morning_close.isoformat() if hd.morning_close else None,
                }
                for hd in half_days
            ],
            "lunar_new_year": {
                "date": lny_info.lunar_new_year_date.isoformat() if lny_info else None,
                "closure_dates": [d.isoformat() for d in lny_closures]
            },
            "special_periods": {
                "typhoon_season": "June - October" if market in ["HK", "TW"] else "N/A",
                "golden_week": "Late April - Early May" if market == "JP" else "N/A",
                "national_day": "October 1-7" if market == "CN" else "N/A",
            }
        }


# Singleton instance
_special_cases_manager: Optional[SpecialCasesManager] = None


def get_special_cases_manager() -> SpecialCasesManager:
    """Get the singleton SpecialCasesManager instance."""
    global _special_cases_manager
    if _special_cases_manager is None:
        _special_cases_manager = SpecialCasesManager()
    return _special_cases_manager


def print_special_cases_report(market_code: str, year: int = 2026):
    """Print a special cases report for a market."""
    manager = get_special_cases_manager()
    summary = manager.get_trading_calendar_summary(market_code, year)
    
    print("=" * 70)
    print(f"SPECIAL CASES REPORT: {market_code} - {year}")
    print("=" * 70)
    
    print(f"\n📅 Total market holidays: {summary['total_holidays']}")
    print(f"⏰ Half-day sessions: {summary['half_day_sessions']}")
    
    if summary['half_days']:
        print("\n📋 Known Half-Day Sessions:")
        for hd in summary['half_days']:
            print(f"  - {hd['date']}: {hd['reason']} (closes {hd['morning_close']})")
    
    if summary['lunar_new_year']['date']:
        print(f"\n🧧 Lunar New Year: {summary['lunar_new_year']['date']}")
        if summary['lunar_new_year']['closure_dates']:
            print(f"   Closure dates: {', '.join(summary['lunar_new_year']['closure_dates'][:5])}...")
    
    print("\n⚠️  Special Periods:")
    for period, dates in summary['special_periods'].items():
        if dates != "N/A":
            print(f"  - {period.replace('_', ' ').title()}: {dates}")
    
    # Get rules
    typhoon_rules = get_typhoon_rules(market_code)
    if typhoon_rules:
        print(f"\n🌀 Typhoon Rules ({typhoon_rules['authority']}):")
        for rule in typhoon_rules['rules'][:2]:
            print(f"  - {rule['signal'].value}: {rule['market_action']}")
    
    settlement_rules = get_settlement_adjustment_rules(market_code)
    if settlement_rules:
        print(f"\n💰 Settlement Adjustments ({settlement_rules['depository']}):")
        for rule in settlement_rules['rules'][:2]:
            print(f"  - {rule['period']}: {rule['typical_delay']}")
    
    print("=" * 70)

"""
Data module for the Settlement Dashboard.

Provides data loading, validation, and access utilities.
"""

from app.data.data_loader import (
    DataLoader,
    MarketDataValidator,
    ExtendedMarketInfo,
    ExtendedTradingHours,
    DepositoryInfo,
    get_data_loader,
    load_all_markets,
    validate_market_data,
    get_market_info,
    print_market_summary,
)

from app.data.holiday_sources import (
    HolidaySourceType,
    HolidayInfo,
    ManualOverride,
    ExchangeCalendarSource,
    PublicHolidaySource,
    ManualOverrideSource,
    HolidayDataManager,
    get_holiday_manager,
    print_holiday_report,
)

from app.data.special_cases import (
    # Typhoon
    TyphoonSignal,
    TyphoonClosure,
    TYPHOON_RULES,
    get_typhoon_rules,
    add_typhoon_closure,
    # Lunar New Year
    LunarNewYearInfo,
    LUNAR_NEW_YEAR_DATA,
    get_lunar_new_year_info,
    get_lny_closure_dates,
    is_lunar_new_year_period,
    # Half-day sessions
    HalfDaySession,
    HALF_DAY_PATTERNS,
    get_half_day_patterns,
    get_known_half_days,
    # Settlement adjustments
    SettlementAdjustment,
    SETTLEMENT_ADJUSTMENT_RULES,
    get_settlement_adjustment_rules,
    estimate_post_holiday_settlement,
    # Unified manager
    SpecialCasesManager,
    get_special_cases_manager,
    print_special_cases_report,
)

__all__ = [
    # Data loader
    "DataLoader",
    "MarketDataValidator",
    "ExtendedMarketInfo",
    "ExtendedTradingHours",
    "DepositoryInfo",
    "get_data_loader",
    "load_all_markets",
    "validate_market_data",
    "get_market_info",
    "print_market_summary",
    # Holiday sources
    "HolidaySourceType",
    "HolidayInfo",
    "ManualOverride",
    "ExchangeCalendarSource",
    "PublicHolidaySource",
    "ManualOverrideSource",
    "HolidayDataManager",
    "get_holiday_manager",
    "print_holiday_report",
    # Special cases - Typhoon
    "TyphoonSignal",
    "TyphoonClosure",
    "TYPHOON_RULES",
    "get_typhoon_rules",
    "add_typhoon_closure",
    # Special cases - Lunar New Year
    "LunarNewYearInfo",
    "LUNAR_NEW_YEAR_DATA",
    "get_lunar_new_year_info",
    "get_lny_closure_dates",
    "is_lunar_new_year_period",
    # Special cases - Half-day
    "HalfDaySession",
    "HALF_DAY_PATTERNS",
    "get_half_day_patterns",
    "get_known_half_days",
    # Special cases - Settlement adjustments
    "SettlementAdjustment",
    "SETTLEMENT_ADJUSTMENT_RULES",
    "get_settlement_adjustment_rules",
    "estimate_post_holiday_settlement",
    # Special cases - Manager
    "SpecialCasesManager",
    "get_special_cases_manager",
    "print_special_cases_report",
]

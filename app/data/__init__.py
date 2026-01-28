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
]

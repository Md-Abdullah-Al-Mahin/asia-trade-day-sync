"""
Configuration settings for the Settlement Dashboard.
"""

from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"

# Market data file
MARKETS_CONFIG_FILE = DATA_DIR / "markets.json"

# Default timezone
DEFAULT_TIMEZONE = "UTC"

# Settlement cycles
DEFAULT_SETTLEMENT_CYCLE = 1  # T+1

# Supported instrument types
INSTRUMENT_TYPES = [
    "equity",
    "etf",
    "bond",
]

# Status codes for settlement check
class SettlementStatus:
    LIKELY = "LIKELY"
    AT_RISK = "AT_RISK"
    UNLIKELY = "UNLIKELY"


# Exchange calendar codes mapping (exchange_calendars library)
EXCHANGE_CALENDAR_CODES = {
    "JP": "XTKS",   # Tokyo Stock Exchange
    "HK": "XHKG",   # Hong Kong Stock Exchange
    "SG": "XSES",   # Singapore Exchange
    "IN": "XNSE",   # National Stock Exchange of India
    "AU": "XASX",   # Australian Securities Exchange
    "KR": "XKRX",   # Korea Exchange
    "TW": "XTAI",   # Taiwan Stock Exchange
    "CN": "XSHG",   # Shanghai Stock Exchange
}

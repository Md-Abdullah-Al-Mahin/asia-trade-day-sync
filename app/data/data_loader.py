"""
Data loader and validator for market configuration.

This module provides utilities for loading, validating, and accessing
market configuration data from the JSON files.
"""

import json
from datetime import time, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from zoneinfo import ZoneInfo


@dataclass
class DepositoryInfo:
    """Depository information for a market."""
    
    name: str
    cut_off_time: time
    notes: Optional[str] = None


@dataclass
class PreAfterHours:
    """Pre-market or after-hours trading session."""
    
    start: time
    end: time


@dataclass
class ExtendedTradingHours:
    """Extended trading hours information including pre/after market."""
    
    open: time
    close: time
    lunch_break_start: Optional[time] = None
    lunch_break_end: Optional[time] = None
    pre_market: Optional[PreAfterHours] = None
    after_hours: Optional[PreAfterHours] = None
    
    @property
    def has_lunch_break(self) -> bool:
        return self.lunch_break_start is not None
    
    @property
    def has_pre_market(self) -> bool:
        return self.pre_market is not None
    
    @property
    def has_after_hours(self) -> bool:
        return self.after_hours is not None


@dataclass
class ExtendedMarketInfo:
    """Extended market information from JSON config."""
    
    code: str
    name: str
    exchange_name: str
    exchange_code: str
    exchange_calendar_code: str
    timezone: str
    utc_offset: str
    trading_hours: ExtendedTradingHours
    settlement_cycle: int
    currency: str
    depository: DepositoryInfo
    special_notes: List[str] = field(default_factory=list)
    website: Optional[str] = None
    
    @property
    def depository_cut_off(self) -> time:
        """Get depository cut-off time."""
        return self.depository.cut_off_time


@dataclass
class ValidationError:
    """Represents a validation error."""
    
    market_code: str
    field: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class ValidationResult:
    """Result of data validation."""
    
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        return len(self.warnings)


class MarketDataValidator:
    """Validates market configuration data."""
    
    REQUIRED_FIELDS = [
        "code", "name", "exchange_name", "exchange_calendar_code",
        "timezone", "trading_hours", "settlement_cycle", "currency"
    ]
    
    VALID_CURRENCIES = ["JPY", "HKD", "SGD", "INR", "AUD", "KRW", "TWD", "CNY", "USD", "EUR"]
    
    def validate(self, markets_data: Dict) -> ValidationResult:
        """
        Validate the entire markets configuration.
        
        Args:
            markets_data: Parsed JSON data
            
        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        
        # Check top-level structure
        if "markets" not in markets_data:
            errors.append(ValidationError(
                market_code="*",
                field="markets",
                message="Missing 'markets' array in configuration"
            ))
            return ValidationResult(is_valid=False, errors=errors)
        
        markets = markets_data["markets"]
        seen_codes = set()
        
        for market in markets:
            market_errors, market_warnings = self._validate_market(market, seen_codes)
            errors.extend(market_errors)
            warnings.extend(market_warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_market(
        self, 
        market: Dict, 
        seen_codes: set
    ) -> tuple:
        """Validate a single market entry."""
        errors = []
        warnings = []
        
        code = market.get("code", "UNKNOWN")
        
        # Check required fields
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in market:
                errors.append(ValidationError(
                    market_code=code,
                    field=field_name,
                    message=f"Missing required field: {field_name}"
                ))
        
        # Check for duplicate codes
        if code in seen_codes:
            errors.append(ValidationError(
                market_code=code,
                field="code",
                message=f"Duplicate market code: {code}"
            ))
        seen_codes.add(code)
        
        # Validate timezone
        timezone = market.get("timezone")
        if timezone:
            try:
                ZoneInfo(timezone)
            except KeyError:
                errors.append(ValidationError(
                    market_code=code,
                    field="timezone",
                    message=f"Invalid timezone: {timezone}"
                ))
        
        # Validate currency
        currency = market.get("currency")
        if currency and currency not in self.VALID_CURRENCIES:
            warnings.append(ValidationError(
                market_code=code,
                field="currency",
                message=f"Uncommon currency code: {currency}",
                severity="warning"
            ))
        
        # Validate trading hours
        trading_hours = market.get("trading_hours", {})
        if trading_hours:
            th_errors = self._validate_trading_hours(code, trading_hours)
            errors.extend(th_errors)
        
        # Validate settlement cycle
        settlement_cycle = market.get("settlement_cycle")
        if settlement_cycle is not None:
            if not isinstance(settlement_cycle, int) or settlement_cycle < 0 or settlement_cycle > 5:
                errors.append(ValidationError(
                    market_code=code,
                    field="settlement_cycle",
                    message=f"Invalid settlement cycle: {settlement_cycle} (must be 0-5)"
                ))
        
        # Check for depository info
        if "depository" not in market:
            warnings.append(ValidationError(
                market_code=code,
                field="depository",
                message="Missing depository information",
                severity="warning"
            ))
        
        return errors, warnings
    
    def _validate_trading_hours(self, code: str, hours: Dict) -> List[ValidationError]:
        """Validate trading hours configuration."""
        errors = []
        
        # Check required fields
        if "open" not in hours:
            errors.append(ValidationError(
                market_code=code,
                field="trading_hours.open",
                message="Missing market open time"
            ))
        
        if "close" not in hours:
            errors.append(ValidationError(
                market_code=code,
                field="trading_hours.close",
                message="Missing market close time"
            ))
        
        # Validate time format
        for field_name in ["open", "close"]:
            if field_name in hours:
                try:
                    self._parse_time(hours[field_name])
                except ValueError:
                    errors.append(ValidationError(
                        market_code=code,
                        field=f"trading_hours.{field_name}",
                        message=f"Invalid time format: {hours[field_name]}"
                    ))
        
        # Validate lunch break if present
        lunch = hours.get("lunch_break")
        if lunch:
            for field_name in ["start", "end"]:
                if field_name not in lunch:
                    errors.append(ValidationError(
                        market_code=code,
                        field=f"trading_hours.lunch_break.{field_name}",
                        message=f"Missing lunch break {field_name} time"
                    ))
                else:
                    try:
                        self._parse_time(lunch[field_name])
                    except ValueError:
                        errors.append(ValidationError(
                            market_code=code,
                            field=f"trading_hours.lunch_break.{field_name}",
                            message=f"Invalid time format: {lunch[field_name]}"
                        ))
        
        return errors
    
    def _parse_time(self, time_str: str) -> time:
        """Parse a time string in HH:MM format."""
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}")
        return time(int(parts[0]), int(parts[1]))


class DataLoader:
    """
    Loads and provides access to market configuration data.
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the data loader.
        
        Args:
            data_dir: Path to data directory. Defaults to app/data.
        """
        if data_dir is None:
            data_dir = Path(__file__).parent
        
        self._data_dir = data_dir
        self._markets_file = data_dir / "markets.json"
        self._validator = MarketDataValidator()
        self._markets_data: Optional[Dict] = None
        self._markets_cache: Dict[str, ExtendedMarketInfo] = {}
    
    def load_markets_data(self) -> Dict:
        """
        Load raw markets data from JSON file.
        
        Returns:
            Parsed JSON data
        """
        if self._markets_data is not None:
            return self._markets_data
        
        if not self._markets_file.exists():
            raise FileNotFoundError(
                f"Markets configuration file not found: {self._markets_file}"
            )
        
        with open(self._markets_file, "r") as f:
            self._markets_data = json.load(f)
        
        return self._markets_data
    
    def validate(self) -> ValidationResult:
        """
        Validate the markets configuration.
        
        Returns:
            ValidationResult with any errors or warnings
        """
        data = self.load_markets_data()
        return self._validator.validate(data)
    
    def get_all_markets(self) -> List[ExtendedMarketInfo]:
        """
        Get all markets as ExtendedMarketInfo objects.
        
        Returns:
            List of ExtendedMarketInfo objects
        """
        data = self.load_markets_data()
        markets = []
        
        for market_data in data.get("markets", []):
            market = self._parse_market(market_data)
            markets.append(market)
            self._markets_cache[market.code] = market
        
        return markets
    
    def get_market(self, code: str) -> Optional[ExtendedMarketInfo]:
        """
        Get a specific market by code.
        
        Args:
            code: Market code (e.g., 'JP', 'HK')
            
        Returns:
            ExtendedMarketInfo or None if not found
        """
        code = code.upper()
        
        if code in self._markets_cache:
            return self._markets_cache[code]
        
        # Load all markets to populate cache
        self.get_all_markets()
        
        return self._markets_cache.get(code)
    
    def get_market_codes(self) -> List[str]:
        """Get list of all market codes."""
        data = self.load_markets_data()
        return [m["code"] for m in data.get("markets", [])]
    
    def get_metadata(self) -> Dict:
        """Get configuration metadata."""
        data = self.load_markets_data()
        return {
            "version": data.get("version"),
            "last_updated": data.get("last_updated"),
            "description": data.get("description"),
            **data.get("metadata", {})
        }
    
    def _parse_market(self, data: Dict) -> ExtendedMarketInfo:
        """Parse a market entry into ExtendedMarketInfo."""
        
        # Parse trading hours
        th = data.get("trading_hours", {})
        trading_hours = ExtendedTradingHours(
            open=self._parse_time(th.get("open", "09:00")),
            close=self._parse_time(th.get("close", "17:00")),
            lunch_break_start=self._parse_time(th["lunch_break"]["start"]) if th.get("lunch_break") else None,
            lunch_break_end=self._parse_time(th["lunch_break"]["end"]) if th.get("lunch_break") else None,
            pre_market=self._parse_session(th.get("pre_market")),
            after_hours=self._parse_session(th.get("after_hours"))
        )
        
        # Parse depository info
        dep = data.get("depository", {})
        depository = DepositoryInfo(
            name=dep.get("name", "Unknown"),
            cut_off_time=self._parse_time(dep.get("cut_off_time", data.get("depository_cut_off", "16:00"))),
            notes=dep.get("notes")
        )
        
        return ExtendedMarketInfo(
            code=data["code"],
            name=data["name"],
            exchange_name=data["exchange_name"],
            exchange_code=data.get("exchange_code", data["code"]),
            exchange_calendar_code=data["exchange_calendar_code"],
            timezone=data["timezone"],
            utc_offset=data.get("utc_offset", ""),
            trading_hours=trading_hours,
            settlement_cycle=data.get("settlement_cycle", 1),
            currency=data["currency"],
            depository=depository,
            special_notes=data.get("special_notes", []),
            website=data.get("website")
        )
    
    def _parse_time(self, time_str: str) -> time:
        """Parse a time string in HH:MM format."""
        if not time_str:
            return time(0, 0)
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    
    def _parse_session(self, session_data: Optional[Dict]) -> Optional[PreAfterHours]:
        """Parse a pre/after market session."""
        if not session_data:
            return None
        return PreAfterHours(
            start=self._parse_time(session_data.get("start", "00:00")),
            end=self._parse_time(session_data.get("end", "00:00"))
        )


# Singleton instance
_data_loader: Optional[DataLoader] = None


def get_data_loader() -> DataLoader:
    """Get the singleton DataLoader instance."""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
    return _data_loader


def load_all_markets() -> List[ExtendedMarketInfo]:
    """Convenience function to load all markets."""
    return get_data_loader().get_all_markets()


def validate_market_data() -> ValidationResult:
    """Convenience function to validate market data."""
    return get_data_loader().validate()


def get_market_info(code: str) -> Optional[ExtendedMarketInfo]:
    """Convenience function to get market info."""
    return get_data_loader().get_market(code)


def print_market_summary():
    """Print a summary of all configured markets."""
    loader = get_data_loader()
    
    # Validate first
    validation = loader.validate()
    
    print("=" * 70)
    print("MARKET DATA SUMMARY")
    print("=" * 70)
    
    # Print metadata
    metadata = loader.get_metadata()
    print(f"\nVersion: {metadata.get('version', 'N/A')}")
    print(f"Last Updated: {metadata.get('last_updated', 'N/A')}")
    print(f"Description: {metadata.get('description', 'N/A')}")
    
    # Print validation status
    print(f"\nValidation: {'✓ PASSED' if validation.is_valid else '✗ FAILED'}")
    if validation.errors:
        print(f"  Errors: {validation.error_count}")
        for err in validation.errors:
            print(f"    - [{err.market_code}] {err.field}: {err.message}")
    if validation.warnings:
        print(f"  Warnings: {validation.warning_count}")
        for warn in validation.warnings[:5]:  # Show first 5
            print(f"    - [{warn.market_code}] {warn.field}: {warn.message}")
    
    # Print markets
    print("\n" + "-" * 70)
    print("CONFIGURED MARKETS")
    print("-" * 70)
    
    markets = loader.get_all_markets()
    
    for market in markets:
        print(f"\n{market.code} - {market.name}")
        print(f"  Exchange: {market.exchange_name} ({market.exchange_code})")
        print(f"  Timezone: {market.timezone} ({market.utc_offset})")
        print(f"  Currency: {market.currency}")
        print(f"  Trading: {market.trading_hours.open.strftime('%H:%M')} - {market.trading_hours.close.strftime('%H:%M')}")
        if market.trading_hours.has_lunch_break:
            print(f"  Lunch: {market.trading_hours.lunch_break_start.strftime('%H:%M')} - {market.trading_hours.lunch_break_end.strftime('%H:%M')}")
        print(f"  Settlement: T+{market.settlement_cycle}")
        print(f"  Depository: {market.depository.name}")
        print(f"  Cut-off: {market.depository.cut_off_time.strftime('%H:%M')}")
        if market.special_notes:
            print(f"  Notes: {market.special_notes[0]}")
    
    print("\n" + "=" * 70)
    print(f"Total markets: {len(markets)}")
    print("=" * 70)


if __name__ == "__main__":
    print_market_summary()

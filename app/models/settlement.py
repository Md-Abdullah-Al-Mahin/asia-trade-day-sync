"""
Settlement calculation models.

This module defines data structures for settlement check requests,
results, market status, and related information.
"""

from datetime import date as date_type, datetime, time, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, computed_field, model_validator

from app.config import INSTRUMENT_TYPES


class SettlementStatusEnum(str, Enum):
    """Settlement status codes."""
    
    LIKELY = "LIKELY"
    AT_RISK = "AT_RISK"
    UNLIKELY = "UNLIKELY"
    
    @property
    def emoji(self) -> str:
        """Get emoji representation of status."""
        return {
            self.LIKELY: "🟢",
            self.AT_RISK: "🟡",
            self.UNLIKELY: "🔴",
        }[self]
    
    @property
    def color(self) -> str:
        """Get color for UI display."""
        return {
            self.LIKELY: "green",
            self.AT_RISK: "yellow",
            self.UNLIKELY: "red",
        }[self]
    
    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return {
            self.LIKELY: "Settlement Likely",
            self.AT_RISK: "Settlement At Risk",
            self.UNLIKELY: "Settlement Unlikely",
        }[self]


class DeadlineType(str, Enum):
    """Types of settlement-related deadlines."""
    
    DEPOSITORY_CUT_OFF = "depository_cut_off"
    TRADE_CONFIRMATION = "trade_confirmation"
    INSTRUCTION_SUBMISSION = "instruction_submission"
    MARKET_CLOSE = "market_close"
    SETTLEMENT_CUT_OFF = "settlement_cut_off"


class SettlementCheckRequest(BaseModel):
    """
    Request model for settlement check.
    
    Contains all information needed to determine settlement viability
    for a cross-market trade.
    """
    
    trade_date: date_type = Field(..., description="Trade date (T)")
    buy_market: str = Field(..., description="Buy-side market code")
    sell_market: str = Field(..., description="Sell-side market code")
    execution_time: Optional[datetime] = Field(
        None, description="Trade execution time (with timezone)"
    )
    instrument_type: str = Field(
        default="equity", description="Instrument type (equity, etf, bond)"
    )
    
    @field_validator("buy_market", "sell_market")
    @classmethod
    def validate_market_code(cls, v: str) -> str:
        """Ensure market code is uppercase."""
        return v.upper().strip()
    
    @field_validator("instrument_type")
    @classmethod
    def validate_instrument_type(cls, v: str) -> str:
        """Validate instrument type."""
        v = v.lower().strip()
        if v not in INSTRUMENT_TYPES:
            raise ValueError(
                f"Invalid instrument type: {v}. "
                f"Must be one of: {', '.join(INSTRUMENT_TYPES)}"
            )
        return v
    
    @model_validator(mode="after")
    def validate_markets_different(self):
        """Ensure buy and sell markets are different."""
        if self.buy_market == self.sell_market:
            raise ValueError("Buy and sell markets must be different")
        return self
    
    @computed_field
    @property
    def market_pair(self) -> str:
        """Get market pair string (e.g., 'JP-HK')."""
        return f"{self.buy_market}-{self.sell_market}"
    
    @computed_field
    @property
    def has_execution_time(self) -> bool:
        """Check if execution time was provided."""
        return self.execution_time is not None
    
    class Config:
        json_schema_extra = {
            "example": {
                "trade_date": "2026-01-28",
                "buy_market": "JP",
                "sell_market": "HK",
                "execution_time": "2026-01-28T10:30:00+09:00",
                "instrument_type": "equity",
            }
        }


class Deadline(BaseModel):
    """
    A settlement-related deadline.
    
    Represents a critical time by which an action must be completed
    for successful settlement.
    """
    
    market_code: str = Field(..., description="Market code")
    deadline_type: DeadlineType = Field(..., description="Type of deadline")
    deadline_time: datetime = Field(..., description="Deadline time (UTC)")
    local_time: time = Field(..., description="Deadline in local time")
    description: str = Field(..., description="Deadline description")
    is_passed: bool = Field(
        default=False, description="Whether deadline has passed"
    )
    time_remaining: Optional[str] = Field(
        None, description="Human-readable time remaining"
    )
    
    @field_validator("market_code")
    @classmethod
    def validate_market_code(cls, v: str) -> str:
        """Ensure market code is uppercase."""
        return v.upper().strip()
    
    @computed_field
    @property
    def local_time_formatted(self) -> str:
        """Get formatted local time string."""
        return self.local_time.strftime("%H:%M")
    
    @classmethod
    def create(
        cls,
        market_code: str,
        deadline_type: DeadlineType,
        deadline_utc: datetime,
        local_time: time,
        description: Optional[str] = None,
        current_time: Optional[datetime] = None
    ) -> "Deadline":
        """
        Factory method to create a Deadline with automatic calculations.
        
        Args:
            market_code: Market code
            deadline_type: Type of deadline
            deadline_utc: Deadline time in UTC
            local_time: Deadline in local market time
            description: Optional description (auto-generated if None)
            current_time: Current UTC time for calculating is_passed
        """
        if description is None:
            description = f"{deadline_type.value.replace('_', ' ').title()} for {market_code}"
        
        is_passed = False
        time_remaining = None
        
        if current_time:
            is_passed = current_time > deadline_utc
            if not is_passed:
                delta = deadline_utc - current_time
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes = remainder // 60
                if hours > 0:
                    time_remaining = f"{hours}h {minutes}m"
                else:
                    time_remaining = f"{minutes}m"
        
        return cls(
            market_code=market_code,
            deadline_type=deadline_type,
            deadline_time=deadline_utc,
            local_time=local_time,
            description=description,
            is_passed=is_passed,
            time_remaining=time_remaining
        )


class MarketDayInfo(BaseModel):
    """Information about a market for a specific date."""
    
    market_code: str = Field(..., description="Market code")
    date: date_type = Field(..., description="Date")
    is_trading_day: bool = Field(..., description="Whether market is open")
    is_settlement_day: bool = Field(..., description="Whether settlement occurs")
    holiday_name: Optional[str] = Field(None, description="Holiday name if applicable")
    trading_hours_start: Optional[time] = Field(None, description="Market open time")
    trading_hours_end: Optional[time] = Field(None, description="Market close time")
    
    @computed_field
    @property
    def status_text(self) -> str:
        """Get human-readable status."""
        if not self.is_trading_day:
            if self.holiday_name:
                return f"Closed ({self.holiday_name})"
            return "Closed"
        return "Open"


class SettlementDetails(BaseModel):
    """Detailed breakdown of settlement calculation."""
    
    # Trade date info
    trade_date_buy_market: MarketDayInfo = Field(
        ..., description="Trade date info for buy market"
    )
    trade_date_sell_market: MarketDayInfo = Field(
        ..., description="Trade date info for sell market"
    )
    
    # Settlement date info  
    settlement_date_buy_market: Optional[MarketDayInfo] = Field(
        None, description="Settlement date info for buy market"
    )
    settlement_date_sell_market: Optional[MarketDayInfo] = Field(
        None, description="Settlement date info for sell market"
    )
    
    # Overlap info
    has_trading_overlap: bool = Field(
        default=False, description="Whether markets have overlapping trading hours"
    )
    overlap_start_utc: Optional[datetime] = Field(
        None, description="Start of overlap window (UTC)"
    )
    overlap_end_utc: Optional[datetime] = Field(
        None, description="End of overlap window (UTC)"
    )
    overlap_duration_minutes: Optional[int] = Field(
        None, description="Duration of overlap in minutes"
    )
    
    # Execution info
    execution_time_valid: Optional[bool] = Field(
        None, description="Whether execution time is within valid window"
    )
    execution_before_cut_off: Optional[bool] = Field(
        None, description="Whether execution is before all cut-offs"
    )
    
    @computed_field
    @property
    def both_markets_open_trade_date(self) -> bool:
        """Check if both markets are open on trade date."""
        return (
            self.trade_date_buy_market.is_trading_day and 
            self.trade_date_sell_market.is_trading_day
        )
    
    @computed_field
    @property
    def both_markets_open_settlement_date(self) -> bool:
        """Check if both markets are open on settlement date."""
        if not self.settlement_date_buy_market or not self.settlement_date_sell_market:
            return False
        return (
            self.settlement_date_buy_market.is_settlement_day and
            self.settlement_date_sell_market.is_settlement_day
        )


class SettlementResult(BaseModel):
    """
    Result of settlement check.
    
    Contains the settlement status, message, and all relevant details
    about the settlement calculation.
    """
    
    status: SettlementStatusEnum = Field(..., description="Settlement status")
    message: str = Field(..., description="Human-readable status message")
    trade_date: date_type = Field(..., description="Trade date (T)")
    settlement_date: Optional[date_type] = Field(
        None, description="Expected settlement date"
    )
    buy_market: str = Field(..., description="Buy-side market code")
    sell_market: str = Field(..., description="Sell-side market code")
    deadlines: List[Deadline] = Field(
        default_factory=list, description="Relevant deadlines"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Warning messages"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommended actions"
    )
    details: Optional[SettlementDetails] = Field(
        None, description="Detailed breakdown"
    )
    
    @field_validator("buy_market", "sell_market")
    @classmethod
    def validate_market_code(cls, v: str) -> str:
        """Ensure market code is uppercase."""
        return v.upper().strip()
    
    @computed_field
    @property
    def market_pair(self) -> str:
        """Get market pair string."""
        return f"{self.buy_market}-{self.sell_market}"
    
    @computed_field
    @property
    def status_emoji(self) -> str:
        """Get status emoji."""
        return self.status.emoji
    
    @computed_field
    @property
    def status_color(self) -> str:
        """Get status color."""
        return self.status.color
    
    @computed_field
    @property
    def settlement_cycle_label(self) -> str:
        """Get settlement cycle label."""
        if self.trade_date and self.settlement_date:
            days = (self.settlement_date - self.trade_date).days
            return f"T+{days}"
        return "T+?"
    
    @computed_field
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0
    
    @computed_field
    @property
    def has_passed_deadlines(self) -> bool:
        """Check if any deadlines have passed."""
        return any(d.is_passed for d in self.deadlines)
    
    @classmethod
    def create_likely(
        cls,
        trade_date: date_type,
        settlement_date: date_type,
        buy_market: str,
        sell_market: str,
        message: Optional[str] = None,
        deadlines: Optional[List[Deadline]] = None,
        details: Optional[SettlementDetails] = None
    ) -> "SettlementResult":
        """Factory method for LIKELY result."""
        if message is None:
            message = (
                f"Settlement expected on {settlement_date}. "
                f"Both {buy_market} and {sell_market} markets are open for trading and settlement."
            )
        
        return cls(
            status=SettlementStatusEnum.LIKELY,
            message=message,
            trade_date=trade_date,
            settlement_date=settlement_date,
            buy_market=buy_market,
            sell_market=sell_market,
            deadlines=deadlines or [],
            recommendations=[
                f"Ensure trade instructions are submitted before cut-off times",
                f"Monitor both markets for any unexpected closures"
            ],
            details=details
        )
    
    @classmethod
    def create_at_risk(
        cls,
        trade_date: date_type,
        settlement_date: date_type,
        buy_market: str,
        sell_market: str,
        message: str,
        warnings: List[str],
        deadlines: Optional[List[Deadline]] = None,
        details: Optional[SettlementDetails] = None
    ) -> "SettlementResult":
        """Factory method for AT_RISK result."""
        return cls(
            status=SettlementStatusEnum.AT_RISK,
            message=message,
            trade_date=trade_date,
            settlement_date=settlement_date,
            buy_market=buy_market,
            sell_market=sell_market,
            deadlines=deadlines or [],
            warnings=warnings,
            recommendations=[
                "Immediate action required for trade confirmation",
                "Contact counterparty to ensure timely processing",
                "Consider alternative execution timing if possible"
            ],
            details=details
        )
    
    @classmethod
    def create_unlikely(
        cls,
        trade_date: date_type,
        buy_market: str,
        sell_market: str,
        message: str,
        next_viable_date: Optional[date_type] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[SettlementDetails] = None
    ) -> "SettlementResult":
        """Factory method for UNLIKELY result."""
        recommendations = [
            "Consider postponing trade to next common business day"
        ]
        if next_viable_date:
            recommendations.append(
                f"Next viable trade date: {next_viable_date}"
            )
        
        return cls(
            status=SettlementStatusEnum.UNLIKELY,
            message=message,
            trade_date=trade_date,
            settlement_date=None,
            buy_market=buy_market,
            sell_market=sell_market,
            warnings=warnings or [],
            recommendations=recommendations,
            details=details
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "LIKELY",
                "message": "Settlement expected on 2026-01-29. Both JP and HK markets are open.",
                "trade_date": "2026-01-28",
                "settlement_date": "2026-01-29",
                "buy_market": "JP",
                "sell_market": "HK",
                "deadlines": [],
                "warnings": [],
                "recommendations": [],
                "details": None,
            }
        }


class MarketStatus(BaseModel):
    """
    Current status of a market.
    
    Provides real-time information about market state, session,
    and upcoming events.
    """
    
    market_code: str = Field(..., description="Market code")
    market_name: str = Field(..., description="Market name")
    timezone: str = Field(..., description="Market timezone")
    is_open: bool = Field(..., description="Whether market is currently open")
    current_session: str = Field(
        ..., description="Current session (pre_market, morning, lunch, afternoon, post_market)"
    )
    local_time: datetime = Field(..., description="Current local time")
    local_date: date_type = Field(..., description="Current local date")
    
    # Trading hours
    trading_hours_open: Optional[time] = Field(
        None, description="Today's market open time"
    )
    trading_hours_close: Optional[time] = Field(
        None, description="Today's market close time"
    )
    
    # Next events
    next_open: Optional[datetime] = Field(
        None, description="Next market open time (if currently closed)"
    )
    next_close: Optional[datetime] = Field(
        None, description="Next market close time (if currently open)"
    )
    time_until_next_event: Optional[str] = Field(
        None, description="Human-readable time until next open/close"
    )
    
    # Holiday info
    is_holiday: bool = Field(
        default=False, description="Whether today is a holiday"
    )
    holiday_name: Optional[str] = Field(
        None, description="Holiday name if applicable"
    )
    is_weekend: bool = Field(
        default=False, description="Whether today is a weekend"
    )
    
    # Cut-off info
    depository_cut_off: Optional[time] = Field(
        None, description="Depository cut-off time"
    )
    is_before_cut_off: bool = Field(
        default=True, description="Whether current time is before cut-off"
    )
    time_until_cut_off: Optional[str] = Field(
        None, description="Time remaining until cut-off"
    )
    
    @field_validator("market_code")
    @classmethod
    def validate_market_code(cls, v: str) -> str:
        """Ensure market code is uppercase."""
        return v.upper().strip()
    
    @computed_field
    @property
    def status_text(self) -> str:
        """Get human-readable status text."""
        if self.is_holiday:
            return f"Closed - {self.holiday_name}"
        if self.is_weekend:
            return "Closed - Weekend"
        if self.is_open:
            return f"Open ({self.current_session.replace('_', ' ').title()})"
        return f"Closed ({self.current_session.replace('_', ' ').title()})"
    
    @computed_field
    @property
    def can_trade_today(self) -> bool:
        """Check if trading is possible today."""
        return not self.is_holiday and not self.is_weekend
    
    class Config:
        json_schema_extra = {
            "example": {
                "market_code": "JP",
                "market_name": "Japan",
                "timezone": "Asia/Tokyo",
                "is_open": True,
                "current_session": "morning",
                "local_time": "2026-01-28T10:30:00+09:00",
                "local_date": "2026-01-28",
                "trading_hours_open": "09:00",
                "trading_hours_close": "15:00",
                "is_holiday": False,
                "is_weekend": False,
                "depository_cut_off": "14:00",
                "is_before_cut_off": True,
            }
        }


class MarketPairComparison(BaseModel):
    """
    Comparison of two markets for settlement analysis.
    
    Shows the relationship between two markets including timezone
    differences and trading hour overlaps.
    """
    
    market_a: MarketStatus = Field(..., description="First market status")
    market_b: MarketStatus = Field(..., description="Second market status")
    
    # Timezone comparison
    timezone_difference_hours: float = Field(
        ..., description="Timezone difference (A - B) in hours"
    )
    
    # Trading overlap
    has_trading_overlap: bool = Field(
        ..., description="Whether markets have overlapping trading hours today"
    )
    overlap_start_local_a: Optional[time] = Field(
        None, description="Overlap start in market A local time"
    )
    overlap_end_local_a: Optional[time] = Field(
        None, description="Overlap end in market A local time"
    )
    overlap_duration_minutes: Optional[int] = Field(
        None, description="Total overlap duration in minutes"
    )
    
    # Common trading status
    both_open_now: bool = Field(
        ..., description="Whether both markets are currently open"
    )
    both_trading_today: bool = Field(
        ..., description="Whether both markets are trading today"
    )
    
    @computed_field
    @property
    def market_pair(self) -> str:
        """Get market pair string."""
        return f"{self.market_a.market_code}-{self.market_b.market_code}"
    
    @computed_field
    @property
    def overlap_summary(self) -> str:
        """Get human-readable overlap summary."""
        if not self.has_trading_overlap:
            return "No trading hour overlap"
        if self.overlap_duration_minutes:
            hours = self.overlap_duration_minutes // 60
            mins = self.overlap_duration_minutes % 60
            if hours > 0:
                return f"{hours}h {mins}m overlap"
            return f"{mins}m overlap"
        return "Overlap exists"

"""
Settlement calculation models.
"""

from datetime import date, datetime, time
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class SettlementStatusEnum(str, Enum):
    """Settlement status codes."""
    
    LIKELY = "LIKELY"
    AT_RISK = "AT_RISK"
    UNLIKELY = "UNLIKELY"


class SettlementCheckRequest(BaseModel):
    """Request model for settlement check."""
    
    trade_date: date = Field(..., description="Trade date (T)")
    buy_market: str = Field(..., description="Buy-side market code")
    sell_market: str = Field(..., description="Sell-side market code")
    execution_time: Optional[datetime] = Field(
        None, description="Trade execution time (with timezone)"
    )
    instrument_type: str = Field(
        default="equity", description="Instrument type (equity, etf, bond)"
    )
    
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
    """A settlement-related deadline."""
    
    market_code: str = Field(..., description="Market code")
    deadline_type: str = Field(..., description="Type of deadline")
    deadline_time: datetime = Field(..., description="Deadline time (UTC)")
    local_time: time = Field(..., description="Deadline in local time")
    description: str = Field(..., description="Deadline description")


class SettlementResult(BaseModel):
    """Result of settlement check."""
    
    status: SettlementStatusEnum = Field(..., description="Settlement status")
    message: str = Field(..., description="Human-readable status message")
    trade_date: date = Field(..., description="Trade date (T)")
    settlement_date: Optional[date] = Field(
        None, description="Expected settlement date (T+1)"
    )
    buy_market: str = Field(..., description="Buy-side market code")
    sell_market: str = Field(..., description="Sell-side market code")
    deadlines: List[Deadline] = Field(
        default_factory=list, description="Relevant deadlines"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Warning messages"
    )
    details: dict = Field(
        default_factory=dict, description="Additional details"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "LIKELY",
                "message": "Settlement expected on 2026-01-29. Both markets are open.",
                "trade_date": "2026-01-28",
                "settlement_date": "2026-01-29",
                "buy_market": "JP",
                "sell_market": "HK",
                "deadlines": [],
                "warnings": [],
                "details": {},
            }
        }


class MarketStatus(BaseModel):
    """Current status of a market."""
    
    market_code: str = Field(..., description="Market code")
    market_name: str = Field(..., description="Market name")
    is_open: bool = Field(..., description="Whether market is currently open")
    current_session: Optional[str] = Field(
        None, description="Current session (pre-market, regular, lunch, post-market, closed)"
    )
    local_time: datetime = Field(..., description="Current local time")
    next_open: Optional[datetime] = Field(
        None, description="Next market open time"
    )
    next_close: Optional[datetime] = Field(
        None, description="Next market close time"
    )
    is_holiday: bool = Field(
        default=False, description="Whether today is a holiday"
    )
    holiday_name: Optional[str] = Field(
        None, description="Holiday name if applicable"
    )

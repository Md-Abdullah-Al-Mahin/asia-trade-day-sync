"""
Market data models.
"""

from datetime import time
from typing import Optional
from pydantic import BaseModel, Field


class LunchBreak(BaseModel):
    """Lunch break period for markets that close midday."""
    
    start: time = Field(..., description="Lunch break start time (local)")
    end: time = Field(..., description="Lunch break end time (local)")


class TradingHours(BaseModel):
    """Trading hours configuration for a market."""
    
    open: time = Field(..., description="Market open time (local)")
    close: time = Field(..., description="Market close time (local)")
    lunch_break: Optional[LunchBreak] = Field(
        None, description="Lunch break if applicable"
    )


class Market(BaseModel):
    """Market configuration model."""
    
    code: str = Field(..., description="Market code (e.g., JP, HK, SG)")
    name: str = Field(..., description="Full market name")
    exchange_name: str = Field(..., description="Exchange name")
    exchange_calendar_code: str = Field(
        ..., description="Code for exchange_calendars library"
    )
    timezone: str = Field(..., description="IANA timezone (e.g., Asia/Tokyo)")
    trading_hours: TradingHours = Field(..., description="Standard trading hours")
    settlement_cycle: int = Field(
        default=1, description="Settlement cycle in days (1 for T+1)"
    )
    currency: str = Field(..., description="Local currency code")
    depository_cut_off: Optional[time] = Field(
        None, description="Depository instruction cut-off time (local)"
    )
    
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

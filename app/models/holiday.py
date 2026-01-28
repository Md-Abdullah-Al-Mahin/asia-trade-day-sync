"""
Holiday calendar models.
"""

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class HolidayType(str, Enum):
    """Type of holiday/closure."""
    
    FULL_DAY = "full_day"
    HALF_DAY = "half_day"
    SPECIAL_CLOSURE = "special_closure"  # e.g., typhoon


class Holiday(BaseModel):
    """Holiday calendar entry."""
    
    market_code: str = Field(..., description="Market code")
    date: date = Field(..., description="Holiday date")
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
    notes: Optional[str] = Field(None, description="Additional notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "market_code": "JP",
                "date": "2026-01-01",
                "name": "New Year's Day",
                "holiday_type": "full_day",
                "affects_trading": True,
                "affects_settlement": True,
                "notes": None,
            }
        }

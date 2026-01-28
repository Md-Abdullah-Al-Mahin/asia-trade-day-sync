"""
Calendar and holiday service.

This module provides calendar operations for trading and settlement
analysis, integrating with the HolidayCalendar and Market models.
"""

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass

from app.models.holiday import (
    Holiday,
    HolidayType,
    HolidayCalendar,
    get_holiday_calendar,
)
from app.models.market import (
    Market,
    get_market,
    get_market_repository,
)
from app.services.timezone_service import (
    TimezoneService,
    OverlapWindow,
    get_timezone_service,
)


@dataclass
class TradingDayInfo:
    """Information about a trading day for a market."""
    
    market_code: str
    date: date
    is_trading_day: bool
    is_settlement_day: bool
    holiday: Optional[Holiday] = None
    is_weekend: bool = False
    
    @property
    def reason_closed(self) -> Optional[str]:
        """Get reason if market is closed."""
        if self.is_trading_day:
            return None
        if self.is_weekend:
            return "Weekend"
        if self.holiday:
            return self.holiday.name
        return "Market Holiday"


@dataclass
class CommonDayInfo:
    """Information about a day for two markets."""
    
    date: date
    market_a_info: TradingDayInfo
    market_b_info: TradingDayInfo
    
    @property
    def both_trading(self) -> bool:
        """Check if both markets are trading."""
        return self.market_a_info.is_trading_day and self.market_b_info.is_trading_day
    
    @property
    def both_settlement(self) -> bool:
        """Check if both markets can settle."""
        return self.market_a_info.is_settlement_day and self.market_b_info.is_settlement_day
    
    @property
    def any_holiday(self) -> bool:
        """Check if either market has a holiday."""
        return (
            self.market_a_info.holiday is not None or 
            self.market_b_info.holiday is not None
        )


@dataclass
class SettlementDateResult:
    """Result of settlement date calculation."""
    
    trade_date: date
    settlement_date: date
    market_code: str
    days_to_settle: int
    skipped_days: List[Tuple[date, str]]  # List of (date, reason) for non-business days
    
    @property
    def is_standard_t_plus_1(self) -> bool:
        """Check if this is standard T+1 settlement."""
        return self.days_to_settle == 1 and len(self.skipped_days) == 0


class CalendarService:
    """
    Service for calendar operations and holiday lookups.
    
    Provides business day calculations, holiday lookups, and
    settlement date calculations for cross-market trading.
    """
    
    def __init__(self):
        self._calendar_cache: Dict[str, HolidayCalendar] = {}
        self._tz_service = get_timezone_service()
    
    def _get_calendar(self, market_code: str) -> HolidayCalendar:
        """Get or create a HolidayCalendar for a market."""
        market_code = market_code.upper()
        if market_code not in self._calendar_cache:
            self._calendar_cache[market_code] = get_holiday_calendar(market_code)
        return self._calendar_cache[market_code]
    
    def is_trading_day(self, market_code: str, check_date: date) -> bool:
        """
        Check if a given date is a trading day for a market.
        
        Args:
            market_code: Market code (e.g., 'JP', 'HK')
            check_date: Date to check
            
        Returns:
            True if the market is open for trading
        """
        calendar = self._get_calendar(market_code)
        return calendar.is_trading_day(check_date)
    
    def is_settlement_day(self, market_code: str, check_date: date) -> bool:
        """
        Check if a given date is a settlement day for a market.
        
        Settlement days typically align with trading days, but some
        markets may have different rules.
        
        Args:
            market_code: Market code
            check_date: Date to check
            
        Returns:
            True if settlement can occur on this date
        """
        calendar = self._get_calendar(market_code)
        return calendar.is_settlement_day(check_date)
    
    def is_weekend(self, check_date: date) -> bool:
        """Check if a date is a weekend."""
        return check_date.weekday() >= 5
    
    def get_trading_day_info(
        self, 
        market_code: str, 
        check_date: date
    ) -> TradingDayInfo:
        """
        Get comprehensive trading day information.
        
        Args:
            market_code: Market code
            check_date: Date to check
            
        Returns:
            TradingDayInfo object
        """
        calendar = self._get_calendar(market_code)
        is_trading = calendar.is_trading_day(check_date)
        is_settlement = calendar.is_settlement_day(check_date)
        holiday = calendar.get_holiday(check_date)
        is_weekend = check_date.weekday() >= 5
        
        return TradingDayInfo(
            market_code=market_code.upper(),
            date=check_date,
            is_trading_day=is_trading,
            is_settlement_day=is_settlement,
            holiday=holiday,
            is_weekend=is_weekend
        )
    
    def get_holidays_for_range(
        self,
        market_code: str,
        start_date: date,
        end_date: date,
        include_weekends: bool = False
    ) -> List[Holiday]:
        """
        Get all holidays for a market within a date range.
        
        Args:
            market_code: Market code
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            include_weekends: Whether to include weekends
            
        Returns:
            List of Holiday objects
        """
        calendar = self._get_calendar(market_code)
        return calendar.get_holidays_in_range(start_date, end_date, include_weekends)
    
    def get_holiday_info(
        self, 
        market_code: str, 
        check_date: date
    ) -> Optional[Holiday]:
        """
        Get holiday information for a specific date.
        
        Args:
            market_code: Market code
            check_date: Date to check
            
        Returns:
            Holiday object if date is a holiday, None otherwise
        """
        calendar = self._get_calendar(market_code)
        return calendar.get_holiday(check_date)
    
    def get_next_trading_day(
        self, 
        market_code: str, 
        from_date: date
    ) -> date:
        """
        Get the next trading day for a market after a given date.
        
        Args:
            market_code: Market code
            from_date: Starting date (exclusive)
            
        Returns:
            Next trading day
        """
        calendar = self._get_calendar(market_code)
        return calendar.get_next_trading_day(from_date)
    
    def get_next_business_day(
        self, 
        market_code: str, 
        from_date: date
    ) -> date:
        """
        Alias for get_next_trading_day.
        
        Args:
            market_code: Market code
            from_date: Starting date (exclusive)
            
        Returns:
            Next business/trading day
        """
        return self.get_next_trading_day(market_code, from_date)
    
    def get_previous_trading_day(
        self, 
        market_code: str, 
        from_date: date
    ) -> date:
        """
        Get the previous trading day for a market before a given date.
        
        Args:
            market_code: Market code
            from_date: Starting date (exclusive)
            
        Returns:
            Previous trading day
        """
        calendar = self._get_calendar(market_code)
        return calendar.get_previous_trading_day(from_date)
    
    def get_trading_days_in_range(
        self,
        market_code: str,
        start_date: date,
        end_date: date
    ) -> List[date]:
        """
        Get all trading days within a date range.
        
        Args:
            market_code: Market code
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            
        Returns:
            List of trading days
        """
        calendar = self._get_calendar(market_code)
        return calendar.get_trading_days_in_range(start_date, end_date)
    
    def get_common_business_days(
        self,
        market_a: str,
        market_b: str,
        start_date: date,
        end_date: date,
    ) -> List[date]:
        """
        Get dates that are business days in both markets.
        
        Args:
            market_a: First market code
            market_b: Second market code
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            List of dates that are business days in both markets
        """
        cal_a = self._get_calendar(market_a)
        cal_b = self._get_calendar(market_b)
        
        common_days = []
        current = start_date
        
        while current <= end_date:
            if cal_a.is_trading_day(current) and cal_b.is_trading_day(current):
                common_days.append(current)
            current += timedelta(days=1)
        
        return common_days
    
    def get_common_day_info(
        self,
        market_a: str,
        market_b: str,
        check_date: date
    ) -> CommonDayInfo:
        """
        Get trading day information for both markets on a specific date.
        
        Args:
            market_a: First market code
            market_b: Second market code
            check_date: Date to check
            
        Returns:
            CommonDayInfo object
        """
        info_a = self.get_trading_day_info(market_a, check_date)
        info_b = self.get_trading_day_info(market_b, check_date)
        
        return CommonDayInfo(
            date=check_date,
            market_a_info=info_a,
            market_b_info=info_b
        )
    
    def get_next_common_trading_day(
        self,
        market_a: str,
        market_b: str,
        from_date: date
    ) -> date:
        """
        Get the next date when both markets are open for trading.
        
        Args:
            market_a: First market code
            market_b: Second market code
            from_date: Starting date (exclusive)
            
        Returns:
            Next common trading day
        """
        cal_a = self._get_calendar(market_a)
        cal_b = self._get_calendar(market_b)
        
        check_date = from_date + timedelta(days=1)
        max_iterations = 30
        
        for _ in range(max_iterations):
            if cal_a.is_trading_day(check_date) and cal_b.is_trading_day(check_date):
                return check_date
            check_date += timedelta(days=1)
        
        raise ValueError(
            f"Could not find common trading day for {market_a} and {market_b} "
            f"within {max_iterations} days of {from_date}"
        )
    
    def calculate_settlement_date(
        self,
        market_code: str,
        trade_date: date,
        settlement_cycle: int = 1
    ) -> SettlementDateResult:
        """
        Calculate the settlement date for a trade.
        
        Args:
            market_code: Market code
            trade_date: Trade date (T)
            settlement_cycle: Settlement cycle (1 for T+1, 2 for T+2)
            
        Returns:
            SettlementDateResult with settlement date and details
        """
        calendar = self._get_calendar(market_code)
        skipped_days = []
        
        current_date = trade_date
        business_days_counted = 0
        
        while business_days_counted < settlement_cycle:
            current_date += timedelta(days=1)
            
            if calendar.is_settlement_day(current_date):
                business_days_counted += 1
            else:
                # Record why this day was skipped
                holiday = calendar.get_holiday(current_date)
                reason = "Weekend" if current_date.weekday() >= 5 else (
                    holiday.name if holiday else "Market Holiday"
                )
                skipped_days.append((current_date, reason))
        
        days_to_settle = (current_date - trade_date).days
        
        return SettlementDateResult(
            trade_date=trade_date,
            settlement_date=current_date,
            market_code=market_code.upper(),
            days_to_settle=days_to_settle,
            skipped_days=skipped_days
        )
    
    def calculate_common_settlement_date(
        self,
        market_a: str,
        market_b: str,
        trade_date: date
    ) -> Tuple[date, SettlementDateResult, SettlementDateResult]:
        """
        Calculate the common settlement date for a cross-market trade.
        
        The settlement date is the first date when BOTH markets can settle.
        
        Args:
            market_a: First market code
            market_b: Second market code
            trade_date: Trade date (T)
            
        Returns:
            Tuple of (common_settlement_date, market_a_result, market_b_result)
        """
        # Get settlement cycles from market config
        try:
            market_a_obj = get_market(market_a)
            market_b_obj = get_market(market_b)
            cycle_a = market_a_obj.settlement_cycle
            cycle_b = market_b_obj.settlement_cycle
        except ValueError:
            cycle_a = cycle_b = 1  # Default to T+1
        
        # Calculate individual settlement dates
        result_a = self.calculate_settlement_date(market_a, trade_date, cycle_a)
        result_b = self.calculate_settlement_date(market_b, trade_date, cycle_b)
        
        # Find the common settlement date (latest of the two)
        common_date = max(result_a.settlement_date, result_b.settlement_date)
        
        # If the common date is later than one market's settlement date,
        # we need to check if that market can settle on the common date
        cal_a = self._get_calendar(market_a)
        cal_b = self._get_calendar(market_b)
        
        # Find a date when both can settle
        max_iterations = 30
        for _ in range(max_iterations):
            if cal_a.is_settlement_day(common_date) and cal_b.is_settlement_day(common_date):
                break
            common_date += timedelta(days=1)
        
        return common_date, result_a, result_b
    
    def count_trading_days_between(
        self,
        market_code: str,
        start_date: date,
        end_date: date
    ) -> int:
        """
        Count trading days between two dates (exclusive).
        
        Args:
            market_code: Market code
            start_date: Start date (exclusive)
            end_date: End date (exclusive)
            
        Returns:
            Number of trading days
        """
        calendar = self._get_calendar(market_code)
        return calendar.count_trading_days_between(start_date, end_date)
    
    def get_month_calendar_data(
        self,
        market_a: str,
        market_b: str,
        year: int,
        month: int
    ) -> List[CommonDayInfo]:
        """
        Get calendar data for a month showing both markets.
        
        Useful for rendering a calendar view in the dashboard.
        
        Args:
            market_a: First market code
            market_b: Second market code
            year: Year
            month: Month (1-12)
            
        Returns:
            List of CommonDayInfo for each day in the month
        """
        import calendar as cal_module
        
        # Get first and last day of month
        _, last_day = cal_module.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)
        
        # Build info for each day
        days = []
        current = start_date
        while current <= end_date:
            days.append(self.get_common_day_info(market_a, market_b, current))
            current += timedelta(days=1)
        
        return days
    
    def get_trading_overlap_for_date(
        self,
        market_a: str,
        market_b: str,
        target_date: date
    ) -> Optional[List[OverlapWindow]]:
        """
        Get trading hour overlap between two markets for a specific date.
        
        Returns None if either market is closed.
        
        Args:
            market_a: First market code
            market_b: Second market code
            target_date: Date to check
            
        Returns:
            List of OverlapWindow objects, or None if markets are closed
        """
        # Check if both markets are open
        if not self.is_trading_day(market_a, target_date):
            return None
        if not self.is_trading_day(market_b, target_date):
            return None
        
        # Get market configurations
        try:
            market_a_obj = get_market(market_a)
            market_b_obj = get_market(market_b)
        except ValueError:
            return None
        
        # Calculate overlap with lunch breaks
        a_lunch_start = None
        a_lunch_end = None
        b_lunch_start = None
        b_lunch_end = None
        
        if market_a_obj.trading_hours.lunch_break:
            a_lunch_start = market_a_obj.trading_hours.lunch_break.start
            a_lunch_end = market_a_obj.trading_hours.lunch_break.end
        
        if market_b_obj.trading_hours.lunch_break:
            b_lunch_start = market_b_obj.trading_hours.lunch_break.start
            b_lunch_end = market_b_obj.trading_hours.lunch_break.end
        
        return self._tz_service.calculate_overlap_with_lunch_breaks(
            market_a_timezone=market_a_obj.timezone,
            market_a_open=market_a_obj.trading_hours.open,
            market_a_close=market_a_obj.trading_hours.close,
            market_a_lunch_start=a_lunch_start,
            market_a_lunch_end=a_lunch_end,
            market_b_timezone=market_b_obj.timezone,
            market_b_open=market_b_obj.trading_hours.open,
            market_b_close=market_b_obj.trading_hours.close,
            market_b_lunch_start=b_lunch_start,
            market_b_lunch_end=b_lunch_end,
            target_date=target_date
        )
    
    def find_next_viable_trade_date(
        self,
        market_a: str,
        market_b: str,
        from_date: date,
        require_overlap: bool = False
    ) -> date:
        """
        Find the next date suitable for trading between two markets.
        
        Args:
            market_a: First market code
            market_b: Second market code
            from_date: Starting date (inclusive)
            require_overlap: Whether to require trading hour overlap
            
        Returns:
            Next viable trade date
        """
        check_date = from_date
        max_iterations = 60
        
        for _ in range(max_iterations):
            # Check if both markets are open
            if self.is_trading_day(market_a, check_date) and \
               self.is_trading_day(market_b, check_date):
                
                if require_overlap:
                    overlap = self.get_trading_overlap_for_date(
                        market_a, market_b, check_date
                    )
                    if overlap and len(overlap) > 0:
                        return check_date
                else:
                    return check_date
            
            check_date += timedelta(days=1)
        
        raise ValueError(
            f"Could not find viable trade date for {market_a} and {market_b} "
            f"within {max_iterations} days"
        )
    
    def get_upcoming_holidays(
        self,
        market_code: str,
        days_ahead: int = 30
    ) -> List[Holiday]:
        """
        Get upcoming holidays for a market.
        
        Args:
            market_code: Market code
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming holidays (excluding weekends)
        """
        today = date.today()
        end_date = today + timedelta(days=days_ahead)
        return self.get_holidays_for_range(market_code, today, end_date, include_weekends=False)
    
    def get_holiday_summary(
        self,
        market_a: str,
        market_b: str,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Get a summary of holidays for two markets in a date range.
        
        Args:
            market_a: First market code
            market_b: Second market code
            start_date: Start of range
            end_date: End of range
            
        Returns:
            Dictionary with holiday summary
        """
        holidays_a = self.get_holidays_for_range(market_a, start_date, end_date)
        holidays_b = self.get_holidays_for_range(market_b, start_date, end_date)
        
        dates_a = {h.date for h in holidays_a}
        dates_b = {h.date for h in holidays_b}
        
        common_dates = dates_a & dates_b
        only_a_dates = dates_a - dates_b
        only_b_dates = dates_b - dates_a
        
        return {
            "market_a": market_a,
            "market_b": market_b,
            "total_holidays_a": len(holidays_a),
            "total_holidays_b": len(holidays_b),
            "common_holidays": len(common_dates),
            "only_in_a": len(only_a_dates),
            "only_in_b": len(only_b_dates),
            "holidays_a": holidays_a,
            "holidays_b": holidays_b,
            "common_dates": sorted(list(common_dates)),
        }


# Singleton instance
_calendar_service: Optional[CalendarService] = None


def get_calendar_service() -> CalendarService:
    """Get the singleton CalendarService instance."""
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService()
    return _calendar_service

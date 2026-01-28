"""
Market Status Service.

Provides real-time market status information, trading hours,
and time-until calculations for the dashboard.
"""

from datetime import date, datetime, time, timedelta
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from app.models.market import Market, get_market, get_market_repository
from app.models.holiday import Holiday, get_holiday_calendar
from app.models.settlement import MarketStatus, MarketPairComparison
from app.services.calendar_service import CalendarService, get_calendar_service
from app.services.timezone_service import TimezoneService, OverlapWindow, get_timezone_service


@dataclass
class TradingSession:
    """Represents a trading session period."""
    
    name: str
    start_time: time
    end_time: time
    is_active: bool = False
    
    @property
    def duration_minutes(self) -> int:
        """Calculate session duration in minutes."""
        start_mins = self.start_time.hour * 60 + self.start_time.minute
        end_mins = self.end_time.hour * 60 + self.end_time.minute
        return end_mins - start_mins


@dataclass
class TradingHoursInfo:
    """Complete trading hours information for a market on a specific date."""
    
    market_code: str
    date: date
    is_trading_day: bool
    sessions: List[TradingSession]
    market_open: Optional[time] = None
    market_close: Optional[time] = None
    lunch_break_start: Optional[time] = None
    lunch_break_end: Optional[time] = None
    holiday_name: Optional[str] = None
    
    @property
    def total_trading_minutes(self) -> int:
        """Calculate total trading minutes (excluding breaks)."""
        return sum(s.duration_minutes for s in self.sessions)
    
    @property
    def has_lunch_break(self) -> bool:
        """Check if there's a lunch break."""
        return self.lunch_break_start is not None


@dataclass
class TimeUntilInfo:
    """Information about time until a specific event."""
    
    event_name: str
    event_time: datetime
    time_remaining: timedelta
    is_today: bool
    
    @property
    def formatted(self) -> str:
        """Get formatted time remaining string."""
        total_seconds = int(self.time_remaining.total_seconds())
        
        if total_seconds < 0:
            return "Passed"
        
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
        
        return " ".join(parts)
    
    @property
    def is_imminent(self) -> bool:
        """Check if event is within 30 minutes."""
        return self.time_remaining.total_seconds() < 1800


@dataclass 
class AllMarketsStatus:
    """Status of all configured markets."""
    
    statuses: List[MarketStatus]
    timestamp: datetime
    
    @property
    def open_markets(self) -> List[MarketStatus]:
        """Get list of currently open markets."""
        return [s for s in self.statuses if s.is_open]
    
    @property
    def closed_markets(self) -> List[MarketStatus]:
        """Get list of currently closed markets."""
        return [s for s in self.statuses if not s.is_open]
    
    @property
    def open_count(self) -> int:
        """Count of open markets."""
        return len(self.open_markets)


class MarketStatusService:
    """
    Service for getting real-time market status information.
    
    Provides functions to check if markets are open, get trading hours,
    and calculate time until various events (close, cut-off, etc.).
    """
    
    def __init__(
        self,
        calendar_service: Optional[CalendarService] = None,
        timezone_service: Optional[TimezoneService] = None,
    ):
        self.calendar_service = calendar_service or get_calendar_service()
        self.timezone_service = timezone_service or get_timezone_service()
        self._market_repo = get_market_repository()
    
    def get_current_market_status(self, market_code: str) -> MarketStatus:
        """
        Get the current status of a market.
        
        Args:
            market_code: Market code (e.g., 'JP', 'HK')
            
        Returns:
            MarketStatus with current state
        """
        market = get_market(market_code)
        
        # Get current times
        local_now = self.timezone_service.get_current_time_in_timezone(market.timezone)
        local_date = local_now.date()
        local_time = local_now.time()
        
        # Check trading day
        is_trading_day = self.calendar_service.is_trading_day(market_code, local_date)
        
        # Check holiday
        holiday = self.calendar_service.get_holiday_info(market_code, local_date)
        is_holiday = holiday is not None and holiday.holiday_type.value != "weekend"
        is_weekend = local_date.weekday() >= 5
        
        # Determine if market is currently open
        is_open = False
        current_session = "closed"
        
        if is_trading_day:
            is_open = market.trading_hours.is_trading_time(local_time)
            current_session = market.trading_hours.get_session(local_time)
        
        # Calculate next open/close
        next_open = None
        next_close = None
        time_until_next_event = None
        
        if is_open:
            # Calculate time until close
            close_dt = self.timezone_service.combine_date_time(
                local_date, market.trading_hours.close, market.timezone
            )
            next_close = close_dt
            delta = self.timezone_service.get_time_until(close_dt, local_now)
            if delta:
                time_until_next_event = self.timezone_service.format_duration(delta)
        else:
            # Calculate time until next open
            if is_trading_day and local_time < market.trading_hours.open:
                # Market opens later today
                open_dt = self.timezone_service.combine_date_time(
                    local_date, market.trading_hours.open, market.timezone
                )
                next_open = open_dt
            else:
                # Market opens next trading day
                next_trading = self.calendar_service.get_next_trading_day(
                    market_code, local_date
                )
                open_dt = self.timezone_service.combine_date_time(
                    next_trading, market.trading_hours.open, market.timezone
                )
                next_open = open_dt
            
            delta = self.timezone_service.get_time_until(next_open, local_now)
            if delta:
                time_until_next_event = self.timezone_service.format_duration(delta)
        
        # Check cut-off status
        is_before_cut_off = True
        time_until_cut_off = None
        
        if market.depository_cut_off and is_trading_day:
            is_before_cut_off = local_time < market.depository_cut_off
            if is_before_cut_off:
                cut_off_dt = self.timezone_service.combine_date_time(
                    local_date, market.depository_cut_off, market.timezone
                )
                delta = self.timezone_service.get_time_until(cut_off_dt, local_now)
                if delta:
                    time_until_cut_off = self.timezone_service.format_duration(delta)
        
        return MarketStatus(
            market_code=market_code,
            market_name=market.name,
            timezone=market.timezone,
            is_open=is_open,
            current_session=current_session,
            local_time=local_now,
            local_date=local_date,
            trading_hours_open=market.trading_hours.open if is_trading_day else None,
            trading_hours_close=market.trading_hours.close if is_trading_day else None,
            next_open=next_open,
            next_close=next_close,
            time_until_next_event=time_until_next_event,
            is_holiday=is_holiday,
            holiday_name=holiday.name if is_holiday else None,
            is_weekend=is_weekend,
            depository_cut_off=market.depository_cut_off,
            is_before_cut_off=is_before_cut_off,
            time_until_cut_off=time_until_cut_off
        )
    
    def get_trading_hours_for_date(
        self, 
        market_code: str, 
        target_date: date
    ) -> TradingHoursInfo:
        """
        Get detailed trading hours for a market on a specific date.
        
        Args:
            market_code: Market code
            target_date: Date to get hours for
            
        Returns:
            TradingHoursInfo with session details
        """
        market = get_market(market_code)
        is_trading = self.calendar_service.is_trading_day(market_code, target_date)
        holiday = self.calendar_service.get_holiday_info(market_code, target_date)
        
        sessions = []
        market_open = None
        market_close = None
        lunch_start = None
        lunch_end = None
        
        if is_trading:
            market_open = market.trading_hours.open
            market_close = market.trading_hours.close
            
            # Get current time for active session check
            local_now = self.timezone_service.get_current_time_in_timezone(market.timezone)
            is_today = local_now.date() == target_date
            current_time = local_now.time() if is_today else None
            
            if market.trading_hours.lunch_break:
                lunch_start = market.trading_hours.lunch_break.start
                lunch_end = market.trading_hours.lunch_break.end
                
                # Morning session
                morning_active = False
                if current_time and market_open <= current_time < lunch_start:
                    morning_active = True
                    
                sessions.append(TradingSession(
                    name="Morning",
                    start_time=market_open,
                    end_time=lunch_start,
                    is_active=morning_active
                ))
                
                # Afternoon session
                afternoon_active = False
                if current_time and lunch_end <= current_time < market_close:
                    afternoon_active = True
                    
                sessions.append(TradingSession(
                    name="Afternoon",
                    start_time=lunch_end,
                    end_time=market_close,
                    is_active=afternoon_active
                ))
            else:
                # Single session
                regular_active = False
                if current_time and market_open <= current_time < market_close:
                    regular_active = True
                    
                sessions.append(TradingSession(
                    name="Regular",
                    start_time=market_open,
                    end_time=market_close,
                    is_active=regular_active
                ))
        
        return TradingHoursInfo(
            market_code=market_code,
            date=target_date,
            is_trading_day=is_trading,
            sessions=sessions,
            market_open=market_open,
            market_close=market_close,
            lunch_break_start=lunch_start,
            lunch_break_end=lunch_end,
            holiday_name=holiday.name if holiday else None
        )
    
    def is_market_open_now(self, market_code: str) -> bool:
        """
        Check if a market is currently open for trading.
        
        Args:
            market_code: Market code
            
        Returns:
            True if market is currently open
        """
        status = self.get_current_market_status(market_code)
        return status.is_open
    
    def get_time_until_open(self, market_code: str) -> Optional[TimeUntilInfo]:
        """
        Get time until market opens.
        
        Args:
            market_code: Market code
            
        Returns:
            TimeUntilInfo or None if market is already open
        """
        status = self.get_current_market_status(market_code)
        
        if status.is_open:
            return None
        
        if status.next_open is None:
            return None
        
        local_now = self.timezone_service.get_current_time_in_timezone(
            get_market(market_code).timezone
        )
        
        delta = status.next_open - local_now
        is_today = status.next_open.date() == local_now.date()
        
        return TimeUntilInfo(
            event_name="Market Open",
            event_time=status.next_open,
            time_remaining=delta,
            is_today=is_today
        )
    
    def get_time_until_close(self, market_code: str) -> Optional[TimeUntilInfo]:
        """
        Get time until market closes.
        
        Args:
            market_code: Market code
            
        Returns:
            TimeUntilInfo or None if market is closed
        """
        status = self.get_current_market_status(market_code)
        
        if not status.is_open:
            return None
        
        if status.next_close is None:
            return None
        
        local_now = self.timezone_service.get_current_time_in_timezone(
            get_market(market_code).timezone
        )
        
        delta = status.next_close - local_now
        
        return TimeUntilInfo(
            event_name="Market Close",
            event_time=status.next_close,
            time_remaining=delta,
            is_today=True
        )
    
    def get_time_until_cut_off(self, market_code: str) -> Optional[TimeUntilInfo]:
        """
        Get time until depository cut-off.
        
        Args:
            market_code: Market code
            
        Returns:
            TimeUntilInfo or None if no cut-off or already passed
        """
        market = get_market(market_code)
        
        if market.depository_cut_off is None:
            return None
        
        local_now = self.timezone_service.get_current_time_in_timezone(market.timezone)
        local_date = local_now.date()
        
        # Check if trading day
        if not self.calendar_service.is_trading_day(market_code, local_date):
            return None
        
        # Check if already past cut-off
        if local_now.time() >= market.depository_cut_off:
            return None
        
        cut_off_dt = self.timezone_service.combine_date_time(
            local_date, market.depository_cut_off, market.timezone
        )
        
        delta = cut_off_dt - local_now
        
        return TimeUntilInfo(
            event_name="Depository Cut-off",
            event_time=cut_off_dt,
            time_remaining=delta,
            is_today=True
        )
    
    def get_all_markets_status(self) -> AllMarketsStatus:
        """
        Get status of all configured markets.
        
        Returns:
            AllMarketsStatus with list of all market statuses
        """
        statuses = []
        for market in self._market_repo.list_all():
            status = self.get_current_market_status(market.code)
            statuses.append(status)
        
        # Sort by whether open, then by name
        statuses.sort(key=lambda s: (not s.is_open, s.market_name))
        
        return AllMarketsStatus(
            statuses=statuses,
            timestamp=self.timezone_service.get_current_time_utc()
        )
    
    def get_market_pair_status(
        self, 
        market_a: str, 
        market_b: str
    ) -> MarketPairComparison:
        """
        Get comparison status for two markets.
        
        Args:
            market_a: First market code
            market_b: Second market code
            
        Returns:
            MarketPairComparison with both statuses and overlap info
        """
        status_a = self.get_current_market_status(market_a)
        status_b = self.get_current_market_status(market_b)
        
        # Calculate timezone difference
        tz_diff = self.timezone_service.get_timezone_difference(
            get_market(market_a).timezone,
            get_market(market_b).timezone
        )
        
        # Get overlap info for today
        today = date.today()
        has_overlap = False
        overlap_start_a = None
        overlap_end_a = None
        overlap_duration = None
        
        overlaps = self.calendar_service.get_trading_overlap_for_date(
            market_a, market_b, today
        )
        
        if overlaps:
            has_overlap = True
            overlap_start_a = overlaps[0].start_market_a_local.time()
            overlap_end_a = overlaps[-1].end_market_a_local.time()
            overlap_duration = sum(o.duration_minutes for o in overlaps)
        
        return MarketPairComparison(
            market_a=status_a,
            market_b=status_b,
            timezone_difference_hours=tz_diff,
            has_trading_overlap=has_overlap,
            overlap_start_local_a=overlap_start_a,
            overlap_end_local_a=overlap_end_a,
            overlap_duration_minutes=overlap_duration,
            both_open_now=status_a.is_open and status_b.is_open,
            both_trading_today=status_a.can_trade_today and status_b.can_trade_today
        )
    
    def get_next_overlap_window(
        self,
        market_a: str,
        market_b: str,
        from_date: Optional[date] = None
    ) -> Optional[Tuple[date, List[OverlapWindow]]]:
        """
        Find the next trading day with overlap between two markets.
        
        Args:
            market_a: First market code
            market_b: Second market code
            from_date: Starting date (defaults to today)
            
        Returns:
            Tuple of (date, overlap_windows) or None if not found
        """
        if from_date is None:
            from_date = date.today()
        
        max_days = 30
        current_date = from_date
        
        for _ in range(max_days):
            overlaps = self.calendar_service.get_trading_overlap_for_date(
                market_a, market_b, current_date
            )
            
            if overlaps and len(overlaps) > 0:
                return (current_date, overlaps)
            
            current_date += timedelta(days=1)
        
        return None
    
    def get_market_summary_for_dashboard(self, market_code: str) -> Dict:
        """
        Get a summary of market status suitable for dashboard display.
        
        Args:
            market_code: Market code
            
        Returns:
            Dictionary with dashboard-ready data
        """
        status = self.get_current_market_status(market_code)
        market = get_market(market_code)
        
        time_until_open = self.get_time_until_open(market_code)
        time_until_close = self.get_time_until_close(market_code)
        time_until_cut_off = self.get_time_until_cut_off(market_code)
        
        return {
            "market_code": market_code,
            "market_name": market.name,
            "exchange_name": market.exchange_name,
            "currency": market.currency,
            "timezone": market.timezone,
            "local_time": status.local_time.strftime("%H:%M:%S"),
            "local_date": status.local_date.isoformat(),
            "is_open": status.is_open,
            "current_session": status.current_session,
            "status_text": status.status_text,
            "can_trade_today": status.can_trade_today,
            "is_holiday": status.is_holiday,
            "holiday_name": status.holiday_name,
            "trading_hours": {
                "open": status.trading_hours_open.strftime("%H:%M") if status.trading_hours_open else None,
                "close": status.trading_hours_close.strftime("%H:%M") if status.trading_hours_close else None,
                "cut_off": market.depository_cut_off.strftime("%H:%M") if market.depository_cut_off else None,
            },
            "time_until": {
                "open": time_until_open.formatted if time_until_open else None,
                "close": time_until_close.formatted if time_until_close else None,
                "cut_off": time_until_cut_off.formatted if time_until_cut_off else None,
            },
            "alerts": {
                "cut_off_imminent": time_until_cut_off.is_imminent if time_until_cut_off else False,
                "close_imminent": time_until_close.is_imminent if time_until_close else False,
            }
        }


# Singleton instance
_market_status_service: Optional[MarketStatusService] = None


def get_market_status_service() -> MarketStatusService:
    """Get the singleton MarketStatusService instance."""
    global _market_status_service
    if _market_status_service is None:
        _market_status_service = MarketStatusService()
    return _market_status_service

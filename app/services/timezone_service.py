"""
Timezone conversion service.

This module provides timezone conversion utilities and overlap
calculations for cross-market trading analysis.
"""

from datetime import datetime, date, time, timedelta
from typing import Optional, Tuple, List, Dict
from zoneinfo import ZoneInfo
from dataclasses import dataclass

import pytz


@dataclass
class OverlapWindow:
    """Represents an overlap window between two markets."""
    
    start_utc: datetime
    end_utc: datetime
    start_market_a_local: datetime
    end_market_a_local: datetime
    start_market_b_local: datetime
    end_market_b_local: datetime
    duration_minutes: int
    
    @property
    def has_overlap(self) -> bool:
        """Check if there is actual overlap."""
        return self.duration_minutes > 0
    
    @property
    def duration_formatted(self) -> str:
        """Get formatted duration string."""
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"


@dataclass
class MarketTimeInfo:
    """Time information for a market on a specific date."""
    
    market_code: str
    timezone: str
    date: date
    open_local: datetime
    close_local: datetime
    open_utc: datetime
    close_utc: datetime
    current_local: Optional[datetime] = None
    
    @property
    def trading_duration_minutes(self) -> int:
        """Get trading duration in minutes."""
        delta = self.close_utc - self.open_utc
        return int(delta.total_seconds() / 60)


class TimezoneService:
    """
    Service for timezone conversions and overlap calculations.
    
    Handles all timezone-related operations for cross-market
    trading analysis, including time conversions and calculating
    trading hour overlaps between different markets.
    """
    
    def __init__(self):
        self._utc = ZoneInfo("UTC")
        self._timezone_cache: Dict[str, ZoneInfo] = {"UTC": self._utc}
    
    def _get_timezone(self, timezone: str) -> ZoneInfo:
        """Get ZoneInfo object with caching."""
        if timezone not in self._timezone_cache:
            self._timezone_cache[timezone] = ZoneInfo(timezone)
        return self._timezone_cache[timezone]
    
    def convert_to_utc(self, local_time: datetime, timezone: str) -> datetime:
        """
        Convert a local time to UTC.
        
        Args:
            local_time: Datetime in local timezone (can be naive or aware)
            timezone: IANA timezone string (e.g., 'Asia/Tokyo')
            
        Returns:
            Datetime in UTC (timezone-aware)
        """
        tz = self._get_timezone(timezone)
        
        # If datetime is naive, localize it first
        if local_time.tzinfo is None:
            local_time = local_time.replace(tzinfo=tz)
        
        # Convert to UTC
        return local_time.astimezone(self._utc)
    
    def convert_from_utc(self, utc_time: datetime, timezone: str) -> datetime:
        """
        Convert UTC time to a local timezone.
        
        Args:
            utc_time: Datetime in UTC (can be naive or aware)
            timezone: IANA timezone string
            
        Returns:
            Datetime in local timezone (timezone-aware)
        """
        tz = self._get_timezone(timezone)
        
        # If datetime is naive, assume it's UTC
        if utc_time.tzinfo is None:
            utc_time = utc_time.replace(tzinfo=self._utc)
        
        # Convert to target timezone
        return utc_time.astimezone(tz)
    
    def get_current_time_utc(self) -> datetime:
        """
        Get current UTC time.
        
        Returns:
            Current datetime in UTC (timezone-aware)
        """
        return datetime.now(self._utc)
    
    def get_current_time_in_timezone(self, timezone: str) -> datetime:
        """
        Get current time in a specific timezone.
        
        Args:
            timezone: IANA timezone string
            
        Returns:
            Current datetime in the specified timezone (timezone-aware)
        """
        tz = self._get_timezone(timezone)
        return datetime.now(tz)
    
    def get_timezone_offset_hours(self, timezone: str, for_date: Optional[date] = None) -> float:
        """
        Get the UTC offset for a timezone in hours.
        
        Args:
            timezone: IANA timezone string
            for_date: Date to check (for DST), defaults to today
            
        Returns:
            Offset from UTC in hours (e.g., +9.0 for Tokyo)
        """
        if for_date is None:
            for_date = date.today()
        
        tz = self._get_timezone(timezone)
        dt = datetime.combine(for_date, time(12, 0), tzinfo=tz)
        offset = dt.utcoffset()
        
        if offset is None:
            return 0.0
        
        return offset.total_seconds() / 3600
    
    def get_timezone_difference(
        self, 
        timezone_a: str, 
        timezone_b: str,
        for_date: Optional[date] = None
    ) -> float:
        """
        Get the difference between two timezones in hours.
        
        Args:
            timezone_a: First timezone
            timezone_b: Second timezone
            for_date: Date to check (for DST)
            
        Returns:
            Difference (A - B) in hours
        """
        offset_a = self.get_timezone_offset_hours(timezone_a, for_date)
        offset_b = self.get_timezone_offset_hours(timezone_b, for_date)
        return offset_a - offset_b
    
    def combine_date_time(
        self, 
        target_date: date, 
        target_time: time, 
        timezone: str
    ) -> datetime:
        """
        Combine a date and time in a specific timezone.
        
        Args:
            target_date: The date
            target_time: The time
            timezone: IANA timezone string
            
        Returns:
            Combined datetime (timezone-aware)
        """
        tz = self._get_timezone(timezone)
        return datetime.combine(target_date, target_time, tzinfo=tz)
    
    def combine_date_time_utc(
        self, 
        target_date: date, 
        target_time: time, 
        timezone: str
    ) -> datetime:
        """
        Combine a date and time in a timezone, then convert to UTC.
        
        Args:
            target_date: The date
            target_time: The time (in local timezone)
            timezone: IANA timezone string
            
        Returns:
            Combined datetime in UTC (timezone-aware)
        """
        local_dt = self.combine_date_time(target_date, target_time, timezone)
        return self.convert_to_utc(local_dt, timezone)
    
    def calculate_overlap_window(
        self,
        market_a_timezone: str,
        market_a_open: time,
        market_a_close: time,
        market_b_timezone: str,
        market_b_open: time,
        market_b_close: time,
        target_date: date,
    ) -> Optional[OverlapWindow]:
        """
        Calculate the overlapping trading window between two markets.
        
        Args:
            market_a_timezone: Timezone for market A
            market_a_open: Opening time for market A (local)
            market_a_close: Closing time for market A (local)
            market_b_timezone: Timezone for market B
            market_b_open: Opening time for market B (local)
            market_b_close: Closing time for market B (local)
            target_date: Date to calculate overlap for
            
        Returns:
            OverlapWindow object, or None if no overlap
        """
        # Convert market A times to UTC
        a_open_local = self.combine_date_time(target_date, market_a_open, market_a_timezone)
        a_close_local = self.combine_date_time(target_date, market_a_close, market_a_timezone)
        a_open_utc = self.convert_to_utc(a_open_local, market_a_timezone)
        a_close_utc = self.convert_to_utc(a_close_local, market_a_timezone)
        
        # Convert market B times to UTC
        b_open_local = self.combine_date_time(target_date, market_b_open, market_b_timezone)
        b_close_local = self.combine_date_time(target_date, market_b_close, market_b_timezone)
        b_open_utc = self.convert_to_utc(b_open_local, market_b_timezone)
        b_close_utc = self.convert_to_utc(b_close_local, market_b_timezone)
        
        # Calculate overlap in UTC
        overlap_start_utc = max(a_open_utc, b_open_utc)
        overlap_end_utc = min(a_close_utc, b_close_utc)
        
        # Check if there's actual overlap
        if overlap_start_utc >= overlap_end_utc:
            return None
        
        # Calculate duration
        duration = overlap_end_utc - overlap_start_utc
        duration_minutes = int(duration.total_seconds() / 60)
        
        # Convert overlap times back to local times
        overlap_start_a = self.convert_from_utc(overlap_start_utc, market_a_timezone)
        overlap_end_a = self.convert_from_utc(overlap_end_utc, market_a_timezone)
        overlap_start_b = self.convert_from_utc(overlap_start_utc, market_b_timezone)
        overlap_end_b = self.convert_from_utc(overlap_end_utc, market_b_timezone)
        
        return OverlapWindow(
            start_utc=overlap_start_utc,
            end_utc=overlap_end_utc,
            start_market_a_local=overlap_start_a,
            end_market_a_local=overlap_end_a,
            start_market_b_local=overlap_start_b,
            end_market_b_local=overlap_end_b,
            duration_minutes=duration_minutes
        )
    
    def calculate_overlap_with_lunch_breaks(
        self,
        market_a_timezone: str,
        market_a_open: time,
        market_a_close: time,
        market_a_lunch_start: Optional[time],
        market_a_lunch_end: Optional[time],
        market_b_timezone: str,
        market_b_open: time,
        market_b_close: time,
        market_b_lunch_start: Optional[time],
        market_b_lunch_end: Optional[time],
        target_date: date,
    ) -> List[OverlapWindow]:
        """
        Calculate overlapping trading windows, accounting for lunch breaks.
        
        Returns a list of overlap windows (may be multiple if lunch breaks
        split the overlap).
        
        Args:
            market_a_*: Market A trading hours and lunch break
            market_b_*: Market B trading hours and lunch break
            target_date: Date to calculate overlap for
            
        Returns:
            List of OverlapWindow objects (empty if no overlap)
        """
        # Build trading sessions for market A
        a_sessions = self._build_trading_sessions(
            target_date, market_a_timezone,
            market_a_open, market_a_close,
            market_a_lunch_start, market_a_lunch_end
        )
        
        # Build trading sessions for market B
        b_sessions = self._build_trading_sessions(
            target_date, market_b_timezone,
            market_b_open, market_b_close,
            market_b_lunch_start, market_b_lunch_end
        )
        
        # Find overlaps between all session combinations
        overlaps = []
        for a_start, a_end in a_sessions:
            for b_start, b_end in b_sessions:
                overlap_start = max(a_start, b_start)
                overlap_end = min(a_end, b_end)
                
                if overlap_start < overlap_end:
                    duration = int((overlap_end - overlap_start).total_seconds() / 60)
                    overlaps.append(OverlapWindow(
                        start_utc=overlap_start,
                        end_utc=overlap_end,
                        start_market_a_local=self.convert_from_utc(overlap_start, market_a_timezone),
                        end_market_a_local=self.convert_from_utc(overlap_end, market_a_timezone),
                        start_market_b_local=self.convert_from_utc(overlap_start, market_b_timezone),
                        end_market_b_local=self.convert_from_utc(overlap_end, market_b_timezone),
                        duration_minutes=duration
                    ))
        
        return overlaps
    
    def _build_trading_sessions(
        self,
        target_date: date,
        timezone: str,
        open_time: time,
        close_time: time,
        lunch_start: Optional[time],
        lunch_end: Optional[time]
    ) -> List[Tuple[datetime, datetime]]:
        """Build list of trading sessions in UTC (accounting for lunch break)."""
        sessions = []
        
        open_utc = self.combine_date_time_utc(target_date, open_time, timezone)
        close_utc = self.combine_date_time_utc(target_date, close_time, timezone)
        
        if lunch_start and lunch_end:
            lunch_start_utc = self.combine_date_time_utc(target_date, lunch_start, timezone)
            lunch_end_utc = self.combine_date_time_utc(target_date, lunch_end, timezone)
            
            # Morning session
            sessions.append((open_utc, lunch_start_utc))
            # Afternoon session
            sessions.append((lunch_end_utc, close_utc))
        else:
            # Single session
            sessions.append((open_utc, close_utc))
        
        return sessions
    
    def get_market_time_info(
        self,
        market_code: str,
        timezone: str,
        open_time: time,
        close_time: time,
        target_date: date
    ) -> MarketTimeInfo:
        """
        Get comprehensive time information for a market.
        
        Args:
            market_code: Market identifier
            timezone: Market timezone
            open_time: Market open time (local)
            close_time: Market close time (local)
            target_date: Date to get info for
            
        Returns:
            MarketTimeInfo object
        """
        open_local = self.combine_date_time(target_date, open_time, timezone)
        close_local = self.combine_date_time(target_date, close_time, timezone)
        open_utc = self.convert_to_utc(open_local, timezone)
        close_utc = self.convert_to_utc(close_local, timezone)
        current_local = self.get_current_time_in_timezone(timezone)
        
        return MarketTimeInfo(
            market_code=market_code,
            timezone=timezone,
            date=target_date,
            open_local=open_local,
            close_local=close_local,
            open_utc=open_utc,
            close_utc=close_utc,
            current_local=current_local
        )
    
    def is_time_in_range(
        self,
        check_time: datetime,
        start_time: datetime,
        end_time: datetime
    ) -> bool:
        """
        Check if a time falls within a range.
        
        All times should be timezone-aware.
        
        Args:
            check_time: Time to check
            start_time: Start of range
            end_time: End of range
            
        Returns:
            True if check_time is within [start_time, end_time)
        """
        return start_time <= check_time < end_time
    
    def format_time_in_timezone(
        self,
        utc_time: datetime,
        timezone: str,
        format_str: str = "%H:%M"
    ) -> str:
        """
        Format a UTC time in a specific timezone.
        
        Args:
            utc_time: Time in UTC
            timezone: Target timezone
            format_str: strftime format string
            
        Returns:
            Formatted time string
        """
        local_time = self.convert_from_utc(utc_time, timezone)
        return local_time.strftime(format_str)
    
    def get_time_until(
        self,
        target_time: datetime,
        from_time: Optional[datetime] = None
    ) -> Optional[timedelta]:
        """
        Calculate time remaining until a target time.
        
        Args:
            target_time: Target datetime
            from_time: Starting time (defaults to current UTC)
            
        Returns:
            timedelta if target is in future, None if passed
        """
        if from_time is None:
            from_time = self.get_current_time_utc()
        
        # Ensure both are timezone-aware
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=self._utc)
        if from_time.tzinfo is None:
            from_time = from_time.replace(tzinfo=self._utc)
        
        delta = target_time - from_time
        if delta.total_seconds() < 0:
            return None
        return delta
    
    def format_duration(self, duration: timedelta) -> str:
        """
        Format a timedelta as a human-readable string.
        
        Args:
            duration: The timedelta to format
            
        Returns:
            Formatted string (e.g., "2h 30m", "45m", "1d 3h")
        """
        total_seconds = int(duration.total_seconds())
        
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


# Singleton instance
_timezone_service: Optional[TimezoneService] = None


def get_timezone_service() -> TimezoneService:
    """Get the singleton TimezoneService instance."""
    global _timezone_service
    if _timezone_service is None:
        _timezone_service = TimezoneService()
    return _timezone_service

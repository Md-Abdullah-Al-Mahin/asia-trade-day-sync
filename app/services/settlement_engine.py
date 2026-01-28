"""
Core settlement calculation engine.

This is the "brain" of the application that determines whether
a cross-market trade will settle on time (T+1).
"""

from datetime import date, datetime, time, timedelta
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

from app.models.market import Market, get_market, get_market_repository
from app.models.holiday import Holiday, get_holiday_calendar
from app.models.settlement import (
    SettlementCheckRequest,
    SettlementResult,
    SettlementStatusEnum,
    SettlementDetails,
    MarketDayInfo,
    MarketStatus,
    MarketPairComparison,
    Deadline,
    DeadlineType,
)
from app.services.calendar_service import (
    CalendarService,
    get_calendar_service,
    TradingDayInfo,
    SettlementDateResult,
)
from app.services.timezone_service import (
    TimezoneService,
    OverlapWindow,
    get_timezone_service,
)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    valid: bool
    message: str
    details: Optional[Dict] = None


@dataclass
class CutOffCheck:
    """Result of cut-off time check."""
    
    market_code: str
    cut_off_time: Optional[time]
    execution_time: Optional[datetime]
    is_before_cut_off: bool
    time_remaining: Optional[timedelta] = None
    message: str = ""


class SettlementEngine:
    """
    Core engine for determining settlement viability.
    
    This is the "brain" of the application that determines whether
    a cross-market trade will settle on time (T+1).
    
    The engine performs the following checks:
    1. Validates trade date is a common business day
    2. Checks execution time against both markets' trading hours
    3. Verifies execution time vs depository cut-off times
    4. Calculates T+1 settlement date for both markets
    5. Finds the common settlement date
    6. Determines the overall settlement status
    """
    
    # Threshold in minutes for "at risk" status (close to cut-off)
    AT_RISK_THRESHOLD_MINUTES = 60
    
    def __init__(
        self,
        calendar_service: Optional[CalendarService] = None,
        timezone_service: Optional[TimezoneService] = None,
    ):
        self.calendar_service = calendar_service or get_calendar_service()
        self.timezone_service = timezone_service or get_timezone_service()
    
    def check_settlement(
        self, request: SettlementCheckRequest
    ) -> SettlementResult:
        """
        Check settlement viability for a cross-market trade.
        
        Core algorithm:
        1. Validate trade date is common business day
        2. Check execution time against both markets' hours
        3. Verify execution time vs cut-off times
        4. Calculate T+1 settlement date for both markets
        5. Find common settlement date
        6. Return status with detailed message
        
        Args:
            request: Settlement check request with trade details
            
        Returns:
            SettlementResult with status, message, and details
        """
        buy_market = request.buy_market.upper()
        sell_market = request.sell_market.upper()
        trade_date = request.trade_date
        execution_time = request.execution_time
        
        # Get market configurations
        try:
            buy_market_obj = get_market(buy_market)
            sell_market_obj = get_market(sell_market)
        except ValueError as e:
            return SettlementResult.create_unlikely(
                trade_date=trade_date,
                buy_market=buy_market,
                sell_market=sell_market,
                message=f"Unknown market: {e}",
                warnings=[str(e)]
            )
        
        # Step 1: Validate trade date
        trade_date_validation = self._validate_trade_date(
            trade_date, buy_market, sell_market
        )
        
        if not trade_date_validation.valid:
            # Find next viable date
            next_viable = self.calendar_service.find_next_viable_trade_date(
                buy_market, sell_market, trade_date
            )
            return SettlementResult.create_unlikely(
                trade_date=trade_date,
                buy_market=buy_market,
                sell_market=sell_market,
                message=trade_date_validation.message,
                next_viable_date=next_viable,
                warnings=[trade_date_validation.message],
                details=self._build_settlement_details(
                    trade_date, buy_market, sell_market, buy_market_obj, sell_market_obj
                )
            )
        
        # Step 2 & 3: Check cut-off times (if execution time provided)
        cut_off_checks = []
        warnings = []
        
        if execution_time:
            buy_cut_off = self._check_cut_off_times(
                execution_time, buy_market, buy_market_obj
            )
            sell_cut_off = self._check_cut_off_times(
                execution_time, sell_market, sell_market_obj
            )
            cut_off_checks = [buy_cut_off, sell_cut_off]
            
            # Check if past cut-off
            if not buy_cut_off.is_before_cut_off:
                warnings.append(
                    f"Execution time is past {buy_market} depository cut-off "
                    f"({buy_cut_off.cut_off_time})"
                )
            if not sell_cut_off.is_before_cut_off:
                warnings.append(
                    f"Execution time is past {sell_market} depository cut-off "
                    f"({sell_cut_off.cut_off_time})"
                )
        
        # Step 4 & 5: Calculate settlement dates
        common_settlement_date, buy_result, sell_result = \
            self.calendar_service.calculate_common_settlement_date(
                buy_market, sell_market, trade_date
            )
        
        # Build detailed info
        details = self._build_settlement_details(
            trade_date, buy_market, sell_market,
            buy_market_obj, sell_market_obj,
            common_settlement_date, execution_time
        )
        
        # Build deadlines
        deadlines = self._build_deadlines(
            trade_date, buy_market_obj, sell_market_obj, execution_time
        )
        
        # Step 6: Determine status
        status = self._determine_status(
            trade_date_validation=trade_date_validation,
            cut_off_checks=cut_off_checks,
            buy_settlement_result=buy_result,
            sell_settlement_result=sell_result,
            common_settlement_date=common_settlement_date,
            execution_time=execution_time
        )
        
        # Build result based on status
        if status == SettlementStatusEnum.LIKELY:
            return SettlementResult.create_likely(
                trade_date=trade_date,
                settlement_date=common_settlement_date,
                buy_market=buy_market,
                sell_market=sell_market,
                message=self._build_likely_message(
                    trade_date, common_settlement_date, buy_market, sell_market
                ),
                deadlines=deadlines,
                details=details
            )
        
        elif status == SettlementStatusEnum.AT_RISK:
            return SettlementResult.create_at_risk(
                trade_date=trade_date,
                settlement_date=common_settlement_date,
                buy_market=buy_market,
                sell_market=sell_market,
                message=self._build_at_risk_message(
                    trade_date, common_settlement_date, buy_market, sell_market,
                    warnings
                ),
                warnings=warnings,
                deadlines=deadlines,
                details=details
            )
        
        else:  # UNLIKELY
            next_viable = self.calendar_service.find_next_viable_trade_date(
                buy_market, sell_market, trade_date + timedelta(days=1)
            )
            return SettlementResult.create_unlikely(
                trade_date=trade_date,
                buy_market=buy_market,
                sell_market=sell_market,
                message=self._build_unlikely_message(
                    trade_date, buy_market, sell_market, warnings
                ),
                next_viable_date=next_viable,
                warnings=warnings,
                details=details
            )
    
    def _validate_trade_date(
        self, 
        trade_date: date, 
        market_a: str, 
        market_b: str
    ) -> ValidationResult:
        """
        Validate that the trade date is a business day in both markets.
        
        Returns:
            ValidationResult with valid bool and message
        """
        is_trading_a = self.calendar_service.is_trading_day(market_a, trade_date)
        is_trading_b = self.calendar_service.is_trading_day(market_b, trade_date)
        
        if is_trading_a and is_trading_b:
            return ValidationResult(
                valid=True,
                message="Trade date is valid for both markets",
                details={"market_a_open": True, "market_b_open": True}
            )
        
        # Build message explaining why invalid
        messages = []
        details = {}
        
        if not is_trading_a:
            holiday_a = self.calendar_service.get_holiday_info(market_a, trade_date)
            reason_a = holiday_a.name if holiday_a else "Market closed"
            messages.append(f"{market_a}: {reason_a}")
            details["market_a_open"] = False
            details["market_a_reason"] = reason_a
        else:
            details["market_a_open"] = True
        
        if not is_trading_b:
            holiday_b = self.calendar_service.get_holiday_info(market_b, trade_date)
            reason_b = holiday_b.name if holiday_b else "Market closed"
            messages.append(f"{market_b}: {reason_b}")
            details["market_b_open"] = False
            details["market_b_reason"] = reason_b
        else:
            details["market_b_open"] = True
        
        return ValidationResult(
            valid=False,
            message=f"Trade date {trade_date} is not valid. " + "; ".join(messages),
            details=details
        )
    
    def _check_cut_off_times(
        self,
        execution_time: datetime,
        market_code: str,
        market: Market
    ) -> CutOffCheck:
        """
        Check if execution time is before the settlement cut-off.
        
        Returns:
            CutOffCheck with result details
        """
        cut_off_time = market.depository_cut_off
        
        if cut_off_time is None:
            return CutOffCheck(
                market_code=market_code,
                cut_off_time=None,
                execution_time=execution_time,
                is_before_cut_off=True,
                message="No depository cut-off defined"
            )
        
        # Convert execution time to market's local timezone
        exec_local = self.timezone_service.convert_from_utc(
            execution_time if execution_time.tzinfo else 
            execution_time.replace(tzinfo=self.timezone_service._utc),
            market.timezone
        )
        exec_time_only = exec_local.time()
        
        is_before = exec_time_only < cut_off_time
        
        # Calculate time remaining
        time_remaining = None
        if is_before:
            cut_off_dt = datetime.combine(exec_local.date(), cut_off_time)
            exec_dt = datetime.combine(exec_local.date(), exec_time_only)
            time_remaining = cut_off_dt - exec_dt
        
        return CutOffCheck(
            market_code=market_code,
            cut_off_time=cut_off_time,
            execution_time=execution_time,
            is_before_cut_off=is_before,
            time_remaining=time_remaining,
            message=f"{'Before' if is_before else 'After'} cut-off ({cut_off_time})"
        )
    
    def _calculate_settlement_date(
        self, 
        trade_date: date, 
        market_code: str
    ) -> date:
        """
        Calculate the settlement date (T+1) for a market.
        
        Returns:
            Settlement date
        """
        result = self.calendar_service.calculate_settlement_date(
            market_code, trade_date
        )
        return result.settlement_date
    
    def _find_common_settlement_date(
        self, 
        market_a: str, 
        market_b: str, 
        trade_date: date
    ) -> Optional[date]:
        """
        Find the earliest common settlement date for both markets.
        
        Returns:
            Common settlement date, or None if not found within reasonable window
        """
        try:
            common_date, _, _ = self.calendar_service.calculate_common_settlement_date(
                market_a, market_b, trade_date
            )
            return common_date
        except ValueError:
            return None
    
    def _determine_status(
        self,
        trade_date_validation: ValidationResult,
        cut_off_checks: List[CutOffCheck],
        buy_settlement_result: SettlementDateResult,
        sell_settlement_result: SettlementDateResult,
        common_settlement_date: date,
        execution_time: Optional[datetime]
    ) -> SettlementStatusEnum:
        """
        Determine the overall settlement status based on validation checks.
        
        Returns:
            SettlementStatusEnum value
        """
        # If trade date is invalid, settlement is unlikely
        if not trade_date_validation.valid:
            return SettlementStatusEnum.UNLIKELY
        
        # Check if any cut-off has passed
        any_past_cut_off = any(
            not check.is_before_cut_off 
            for check in cut_off_checks
        )
        
        if any_past_cut_off:
            return SettlementStatusEnum.UNLIKELY
        
        # Check if close to cut-off (at risk)
        if execution_time and cut_off_checks:
            for check in cut_off_checks:
                if check.time_remaining:
                    minutes_remaining = check.time_remaining.total_seconds() / 60
                    if minutes_remaining < self.AT_RISK_THRESHOLD_MINUTES:
                        return SettlementStatusEnum.AT_RISK
        
        # Check if settlement requires skipping many days
        max_days_to_settle = max(
            buy_settlement_result.days_to_settle,
            sell_settlement_result.days_to_settle
        )
        
        if max_days_to_settle > 3:
            # Settlement delayed significantly (e.g., over long holiday)
            return SettlementStatusEnum.AT_RISK
        
        return SettlementStatusEnum.LIKELY
    
    def _build_settlement_details(
        self,
        trade_date: date,
        buy_market: str,
        sell_market: str,
        buy_market_obj: Market,
        sell_market_obj: Market,
        settlement_date: Optional[date] = None,
        execution_time: Optional[datetime] = None
    ) -> SettlementDetails:
        """Build detailed settlement breakdown."""
        
        # Trade date info for both markets
        buy_trade_info = self._build_market_day_info(
            buy_market, trade_date, buy_market_obj
        )
        sell_trade_info = self._build_market_day_info(
            sell_market, trade_date, sell_market_obj
        )
        
        # Settlement date info
        buy_settle_info = None
        sell_settle_info = None
        if settlement_date:
            buy_settle_info = self._build_market_day_info(
                buy_market, settlement_date, buy_market_obj
            )
            sell_settle_info = self._build_market_day_info(
                sell_market, settlement_date, sell_market_obj
            )
        
        # Get overlap info
        has_overlap = False
        overlap_start = None
        overlap_end = None
        overlap_duration = None
        
        overlaps = self.calendar_service.get_trading_overlap_for_date(
            buy_market, sell_market, trade_date
        )
        
        if overlaps:
            has_overlap = True
            # Use the first and last overlap windows
            overlap_start = overlaps[0].start_utc
            overlap_end = overlaps[-1].end_utc
            overlap_duration = sum(o.duration_minutes for o in overlaps)
        
        # Check execution time validity
        execution_valid = None
        execution_before_cut_off = None
        
        if execution_time and overlaps:
            # Check if execution is within any overlap window
            exec_utc = execution_time if execution_time.tzinfo else \
                execution_time.replace(tzinfo=self.timezone_service._utc)
            
            execution_valid = any(
                o.start_utc <= exec_utc <= o.end_utc
                for o in overlaps
            )
            
            # Check cut-offs
            buy_cut_off = self._check_cut_off_times(
                execution_time, buy_market, buy_market_obj
            )
            sell_cut_off = self._check_cut_off_times(
                execution_time, sell_market, sell_market_obj
            )
            execution_before_cut_off = (
                buy_cut_off.is_before_cut_off and 
                sell_cut_off.is_before_cut_off
            )
        
        return SettlementDetails(
            trade_date_buy_market=buy_trade_info,
            trade_date_sell_market=sell_trade_info,
            settlement_date_buy_market=buy_settle_info,
            settlement_date_sell_market=sell_settle_info,
            has_trading_overlap=has_overlap,
            overlap_start_utc=overlap_start,
            overlap_end_utc=overlap_end,
            overlap_duration_minutes=overlap_duration,
            execution_time_valid=execution_valid,
            execution_before_cut_off=execution_before_cut_off
        )
    
    def _build_market_day_info(
        self,
        market_code: str,
        check_date: date,
        market: Market
    ) -> MarketDayInfo:
        """Build MarketDayInfo for a specific date."""
        is_trading = self.calendar_service.is_trading_day(market_code, check_date)
        is_settlement = self.calendar_service.is_settlement_day(market_code, check_date)
        holiday = self.calendar_service.get_holiday_info(market_code, check_date)
        
        return MarketDayInfo(
            market_code=market_code,
            date=check_date,
            is_trading_day=is_trading,
            is_settlement_day=is_settlement,
            holiday_name=holiday.name if holiday else None,
            trading_hours_start=market.trading_hours.open if is_trading else None,
            trading_hours_end=market.trading_hours.close if is_trading else None
        )
    
    def _build_deadlines(
        self,
        trade_date: date,
        buy_market: Market,
        sell_market: Market,
        execution_time: Optional[datetime]
    ) -> List[Deadline]:
        """Build list of relevant deadlines."""
        deadlines = []
        current_utc = self.timezone_service.get_current_time_utc()
        
        for market in [buy_market, sell_market]:
            if market.depository_cut_off:
                # Convert cut-off to UTC
                cut_off_utc = self.timezone_service.combine_date_time_utc(
                    trade_date, market.depository_cut_off, market.timezone
                )
                
                deadline = Deadline.create(
                    market_code=market.code,
                    deadline_type=DeadlineType.DEPOSITORY_CUT_OFF,
                    deadline_utc=cut_off_utc,
                    local_time=market.depository_cut_off,
                    description=f"{market.code} depository instruction cut-off",
                    current_time=current_utc
                )
                deadlines.append(deadline)
            
            # Add market close deadline
            close_utc = self.timezone_service.combine_date_time_utc(
                trade_date, market.trading_hours.close, market.timezone
            )
            
            close_deadline = Deadline.create(
                market_code=market.code,
                deadline_type=DeadlineType.MARKET_CLOSE,
                deadline_utc=close_utc,
                local_time=market.trading_hours.close,
                description=f"{market.code} market close",
                current_time=current_utc
            )
            deadlines.append(close_deadline)
        
        # Sort by deadline time
        deadlines.sort(key=lambda d: d.deadline_time)
        
        return deadlines
    
    def _build_likely_message(
        self,
        trade_date: date,
        settlement_date: date,
        buy_market: str,
        sell_market: str
    ) -> str:
        """Build message for LIKELY status."""
        days = (settlement_date - trade_date).days
        return (
            f"Settlement expected on {settlement_date} (T+{days}). "
            f"Both {buy_market} and {sell_market} markets are open for "
            f"trading and settlement."
        )
    
    def _build_at_risk_message(
        self,
        trade_date: date,
        settlement_date: date,
        buy_market: str,
        sell_market: str,
        warnings: List[str]
    ) -> str:
        """Build message for AT_RISK status."""
        days = (settlement_date - trade_date).days
        base_msg = (
            f"Settlement may occur on {settlement_date} (T+{days}), "
            f"but operational cut-off is imminent. "
        )
        
        if warnings:
            base_msg += "Issues: " + "; ".join(warnings)
        else:
            base_msg += "Immediate action required for confirmations."
        
        return base_msg
    
    def _build_unlikely_message(
        self,
        trade_date: date,
        buy_market: str,
        sell_market: str,
        warnings: List[str]
    ) -> str:
        """Build message for UNLIKELY status."""
        if warnings:
            return f"Settlement unlikely. " + "; ".join(warnings)
        
        return (
            f"Trade date {trade_date} is not valid for both markets. "
            f"Please select a common business day."
        )
    
    def get_market_status(self, market_code: str) -> MarketStatus:
        """
        Get the current status of a market.
        
        Args:
            market_code: Market code
            
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
    
    def get_market_pair_comparison(
        self,
        market_a: str,
        market_b: str
    ) -> MarketPairComparison:
        """
        Get comparison of two markets for current date.
        
        Args:
            market_a: First market code
            market_b: Second market code
            
        Returns:
            MarketPairComparison with both market statuses and overlap info
        """
        status_a = self.get_market_status(market_a)
        status_b = self.get_market_status(market_b)
        
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


# Singleton instance
_settlement_engine: Optional[SettlementEngine] = None


def get_settlement_engine() -> SettlementEngine:
    """Get the singleton SettlementEngine instance."""
    global _settlement_engine
    if _settlement_engine is None:
        _settlement_engine = SettlementEngine()
    return _settlement_engine

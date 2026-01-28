"""
Settlement check action component.
"""

import streamlit as st
from datetime import date, time, datetime

from app.models import SettlementCheckRequest
from app.services import get_settlement_engine


def perform_settlement_check(
    source_code: str,
    target_code: str,
    trade_date: date,
    execution_time: time,
    instrument_type: str
):
    """Perform settlement check and update session state."""
    engine = get_settlement_engine()
    try:
        execution_datetime = datetime.combine(trade_date, execution_time)
        request = SettlementCheckRequest(
            trade_date=trade_date,
            sell_market=source_code,
            buy_market=target_code,
            execution_time=execution_datetime,
            instrument_type=instrument_type
        )
        result = engine.check_settlement(request)
        st.session_state.settlement_result = result
    except Exception as e:
        st.error(f"Error checking settlement: {e}")
        st.session_state.settlement_result = None

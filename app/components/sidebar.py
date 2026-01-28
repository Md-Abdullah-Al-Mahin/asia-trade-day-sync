"""
Sidebar control panel component.
"""

import streamlit as st
from datetime import date, time, datetime, timedelta
from typing import Optional, Tuple

from app.models import get_market_repository
from app.services import get_timezone_service, get_market_status_service
from app.config import INSTRUMENT_TYPES

from app.components.session_state import get_market_options


def render_sidebar() -> Tuple[Optional[str], Optional[str], date, time, str]:
    """
    Render sidebar control panel.

    Returns:
        Tuple of (market_a_code, market_b_code, trade_date, execution_time, instrument_type)
    """
    market_options = get_market_options()
    market_list = list(market_options.keys())

    with st.sidebar:
        st.header("Trade Parameters")
        st.divider()

        st.subheader("Markets")
        source_market = st.selectbox(
            "Source (Sell)",
            options=market_list,
            index=0,
            help="Market where the security is being sold",
        )
        target_market = st.selectbox(
            "Target (Buy)",
            options=market_list,
            index=1 if len(market_list) > 1 else 0,
            help="Market where the security is being purchased",
        )
        if source_market == target_market:
            st.warning("Same market selected for both sides")

        st.divider()
        st.subheader("Trade Timing")
        trade_date = st.date_input(
            "Trade Date",
            value=date.today(),
            min_value=date.today() - timedelta(days=30),
            max_value=date.today() + timedelta(days=365),
        )

        time_input_mode = st.radio(
            "Time input",
            options=["Slider", "Dropdown"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
        )
        if time_input_mode == "Slider":
            time_minutes = st.slider(
                "Execution time",
                min_value=0,
                max_value=23 * 60 + 59,
                value=10 * 60,
                step=15,
                format="%d min",
            )
            exec_hour = time_minutes // 60
            exec_minute = time_minutes % 60
            execution_time = time(exec_hour, exec_minute)
        else:
            c1, c2 = st.columns(2)
            with c1:
                exec_hour = st.selectbox("Hour", range(24), index=10, format_func=lambda x: f"{x:02d}")
            with c2:
                exec_minute = st.selectbox("Minute", [0, 15, 30, 45], index=0, format_func=lambda x: f"{x:02d}")
            execution_time = time(exec_hour, exec_minute)
        st.caption(f"Execution: {execution_time.strftime('%H:%M')}")

        st.divider()
        st.subheader("Instrument")
        instrument_type = st.selectbox("Type", options=INSTRUMENT_TYPES, index=0, label_visibility="collapsed")

        st.divider()
        with st.expander("Advanced"):
            st.checkbox("Consider pre-market", value=False)
            st.checkbox("Consider after-hours", value=False)
            st.number_input("Settlement override (days)", min_value=1, max_value=5, value=2)

        st.divider()
        check_clicked = st.button("Check Settlement", type="primary", use_container_width=True)
        if check_clicked:
            st.session_state.last_check_time = datetime.now()
            st.session_state.trigger_check = True
        if st.session_state.last_check_time:
            st.caption(f"Last check: {st.session_state.last_check_time.strftime('%H:%M:%S')}")

        st.divider()
        st.subheader("Quick Info")
        source_code = market_options[source_market]
        target_code = market_options[target_market]
        try:
            repo = get_market_repository()
            tz_service = get_timezone_service()
            ms = get_market_status_service()
            now_utc = datetime.utcnow()
            src = repo.get(source_code)
            tgt = repo.get(target_code)
            st.caption(f"{source_code}: {tz_service.convert_from_utc(now_utc, src.timezone).strftime('%H:%M')}")
            st.caption(f"{target_code}: {tz_service.convert_from_utc(now_utc, tgt.timezone).strftime('%H:%M')}")
            ss, ts = ms.get_market_status(source_code), ms.get_market_status(target_code)
            st.caption(f"Status: {source_code} {'Open' if ss.is_open else 'Closed'} · {target_code} {'Open' if ts.is_open else 'Closed'}")
        except Exception:
            st.caption("Market status unavailable")

    return (
        market_options[source_market],
        market_options[target_market],
        trade_date,
        execution_time,
        instrument_type,
    )

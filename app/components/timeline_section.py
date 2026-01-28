"""
Timeline (Gantt chart) section component.
"""

import streamlit as st
from datetime import date, time, datetime
from typing import Optional

from app.models import get_market_repository
from app.services import get_calendar_service
from app.visualizations import create_market_timeline


def render_timeline_chart(
    source_code: str,
    target_code: str,
    trade_date: date,
    execution_time: Optional[time] = None
):
    """
    Render the Gantt chart timeline visualization.
    """
    st.subheader("Market Timeline")
    col_opt1, col_opt2 = st.columns([3, 1])
    is_today = trade_date == date.today()
    show_current_time = False
    with col_opt1:
        if is_today:
            show_current_time = st.checkbox("Show current time on chart", value=True)
    with col_opt2:
        st.selectbox("Timezone", options=["UTC", "Local"], index=0, label_visibility="collapsed")

    exec_datetime = None
    if execution_time:
        exec_datetime = datetime.combine(trade_date, execution_time)
    if is_today and show_current_time and exec_datetime is None:
        exec_datetime = datetime.now()

    try:
        fig = create_market_timeline(
            market_a_code=source_code,
            market_b_code=target_code,
            target_date=trade_date,
            execution_time=exec_datetime
        )
        st.plotly_chart(fig, use_container_width=True)

        calendar_service = get_calendar_service()
        overlaps = calendar_service.get_trading_overlap_for_date(source_code, target_code, trade_date)

        if overlaps:
            total_mins = sum(w.duration_minutes for w in overlaps)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Overlap windows", len(overlaps), None)
            with col2:
                st.metric("Total overlap", f"{total_mins} min", None)
            with col3:
                repo = get_market_repository()
                sm, tm = repo.get(source_code), repo.get(target_code)
                latest = max(sm.trading_hours.close, tm.trading_hours.close)
                st.metric("Latest close", latest.strftime("%H:%M"), None)

            with st.expander("Overlap details"):
                for i, window in enumerate(overlaps, 1):
                    st.markdown(f"""
                    **Window {i}**
                    - UTC: {window.start_utc.strftime('%H:%M')} - {window.end_utc.strftime('%H:%M')}
                    - Duration: {window.duration_minutes} minutes
                    """)
        else:
            st.warning("No trading hour overlap on this date.")

    except Exception as e:
        st.error(f"Could not render timeline: {e}")
        calendar_service = get_calendar_service()
        try:
            overlaps = calendar_service.get_trading_overlap_for_date(source_code, target_code, trade_date)
            if overlaps:
                for i, window in enumerate(overlaps, 1):
                    st.markdown(f"- Window {i}: {window.start_utc.strftime('%H:%M')} - {window.end_utc.strftime('%H:%M')} UTC ({window.duration_minutes} min)")
        except Exception:
            st.info("Unable to calculate overlap information")

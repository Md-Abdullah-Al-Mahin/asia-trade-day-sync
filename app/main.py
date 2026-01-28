"""
Streamlit Dashboard Entry Point — Cross-Market T+1 Settlement
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from datetime import date

from app.components import (
    inject_styles,
    init_session_state,
    render_sidebar,
    render_settlement_status,
    render_market_info_cards,
    render_timeline_chart,
    render_calendar_view,
    render_current_time_indicator,
    perform_settlement_check,
)

st.set_page_config(
    page_title="Asia T+1 Settlement",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_styles()


def main():
    init_session_state()

    st.title("Cross-Market T+1 Settlement")
    st.caption("Analyze settlement feasibility for cross-border trades across Asian markets")
    st.divider()

    source_code, target_code, trade_date, execution_time, instrument_type = render_sidebar()

    col_time, col_refresh = st.columns([4, 1])
    with col_time:
        render_current_time_indicator(source_code, target_code)
    with col_refresh:
        st.checkbox("Auto-refresh", value=False, key="auto_refresh")
        if st.button("Refresh", key="manual_refresh", use_container_width=True):
            st.rerun()

    if st.session_state.get("trigger_check", False):
        perform_settlement_check(source_code, target_code, trade_date, execution_time, instrument_type)
        st.session_state.trigger_check = False

    col_status, col_info = st.columns([1, 1])
    with col_status:
        st.subheader("Settlement")
        render_settlement_status(st.session_state.settlement_result)
    with col_info:
        st.subheader("Markets")
        render_market_info_cards(source_code, target_code, trade_date)

    st.divider()
    render_timeline_chart(source_code, target_code, trade_date, execution_time)
    st.divider()
    render_calendar_view(source_code, target_code, trade_date)

    st.divider()
    st.caption(f"Asia T+1 Settlement Dashboard · {date.today().strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()

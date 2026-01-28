"""
Streamlit Dashboard Entry Point

Cross-Market T+1 Settlement Dashboard
"""

import sys
from pathlib import Path

# Add parent directory to path when running with streamlit
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

# Page configuration
st.set_page_config(
    page_title="Asia T+1 Settlement Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_styles()


def main():
    """Main dashboard application."""
    init_session_state()

    st.title("🌏 Cross-Market T+1 Settlement Dashboard")
    st.markdown("*Analyze settlement feasibility for cross-border trades across Asian markets*")
    st.markdown("---")

    source_code, target_code, trade_date, execution_time, instrument_type = render_sidebar()

    # Current time indicators
    col_time, col_refresh = st.columns([4, 1])
    with col_time:
        render_current_time_indicator(source_code, target_code)
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        auto_refresh = st.checkbox(
            "🔄 Auto-refresh",
            value=False,
            help="Automatically refresh time indicators every 30 seconds"
        )
        if auto_refresh:
            st.caption("Refreshing in 30s...")
        if st.button("🔄 Refresh", key="manual_refresh", use_container_width=True):
            st.rerun()

    if st.session_state.get('trigger_check', False):
        perform_settlement_check(source_code, target_code, trade_date, execution_time, instrument_type)
        st.session_state.trigger_check = False

    # Main layout
    col_status, col_info = st.columns([1, 1])
    with col_status:
        st.markdown("## 📊 Settlement Analysis")
        render_settlement_status(st.session_state.settlement_result)
    with col_info:
        st.markdown("## 🏛️ Market Information")
        render_market_info_cards(source_code, target_code, trade_date)

    st.markdown("---")
    render_timeline_chart(source_code, target_code, trade_date, execution_time)
    st.markdown("---")
    render_calendar_view(source_code, target_code, trade_date)

    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9em;">
        <p>📊 Asia T+1 Settlement Dashboard | Personal Project</p>
        <p>Data sources: exchange_calendars, holidays library | Last updated: {}</p>
    </div>
    """.format(date.today().strftime("%Y-%m-%d")), unsafe_allow_html=True)


if __name__ == "__main__":
    main()

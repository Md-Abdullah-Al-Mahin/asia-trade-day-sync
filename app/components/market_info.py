"""
Market information cards component.
"""

import streamlit as st
from datetime import date

from app.models import get_market_repository
from app.data import get_holiday_manager, get_special_cases_manager


def render_market_info_cards(source_code: str, target_code: str, trade_date: date):
    """Render market information in a simple two-column layout."""
    repo = get_market_repository()
    holiday_manager = get_holiday_manager()
    special_cases = get_special_cases_manager()
    source_market = repo.get(source_code)
    target_market = repo.get(target_code)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(source_market.name)
        st.caption(f"{source_market.code} · {source_market.timezone} · {source_market.currency}")
        st.caption(f"T+{source_market.settlement_cycle} · {source_market.trading_hours.open.strftime('%H:%M')}–{source_market.trading_hours.close.strftime('%H:%M')}")
        h = holiday_manager.get_holiday_info(source_code, trade_date)
        st.success("Open") if not h else st.error(f"Closed: {h.name}")
        for w in special_cases.check_special_conditions(source_code, trade_date).get("warnings", [])[:2]:
            st.warning(w)

    with col2:
        st.subheader(target_market.name)
        st.caption(f"{target_market.code} · {target_market.timezone} · {target_market.currency}")
        st.caption(f"T+{target_market.settlement_cycle} · {target_market.trading_hours.open.strftime('%H:%M')}–{target_market.trading_hours.close.strftime('%H:%M')}")
        h = holiday_manager.get_holiday_info(target_code, trade_date)
        st.success("Open") if not h else st.error(f"Closed: {h.name}")
        for w in special_cases.check_special_conditions(target_code, trade_date).get("warnings", [])[:2]:
            st.warning(w)

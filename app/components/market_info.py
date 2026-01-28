"""
Market information cards component.
"""

import streamlit as st
from datetime import date

from app.models import get_market_repository
from app.data import get_holiday_manager, get_special_cases_manager


def render_market_info_cards(source_code: str, target_code: str, trade_date: date):
    """Render market information cards."""
    repo = get_market_repository()
    holiday_manager = get_holiday_manager()
    special_cases = get_special_cases_manager()

    source_market = repo.get(source_code)
    target_market = repo.get(target_code)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"### 📤 {source_market.name}")
        st.markdown(f"""
        - **Code**: {source_market.code}
        - **Timezone**: {source_market.timezone}
        - **Currency**: {source_market.currency}
        - **Settlement**: T+{source_market.settlement_cycle}
        """)
        st.markdown(f"**Trading Hours**: {source_market.trading_hours.open.strftime('%H:%M')} - {source_market.trading_hours.close.strftime('%H:%M')}")
        holiday = holiday_manager.get_holiday_info(source_code, trade_date)
        if holiday:
            st.error(f"🚫 **Closed**: {holiday.name}")
        else:
            st.success("✅ **Open** on selected date")
        conditions = special_cases.check_special_conditions(source_code, trade_date)
        if conditions['warnings']:
            for warning in conditions['warnings'][:2]:
                st.warning(warning)

    with col2:
        st.markdown(f"### 📥 {target_market.name}")
        st.markdown(f"""
        - **Code**: {target_market.code}
        - **Timezone**: {target_market.timezone}
        - **Currency**: {target_market.currency}
        - **Settlement**: T+{target_market.settlement_cycle}
        """)
        st.markdown(f"**Trading Hours**: {target_market.trading_hours.open.strftime('%H:%M')} - {target_market.trading_hours.close.strftime('%H:%M')}")
        holiday = holiday_manager.get_holiday_info(target_code, trade_date)
        if holiday:
            st.error(f"🚫 **Closed**: {holiday.name}")
        else:
            st.success("✅ **Open** on selected date")
        conditions = special_cases.check_special_conditions(target_code, trade_date)
        if conditions['warnings']:
            for warning in conditions['warnings'][:2]:
                st.warning(warning)

"""
Calendar month view section component.
"""

import calendar as cal_module
import streamlit as st
from datetime import date, timedelta

from app.models import get_market_repository
from app.data import get_holiday_manager
from app.visualizations import create_calendar_month_view, get_month_summary


def render_calendar_view(source_code: str, target_code: str, trade_date: date):
    """
    Render the calendar month view visualization.
    """
    st.markdown("### 📅 Calendar View")

    repo = get_market_repository()
    source_market = repo.get(source_code)
    target_market = repo.get(target_code)

    col_date1, col_date2, col_date3 = st.columns([2, 1, 1])
    with col_date1:
        quick_date = st.date_input(
            "📆 Quick Date Selection",
            value=trade_date,
            min_value=date.today() - timedelta(days=365),
            max_value=date.today() + timedelta(days=365),
            help="Click to quickly change the trade date",
            key="calendar_quick_date"
        )
        if quick_date != trade_date:
            st.info(f"💡 Date changed to {quick_date.strftime('%B %d, %Y')}. Use sidebar to apply.")
    with col_date2:
        if st.button("📍 Today", key="jump_today", use_container_width=True):
            st.session_state.calendar_month = date.today().month
            st.session_state.calendar_year = date.today().year
            st.rerun()
    with col_date3:
        if st.button("🎯 Selected", key="jump_selected", use_container_width=True):
            st.session_state.calendar_month = trade_date.month
            st.session_state.calendar_year = trade_date.year
            st.rerun()

    col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
    with col_nav1:
        prev_month = trade_date.month - 1 if trade_date.month > 1 else 12
        prev_year = trade_date.year if trade_date.month > 1 else trade_date.year - 1
        if st.button("◀ Prev", key="prev_month", use_container_width=True):
            st.session_state.calendar_month = prev_month
            st.session_state.calendar_year = prev_year
    with col_nav2:
        display_month = getattr(st.session_state, 'calendar_month', trade_date.month)
        display_year = getattr(st.session_state, 'calendar_year', trade_date.year)
        month_name = cal_module.month_name[display_month]
        st.markdown(f"<h4 style='text-align: center; margin: 0;'>{month_name} {display_year}</h4>", unsafe_allow_html=True)
    with col_nav3:
        next_month = trade_date.month + 1 if trade_date.month < 12 else 1
        next_year = trade_date.year if trade_date.month < 12 else trade_date.year + 1
        if st.button("Next ▶", key="next_month", use_container_width=True):
            st.session_state.calendar_month = next_month
            st.session_state.calendar_year = next_year

    display_month = getattr(st.session_state, 'calendar_month', trade_date.month)
    display_year = getattr(st.session_state, 'calendar_year', trade_date.year)

    try:
        fig = create_calendar_month_view(
            market_a_code=source_code,
            market_b_code=target_code,
            year=display_year,
            month=display_month,
            selected_date=trade_date
        )
        st.plotly_chart(fig, use_container_width=True)

        summary = get_month_summary(source_code, target_code, display_year, display_month)
        st.markdown("#### 📊 Month Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="✅ Both Open", value=f"{summary['common_open']} days", help="Days when both markets are open for trading")
        with col2:
            st.metric(label=f"🟠 {source_market.name} Only", value=f"{summary['holiday_a_only']} days", help=f"Days when only {source_market.name} is closed")
        with col3:
            st.metric(label=f"🔵 {target_market.name} Only", value=f"{summary['holiday_b_only']} days", help=f"Days when only {target_market.name} is closed")
        with col4:
            st.metric(label="🔴 Both Closed", value=f"{summary['common_holiday']} days", help="Days when both markets are closed (holidays)")

        with st.expander("📋 Upcoming Holidays"):
            holiday_manager = get_holiday_manager()
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                st.markdown(f"**{source_market.name} ({source_code})**")
                holidays = holiday_manager.get_upcoming_holidays(source_code, days_ahead=60)
                if holidays:
                    for h in holidays[:8]:
                        st.markdown(f"- **{h.date.strftime('%b %d')}** ({h.date.strftime('%a')}): {h.name}")
                else:
                    st.markdown("_No holidays in next 60 days_")
            with col_h2:
                st.markdown(f"**{target_market.name} ({target_code})**")
                holidays = holiday_manager.get_upcoming_holidays(target_code, days_ahead=60)
                if holidays:
                    for h in holidays[:8]:
                        st.markdown(f"- **{h.date.strftime('%b %d')}** ({h.date.strftime('%a')}): {h.name}")
                else:
                    st.markdown("_No holidays in next 60 days_")

    except Exception as e:
        st.error(f"Could not render calendar: {e}")
        holiday_manager = get_holiday_manager()
        st.markdown("**Fallback - Upcoming Holidays:**")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{source_code}:**")
            for h in holiday_manager.get_upcoming_holidays(source_code, days_ahead=30)[:5]:
                st.markdown(f"- {h.date.strftime('%b %d')}: {h.name}")
        with col2:
            st.markdown(f"**{target_code}:**")
            for h in holiday_manager.get_upcoming_holidays(target_code, days_ahead=30)[:5]:
                st.markdown(f"- {h.date.strftime('%b %d')}: {h.name}")

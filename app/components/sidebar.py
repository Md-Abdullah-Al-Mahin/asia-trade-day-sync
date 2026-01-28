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
        st.header("🎛️ Trade Parameters")
        st.markdown("---")

        # Market Selection Section
        st.subheader("Markets")

        source_market = st.selectbox(
            "📤 Source Market (Sell)",
            options=market_list,
            index=0,
            help="Market where the security is being sold"
        )

        target_market = st.selectbox(
            "📥 Target Market (Buy)",
            options=market_list,
            index=1 if len(market_list) > 1 else 0,
            help="Market where the security is being purchased"
        )

        if source_market == target_market:
            st.warning("⚠️ Same market selected for both sides")

        st.markdown("---")

        # Date & Time Section
        st.subheader("Trade Timing")

        trade_date = st.date_input(
            "📅 Trade Date",
            value=date.today(),
            min_value=date.today() - timedelta(days=30),
            max_value=date.today() + timedelta(days=365),
            help="Date of the trade execution"
        )

        # Execution Time - Option to use slider or selectbox
        time_input_mode = st.radio(
            "Time Input Mode",
            options=["Slider", "Dropdown"],
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )

        if time_input_mode == "Slider":
            time_minutes = st.slider(
                "⏰ Execution Time",
                min_value=0,
                max_value=23 * 60 + 59,
                value=10 * 60,
                step=15,
                format="%d min",
                help="Drag to select execution time"
            )
            exec_hour = time_minutes // 60
            exec_minute = time_minutes % 60
            execution_time = time(exec_hour, exec_minute)

            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 10px 15px;
                border-radius: 8px;
                text-align: center;
                font-size: 1.2em;
                margin: 5px 0;
            ">
                ⏰ <strong>{execution_time.strftime('%H:%M')}</strong>
            </div>
            """, unsafe_allow_html=True)
        else:
            col1, col2 = st.columns(2)
            with col1:
                exec_hour = st.selectbox(
                    "Hour",
                    options=list(range(0, 24)),
                    index=10,
                    format_func=lambda x: f"{x:02d}"
                )
            with col2:
                exec_minute = st.selectbox(
                    "Minute",
                    options=[0, 15, 30, 45],
                    index=0,
                    format_func=lambda x: f"{x:02d}"
                )
            execution_time = time(exec_hour, exec_minute)
            st.caption(f"⏰ Execution Time: {execution_time.strftime('%H:%M')}")

        st.markdown("---")

        # Instrument Type
        st.subheader("Instrument")
        instrument_type = st.selectbox(
            "📈 Instrument Type",
            options=INSTRUMENT_TYPES,
            index=0,
            help="Type of security being traded"
        )

        st.markdown("---")

        # Advanced Options (collapsible)
        with st.expander("⚙️ Advanced Options"):
            st.checkbox(
                "Consider pre-market hours",
                value=False,
                help="Include pre-market session in analysis"
            )
            st.checkbox(
                "Consider after-hours",
                value=False,
                help="Include after-hours session in analysis"
            )
            st.number_input(
                "Settlement cycle override (days)",
                min_value=1,
                max_value=5,
                value=2,
                help="Override default T+N settlement cycle"
            )

        st.markdown("---")

        # Check Settlement Button
        check_clicked = st.button(
            "🔍 Check Settlement",
            type="primary",
            use_container_width=True,
            help="Analyze settlement feasibility"
        )

        if check_clicked:
            st.session_state.last_check_time = datetime.now()
            st.session_state.trigger_check = True

        if st.session_state.last_check_time:
            st.caption(f"Last checked: {st.session_state.last_check_time.strftime('%H:%M:%S')}")

        st.markdown("---")

        # Quick Info Section with Current Time Indicators
        st.subheader("ℹ️ Quick Info")
        market_status_service = get_market_status_service()
        tz_service = get_timezone_service()
        source_code = market_options[source_market]
        target_code = market_options[target_market]

        try:
            repo = get_market_repository()
            source_market_data = repo.get(source_code)
            target_market_data = repo.get(target_code)

            st.markdown("**🕐 Current Local Times:**")
            now_utc = datetime.utcnow()
            source_local = tz_service.convert_from_utc(now_utc, source_market_data.timezone)
            target_local = tz_service.convert_from_utc(now_utc, target_market_data.timezone)

            st.markdown(f"""
            <div style="font-family: monospace; font-size: 0.9em; margin: 5px 0;">
                🇯🇵 <strong>{source_code}</strong>: {source_local.strftime('%H:%M:%S')} ({source_market_data.timezone.split('/')[-1]})<br>
                🇭🇰 <strong>{target_code}</strong>: {target_local.strftime('%H:%M:%S')} ({target_market_data.timezone.split('/')[-1]})
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**📊 Market Status:**")
            source_status = market_status_service.get_market_status(source_code)
            target_status = market_status_service.get_market_status(target_code)

            source_emoji = "🟢" if source_status.is_open else "🔴"
            source_session = source_status.session if hasattr(source_status, 'session') else "Unknown"
            st.markdown(f"**{source_code}**: {source_emoji} {source_session}")

            target_emoji = "🟢" if target_status.is_open else "🔴"
            target_session = target_status.session if hasattr(target_status, 'session') else "Unknown"
            st.markdown(f"**{target_code}**: {target_emoji} {target_session}")

            if hasattr(source_status, 'next_change') and source_status.next_change:
                time_to_change = source_status.next_change - now_utc
                if time_to_change.total_seconds() > 0:
                    hours, remainder = divmod(int(time_to_change.total_seconds()), 3600)
                    minutes = remainder // 60
                    if hours > 0:
                        st.caption(f"⏳ {source_code} changes in {hours}h {minutes}m")
                    else:
                        st.caption(f"⏳ {source_code} changes in {minutes}m")

        except Exception:
            st.caption("Market status unavailable")

    return (
        market_options[source_market],
        market_options[target_market],
        trade_date,
        execution_time,
        instrument_type
    )

"""
Current time indicators component.
"""

import streamlit as st
from datetime import datetime

from app.models import get_market_repository
from app.services import get_timezone_service, get_market_status_service


def render_current_time_indicator(source_code: str, target_code: str):
    """
    Render current time indicators for both markets.
    """
    repo = get_market_repository()
    tz_service = get_timezone_service()
    market_status_service = get_market_status_service()

    source_market = repo.get(source_code)
    target_market = repo.get(target_code)

    if not source_market or not target_market:
        return

    now_utc = datetime.utcnow()
    source_local = tz_service.convert_from_utc(now_utc, source_market.timezone)
    target_local = tz_service.convert_from_utc(now_utc, target_market.timezone)

    try:
        source_status = market_status_service.get_market_status(source_code)
        target_status = market_status_service.get_market_status(target_code)
    except Exception:
        source_status = None
        target_status = None

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        source_emoji = "🟢" if (source_status and source_status.is_open) else "🔴"
        source_session = source_status.session if source_status else "Unknown"
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 15px;
            border-radius: 10px;
            text-align: center;
        ">
            <div style="font-size: 0.85em; opacity: 0.9;">📤 {source_market.name}</div>
            <div style="font-size: 1.8em; font-weight: bold; font-family: monospace;">
                {source_local.strftime('%H:%M:%S')}
            </div>
            <div style="font-size: 0.8em;">{source_emoji} {source_session}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        target_emoji = "🟢" if (target_status and target_status.is_open) else "🔴"
        target_session = target_status.session if target_status else "Unknown"
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 12px 15px;
            border-radius: 10px;
            text-align: center;
        ">
            <div style="font-size: 0.85em; opacity: 0.9;">📥 {target_market.name}</div>
            <div style="font-size: 1.8em; font-weight: bold; font-family: monospace;">
                {target_local.strftime('%H:%M:%S')}
            </div>
            <div style="font-size: 0.8em;">{target_emoji} {target_session}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="
            background: #343a40;
            color: white;
            padding: 12px 15px;
            border-radius: 10px;
            text-align: center;
        ">
            <div style="font-size: 0.85em; opacity: 0.9;">🌐 UTC</div>
            <div style="font-size: 1.4em; font-weight: bold; font-family: monospace;">
                {now_utc.strftime('%H:%M')}
            </div>
            <div style="font-size: 0.75em;">{now_utc.strftime('%Y-%m-%d')}</div>
        </div>
        """, unsafe_allow_html=True)

"""
Current time indicators component.
"""

import streamlit as st
from datetime import datetime

from app.models import get_market_repository
from app.services import get_timezone_service, get_market_status_service


def render_current_time_indicator(source_code: str, target_code: str):
    """Render current time for both markets using simple metrics."""
    repo = get_market_repository()
    tz_service = get_timezone_service()
    ms = get_market_status_service()

    source_market = repo.get(source_code)
    target_market = repo.get(target_code)
    if not source_market or not target_market:
        return

    now_utc = datetime.utcnow()
    src_local = tz_service.convert_from_utc(now_utc, source_market.timezone)
    tgt_local = tz_service.convert_from_utc(now_utc, target_market.timezone)

    try:
        src_status = ms.get_market_status(source_code)
        tgt_status = ms.get_market_status(target_code)
        src_label = "Open" if src_status.is_open else "Closed"
        tgt_label = "Open" if tgt_status.is_open else "Closed"
    except Exception:
        src_label = tgt_label = "—"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(source_market.name, src_local.strftime("%H:%M:%S"), src_label)
    with col2:
        st.metric(target_market.name, tgt_local.strftime("%H:%M:%S"), tgt_label)
    with col3:
        st.metric("UTC", now_utc.strftime("%H:%M"), now_utc.strftime("%Y-%m-%d"))

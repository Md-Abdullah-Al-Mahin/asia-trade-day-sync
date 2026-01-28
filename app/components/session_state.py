"""
Session state initialization and helpers.
"""

import streamlit as st

from app.models import get_market_repository


def get_market_options() -> dict:
    """Get available markets for dropdown."""
    repo = get_market_repository()
    markets = repo.list_all()
    return {f"{m.name} ({m.code})": m.code for m in markets}


def init_session_state():
    """Initialize session state variables."""
    if 'settlement_result' not in st.session_state:
        st.session_state.settlement_result = None
    if 'last_check_time' not in st.session_state:
        st.session_state.last_check_time = None
    if 'show_advanced' not in st.session_state:
        st.session_state.show_advanced = False

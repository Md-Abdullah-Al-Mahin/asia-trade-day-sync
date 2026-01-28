"""
Custom CSS for the dashboard. Kept minimal for a clean look.
"""

import streamlit as st

DASHBOARD_CSS = ""


def inject_styles():
    """Inject custom CSS (none for simplified look)."""
    if DASHBOARD_CSS:
        st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

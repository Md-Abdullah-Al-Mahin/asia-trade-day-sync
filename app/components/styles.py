"""
Custom CSS styles for the Streamlit dashboard.
"""

import streamlit as st

DASHBOARD_CSS = """
<style>
    /* Status box styles */
    .status-likely {
        background-color: #d4edda;
        border: 2px solid #28a745;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .status-at-risk {
        background-color: #fff3cd;
        border: 2px solid #ffc107;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .status-unlikely {
        background-color: #f8d7da;
        border: 2px solid #dc3545;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    
    /* Market info cards */
    .market-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    
    /* Deadline styles */
    .deadline-passed {
        color: #dc3545;
        font-weight: bold;
    }
    .deadline-warning {
        color: #ffc107;
        font-weight: bold;
    }
    .deadline-ok {
        color: #28a745;
    }
    
    /* Sidebar styling */
    .sidebar-section {
        margin-bottom: 20px;
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        padding: 15px;
        color: white;
        text-align: center;
    }
</style>
"""


def inject_styles():
    """Inject custom CSS into the Streamlit app."""
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

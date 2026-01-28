"""
Streamlit Dashboard Entry Point

Cross-Market T+1 Settlement Dashboard
"""

import sys
from pathlib import Path

# Add parent directory to path for imports when running with streamlit
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from datetime import date, time, datetime, timedelta
from typing import Optional, Tuple

# Import services and models
from app.models import get_market_repository, SettlementCheckRequest
from app.services import (
    get_settlement_engine,
    get_calendar_service,
    get_timezone_service,
    get_market_status_service,
)
from app.data import (
    get_holiday_manager,
    get_special_cases_manager,
)
from app.config import INSTRUMENT_TYPES


# Page configuration
st.set_page_config(
    page_title="Asia T+1 Settlement Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
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
""", unsafe_allow_html=True)


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
        
        # Source Market (Sell Side)
        source_market = st.selectbox(
            "📤 Source Market (Sell)",
            options=market_list,
            index=0,
            help="Market where the security is being sold"
        )
        
        # Target Market (Buy Side)
        target_market = st.selectbox(
            "📥 Target Market (Buy)",
            options=market_list,
            index=1 if len(market_list) > 1 else 0,
            help="Market where the security is being purchased"
        )
        
        # Warn if same market selected
        if source_market == target_market:
            st.warning("⚠️ Same market selected for both sides")
        
        st.markdown("---")
        
        # Date & Time Section
        st.subheader("Trade Timing")
        
        # Trade Date
        trade_date = st.date_input(
            "📅 Trade Date",
            value=date.today(),
            min_value=date.today() - timedelta(days=30),
            max_value=date.today() + timedelta(days=365),
            help="Date of the trade execution"
        )
        
        # Execution Time
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
            # Trigger settlement check (will be processed in main area)
            st.session_state.trigger_check = True
        
        # Show last check time
        if st.session_state.last_check_time:
            st.caption(f"Last checked: {st.session_state.last_check_time.strftime('%H:%M:%S')}")
        
        st.markdown("---")
        
        # Quick Info Section
        st.subheader("ℹ️ Quick Info")
        
        # Show current market status
        market_status_service = get_market_status_service()
        source_code = market_options[source_market]
        target_code = market_options[target_market]
        
        try:
            source_status = market_status_service.get_market_status(source_code)
            target_status = market_status_service.get_market_status(target_code)
            
            # Source market status
            source_emoji = "🟢" if source_status.is_open else "🔴"
            st.markdown(f"**{source_code}**: {source_emoji} {source_status.session}")
            
            # Target market status
            target_emoji = "🟢" if target_status.is_open else "🔴"
            st.markdown(f"**{target_code}**: {target_emoji} {target_status.session}")
            
        except Exception:
            st.caption("Market status unavailable")
    
    return (
        market_options[source_market],
        market_options[target_market],
        trade_date,
        execution_time,
        instrument_type
    )


def render_settlement_status(result):
    """Render the settlement status widget."""
    if result is None:
        st.info("👆 Configure parameters and click **Check Settlement** to analyze")
        return
    
    # Determine status styling
    status = result.status.value
    
    if status == "LIKELY":
        status_class = "status-likely"
        status_emoji = "🟢"
        status_color = "#28a745"
    elif status == "AT_RISK":
        status_class = "status-at-risk"
        status_emoji = "🟡"
        status_color = "#ffc107"
    else:
        status_class = "status-unlikely"
        status_emoji = "🔴"
        status_color = "#dc3545"
    
    # Main status display
    st.markdown(f"""
    <div class="{status_class}">
        <h1 style="margin: 0; color: {status_color};">{status_emoji}</h1>
        <h2 style="margin: 10px 0; color: {status_color};">SETTLEMENT {status}</h2>
        <p style="font-size: 1.1em; margin: 10px 0;">{result.message}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # Settlement details
    if result.settlement_details:
        details = result.settlement_details
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                label="📤 Source Settlement",
                value=details.source_settlement_date.strftime("%b %d") if details.source_settlement_date else "N/A",
                delta=f"T+{details.source_settlement_cycle}" if details.source_settlement_cycle else None
            )
        
        with col2:
            st.metric(
                label="📥 Target Settlement",
                value=details.target_settlement_date.strftime("%b %d") if details.target_settlement_date else "N/A",
                delta=f"T+{details.target_settlement_cycle}" if details.target_settlement_cycle else None
            )
        
        if details.common_settlement_date:
            st.success(f"✅ Common Settlement Date: **{details.common_settlement_date.strftime('%A, %B %d, %Y')}**")
    
    # Deadlines
    if result.deadlines:
        st.markdown("### ⏰ Key Deadlines")
        
        for deadline in result.deadlines:
            if deadline.is_passed:
                icon = "❌"
                style = "deadline-passed"
            elif deadline.time_remaining and deadline.time_remaining.total_seconds() < 3600:
                icon = "⚠️"
                style = "deadline-warning"
            else:
                icon = "✅"
                style = "deadline-ok"
            
            time_str = deadline.time.strftime("%H:%M") if deadline.time else "N/A"
            remaining = ""
            if deadline.time_remaining:
                hours = int(deadline.time_remaining.total_seconds() // 3600)
                mins = int((deadline.time_remaining.total_seconds() % 3600) // 60)
                if hours > 0:
                    remaining = f" ({hours}h {mins}m remaining)"
                else:
                    remaining = f" ({mins}m remaining)"
            
            st.markdown(f"<span class='{style}'>{icon} **{deadline.name}**: {time_str}{remaining}</span>", 
                       unsafe_allow_html=True)
    
    # Warnings
    if result.warnings:
        st.markdown("### ⚠️ Warnings")
        for warning in result.warnings:
            st.warning(warning)
    
    # Recommendations
    if result.recommendations:
        st.markdown("### 💡 Recommendations")
        for rec in result.recommendations:
            st.info(rec)


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
        
        # Market details
        st.markdown(f"""
        - **Code**: {source_market.code}
        - **Timezone**: {source_market.timezone}
        - **Currency**: {source_market.currency}
        - **Settlement**: T+{source_market.settlement_cycle}
        """)
        
        # Trading hours
        st.markdown(f"**Trading Hours**: {source_market.trading_hours.open.strftime('%H:%M')} - {source_market.trading_hours.close.strftime('%H:%M')}")
        
        # Holiday check
        holiday = holiday_manager.get_holiday_info(source_code, trade_date)
        if holiday:
            st.error(f"🚫 **Closed**: {holiday.name}")
        else:
            st.success("✅ **Open** on selected date")
        
        # Special conditions
        conditions = special_cases.check_special_conditions(source_code, trade_date)
        if conditions['warnings']:
            for warning in conditions['warnings'][:2]:
                st.warning(warning)
    
    with col2:
        st.markdown(f"### 📥 {target_market.name}")
        
        # Market details
        st.markdown(f"""
        - **Code**: {target_market.code}
        - **Timezone**: {target_market.timezone}
        - **Currency**: {target_market.currency}
        - **Settlement**: T+{target_market.settlement_cycle}
        """)
        
        # Trading hours
        st.markdown(f"**Trading Hours**: {target_market.trading_hours.open.strftime('%H:%M')} - {target_market.trading_hours.close.strftime('%H:%M')}")
        
        # Holiday check
        holiday = holiday_manager.get_holiday_info(target_code, trade_date)
        if holiday:
            st.error(f"🚫 **Closed**: {holiday.name}")
        else:
            st.success("✅ **Open** on selected date")
        
        # Special conditions
        conditions = special_cases.check_special_conditions(target_code, trade_date)
        if conditions['warnings']:
            for warning in conditions['warnings'][:2]:
                st.warning(warning)


def render_timeline_placeholder(source_code: str, target_code: str, trade_date: date):
    """Render placeholder for the timeline visualization."""
    st.markdown("### 📊 Market Timeline")
    st.info("📈 Interactive Gantt chart visualization will be implemented in Step 5.3")
    
    # Show basic timeline info
    calendar_service = get_calendar_service()
    
    try:
        overlaps = calendar_service.get_trading_overlap_for_date(source_code, target_code, trade_date)
        
        if overlaps:
            st.markdown("**Trading Hour Overlaps:**")
            total_mins = 0
            for i, window in enumerate(overlaps, 1):
                duration_mins = window.duration_minutes
                total_mins += duration_mins
                st.markdown(f"""
                - **Window {i}**: {window.start_utc.strftime('%H:%M')} - {window.end_utc.strftime('%H:%M')} UTC 
                  ({duration_mins} minutes)
                """)
            
            st.success(f"✅ Total overlap: **{total_mins} minutes**")
        else:
            st.warning("⚠️ No trading hour overlap found between these markets on this date")
    
    except Exception as e:
        st.error(f"Could not calculate overlap: {e}")


def render_calendar_placeholder(source_code: str, target_code: str, trade_date: date):
    """Render placeholder for the calendar view."""
    st.markdown("### 📅 Calendar View")
    st.info("🗓️ Interactive calendar visualization will be implemented in Step 5.4")
    
    # Show upcoming holidays
    holiday_manager = get_holiday_manager()
    calendar_service = get_calendar_service()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**{source_code} - Upcoming Holidays:**")
        holidays = holiday_manager.get_upcoming_holidays(source_code, days_ahead=30)
        if holidays:
            for h in holidays[:5]:
                st.markdown(f"- {h.date.strftime('%b %d')}: {h.name}")
        else:
            st.markdown("No holidays in next 30 days")
    
    with col2:
        st.markdown(f"**{target_code} - Upcoming Holidays:**")
        holidays = holiday_manager.get_upcoming_holidays(target_code, days_ahead=30)
        if holidays:
            for h in holidays[:5]:
                st.markdown(f"- {h.date.strftime('%b %d')}: {h.name}")
        else:
            st.markdown("No holidays in next 30 days")


def perform_settlement_check(source_code: str, target_code: str, trade_date: date, 
                            execution_time: time, instrument_type: str):
    """Perform settlement check and update session state."""
    engine = get_settlement_engine()
    
    try:
        # Create datetime for execution
        execution_datetime = datetime.combine(trade_date, execution_time)
        
        # Create request object
        request = SettlementCheckRequest(
            trade_date=trade_date,
            sell_market=source_code,  # Source = Sell side
            buy_market=target_code,   # Target = Buy side
            execution_time=execution_datetime,
            instrument_type=instrument_type
        )
        
        # Perform check
        result = engine.check_settlement(request)
        
        st.session_state.settlement_result = result
        
    except Exception as e:
        st.error(f"Error checking settlement: {e}")
        st.session_state.settlement_result = None


def main():
    """Main dashboard application."""
    # Initialize session state
    init_session_state()
    
    # Header
    st.title("🌏 Cross-Market T+1 Settlement Dashboard")
    st.markdown("*Analyze settlement feasibility for cross-border trades across Asian markets*")
    st.markdown("---")
    
    # Render sidebar and get parameters
    source_code, target_code, trade_date, execution_time, instrument_type = render_sidebar()
    
    # Check if settlement check was triggered
    if st.session_state.get('trigger_check', False):
        perform_settlement_check(source_code, target_code, trade_date, execution_time, instrument_type)
        st.session_state.trigger_check = False
    
    # Main layout
    # Row 1: Settlement Status and Market Info
    col_status, col_info = st.columns([1, 1])
    
    with col_status:
        st.markdown("## 📊 Settlement Analysis")
        render_settlement_status(st.session_state.settlement_result)
    
    with col_info:
        st.markdown("## 🏛️ Market Information")
        render_market_info_cards(source_code, target_code, trade_date)
    
    st.markdown("---")
    
    # Row 2: Timeline
    render_timeline_placeholder(source_code, target_code, trade_date)
    
    st.markdown("---")
    
    # Row 3: Calendar
    render_calendar_placeholder(source_code, target_code, trade_date)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9em;">
        <p>📊 Asia T+1 Settlement Dashboard | Personal Project</p>
        <p>Data sources: exchange_calendars, holidays library | Last updated: {}</p>
    </div>
    """.format(date.today().strftime("%Y-%m-%d")), unsafe_allow_html=True)


if __name__ == "__main__":
    main()

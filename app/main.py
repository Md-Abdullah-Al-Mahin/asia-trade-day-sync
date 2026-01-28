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
from app.visualizations import create_market_timeline, create_trading_hours_gantt


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
    """
    Render the settlement status widget.
    
    Large, color-coded result card showing:
    - Clear status message
    - Settlement date
    - Key deadlines
    - Actionable recommendations
    """
    if result is None:
        # Show placeholder when no result yet
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
            border: 2px dashed #ccc;
            border-radius: 15px;
            padding: 40px 20px;
            text-align: center;
        ">
            <p style="font-size: 3em; margin: 0;">📊</p>
            <h3 style="color: #666; margin: 15px 0;">Settlement Analysis</h3>
            <p style="color: #888; margin: 10px 0;">
                Configure trade parameters in the sidebar and click<br>
                <strong style="color: #0066cc;">🔍 Check Settlement</strong> to analyze
            </p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Determine status styling
    status = result.status.value
    
    if status == "LIKELY":
        status_class = "status-likely"
        status_emoji = "🟢"
        status_color = "#28a745"
        bg_gradient = "linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%)"
        border_color = "#28a745"
        icon_bg = "#28a745"
    elif status == "AT_RISK":
        status_class = "status-at-risk"
        status_emoji = "🟡"
        status_color = "#856404"
        bg_gradient = "linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%)"
        border_color = "#ffc107"
        icon_bg = "#ffc107"
    else:
        status_class = "status-unlikely"
        status_emoji = "🔴"
        status_color = "#721c24"
        bg_gradient = "linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%)"
        border_color = "#dc3545"
        icon_bg = "#dc3545"
    
    # Main status card
    st.markdown(f"""
    <div style="
        background: {bg_gradient};
        border: 3px solid {border_color};
        border-radius: 15px;
        padding: 25px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    ">
        <div style="
            display: inline-block;
            background: {icon_bg};
            border-radius: 50%;
            width: 80px;
            height: 80px;
            line-height: 80px;
            margin-bottom: 15px;
        ">
            <span style="font-size: 2.5em;">{status_emoji}</span>
        </div>
        <h2 style="margin: 10px 0; color: {status_color}; font-size: 1.8em;">
            SETTLEMENT {status.replace('_', ' ')}
        </h2>
        <p style="font-size: 1.15em; margin: 15px 0; color: {status_color};">
            {result.message}
        </p>
        <div style="
            background: rgba(255,255,255,0.7);
            border-radius: 8px;
            padding: 10px;
            margin-top: 15px;
        ">
            <span style="font-size: 0.9em; color: #666;">
                📅 Trade Date: <strong>{result.trade_date.strftime('%B %d, %Y')}</strong> | 
                🔄 {result.market_pair}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Settlement Date Display
    if result.settlement_date:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            color: white;
            margin-bottom: 20px;
        ">
            <p style="margin: 0; font-size: 0.9em; opacity: 0.9;">Expected Settlement Date</p>
            <h2 style="margin: 5px 0; font-size: 1.6em;">
                📆 {result.settlement_date.strftime('%A, %B %d, %Y')}
            </h2>
            <p style="margin: 5px 0; font-size: 1em; opacity: 0.9;">
                {result.settlement_cycle_label} Settlement
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Settlement details breakdown
    if result.details:
        details = result.details
        
        st.markdown("#### 📋 Settlement Breakdown")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Sell market info
            sell_info = details.trade_date_sell_market
            st.markdown(f"""
            <div style="
                background: #f8f9fa;
                border-left: 4px solid #dc3545;
                border-radius: 5px;
                padding: 15px;
                margin: 10px 0;
            ">
                <h4 style="margin: 0 0 10px 0; color: #dc3545;">📤 Sell Market ({result.sell_market})</h4>
                <p style="margin: 5px 0;"><strong>Trade Date:</strong> {sell_info.date.strftime('%b %d, %Y') if sell_info else 'N/A'}</p>
                <p style="margin: 5px 0;"><strong>Is Trading Day:</strong> {'✅ Yes' if sell_info and sell_info.is_trading_day else '❌ No'}</p>
                <p style="margin: 5px 0;"><strong>Is Settlement Day:</strong> {'✅ Yes' if sell_info and sell_info.is_settlement_day else '❌ No'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if details.settlement_date_sell_market:
                settle_sell = details.settlement_date_sell_market
                st.markdown(f"""
                <div style="
                    background: #e8f5e9;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 5px 0;
                    text-align: center;
                ">
                    <small>Settlement: <strong>{settle_sell.date.strftime('%b %d')}</strong></small>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            # Buy market info
            buy_info = details.trade_date_buy_market
            st.markdown(f"""
            <div style="
                background: #f8f9fa;
                border-left: 4px solid #28a745;
                border-radius: 5px;
                padding: 15px;
                margin: 10px 0;
            ">
                <h4 style="margin: 0 0 10px 0; color: #28a745;">📥 Buy Market ({result.buy_market})</h4>
                <p style="margin: 5px 0;"><strong>Trade Date:</strong> {buy_info.date.strftime('%b %d, %Y') if buy_info else 'N/A'}</p>
                <p style="margin: 5px 0;"><strong>Is Trading Day:</strong> {'✅ Yes' if buy_info and buy_info.is_trading_day else '❌ No'}</p>
                <p style="margin: 5px 0;"><strong>Is Settlement Day:</strong> {'✅ Yes' if buy_info and buy_info.is_settlement_day else '❌ No'}</p>
            </div>
            """, unsafe_allow_html=True)
            
            if details.settlement_date_buy_market:
                settle_buy = details.settlement_date_buy_market
                st.markdown(f"""
                <div style="
                    background: #e8f5e9;
                    border-radius: 5px;
                    padding: 10px;
                    margin: 5px 0;
                    text-align: center;
                ">
                    <small>Settlement: <strong>{settle_buy.date.strftime('%b %d')}</strong></small>
                </div>
                """, unsafe_allow_html=True)
        
        # Overlap info
        if details.has_trading_overlap:
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%);
                border-radius: 8px;
                padding: 15px;
                margin: 15px 0;
                text-align: center;
            ">
                <span style="font-size: 1.5em;">⏱️</span>
                <strong> Trading Hour Overlap: {details.overlap_duration_minutes or 0} minutes</strong>
                {f"<br><small>Window: {details.overlap_start_utc.strftime('%H:%M')} - {details.overlap_end_utc.strftime('%H:%M')} UTC</small>" if details.overlap_start_utc and details.overlap_end_utc else ""}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="
                background: #fff3cd;
                border-radius: 8px;
                padding: 15px;
                margin: 15px 0;
                text-align: center;
            ">
                <span style="font-size: 1.5em;">⚠️</span>
                <strong> No Trading Hour Overlap</strong>
                <br><small>Markets do not have overlapping trading hours on this date</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Key Deadlines Section
    if result.deadlines:
        st.markdown("#### ⏰ Key Deadlines")
        
        for deadline in result.deadlines:
            # Determine deadline status
            if deadline.is_passed:
                icon = "❌"
                bg_color = "#f8d7da"
                text_color = "#721c24"
                status_text = "PASSED"
            elif deadline.time_remaining:
                # time_remaining is a string like "2h 30m"
                icon = "✅"
                bg_color = "#d4edda"
                text_color = "#155724"
                status_text = deadline.time_remaining
            else:
                icon = "📌"
                bg_color = "#e2e3e5"
                text_color = "#383d41"
                status_text = ""
            
            # Use local_time for display
            time_str = deadline.local_time.strftime("%H:%M") if deadline.local_time else "N/A"
            deadline_name = deadline.description or deadline.deadline_type.value.replace("_", " ").title()
            
            st.markdown(f"""
            <div style="
                background: {bg_color};
                border-radius: 8px;
                padding: 12px 15px;
                margin: 8px 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            ">
                <div>
                    <span style="font-size: 1.2em;">{icon}</span>
                    <strong style="color: {text_color}; margin-left: 8px;">{deadline_name}</strong>
                    <span style="color: {text_color}; margin-left: 10px;">({deadline.market_code}) {time_str}</span>
                </div>
                <div>
                    <span style="
                        background: rgba(0,0,0,0.1);
                        padding: 4px 10px;
                        border-radius: 15px;
                        font-size: 0.85em;
                        color: {text_color};
                    ">{status_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Warnings Section
    if result.warnings:
        st.markdown("#### ⚠️ Warnings")
        for warning in result.warnings:
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, #fff3cd 0%, #ffe69c 100%);
                border-left: 4px solid #ffc107;
                border-radius: 5px;
                padding: 12px 15px;
                margin: 8px 0;
            ">
                <span style="font-size: 1.1em;">⚠️</span>
                <span style="margin-left: 8px; color: #856404;">{warning}</span>
            </div>
            """, unsafe_allow_html=True)
    
    # Recommendations Section
    if result.recommendations:
        st.markdown("#### 💡 Recommendations")
        for i, rec in enumerate(result.recommendations, 1):
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%);
                border-left: 4px solid #2196f3;
                border-radius: 5px;
                padding: 12px 15px;
                margin: 8px 0;
            ">
                <span style="
                    background: #2196f3;
                    color: white;
                    border-radius: 50%;
                    width: 24px;
                    height: 24px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 0.8em;
                    margin-right: 10px;
                ">{i}</span>
                <span style="color: #0d47a1;">{rec}</span>
            </div>
            """, unsafe_allow_html=True)
    
    # Summary footer
    st.markdown(f"""
    <div style="
        background: #f8f9fa;
        border-radius: 8px;
        padding: 10px 15px;
        margin-top: 20px;
        text-align: center;
        font-size: 0.85em;
        color: #666;
    ">
        Analysis completed • {result.buy_market} ↔ {result.sell_market} • 
        Trade: {result.trade_date.strftime('%b %d')} → Settlement: {result.settlement_date.strftime('%b %d') if result.settlement_date else 'TBD'}
    </div>
    """, unsafe_allow_html=True)


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


def render_timeline_chart(
    source_code: str, 
    target_code: str, 
    trade_date: date,
    execution_time: Optional[time] = None
):
    """
    Render the Gantt chart timeline visualization.
    
    Shows:
    - Trading hours (green bars)
    - Non-trading hours (gray)
    - Holidays (red bar across day)
    - Lunch breaks (hatched/lighter)
    - Cut-off times (amber vertical line)
    - Execution time marker
    """
    st.markdown("### 📊 Market Timeline")
    
    # Create execution datetime if provided
    exec_datetime = None
    if execution_time:
        exec_datetime = datetime.combine(trade_date, execution_time)
    
    try:
        # Create the Gantt chart
        fig = create_market_timeline(
            market_a_code=source_code,
            market_b_code=target_code,
            target_date=trade_date,
            execution_time=exec_datetime
        )
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
        
        # Show overlap summary below the chart
        calendar_service = get_calendar_service()
        overlaps = calendar_service.get_trading_overlap_for_date(source_code, target_code, trade_date)
        
        if overlaps:
            total_mins = sum(w.duration_minutes for w in overlaps)
            
            # Create a summary row
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    label="🔄 Overlap Windows",
                    value=len(overlaps),
                    help="Number of overlapping trading periods"
                )
            
            with col2:
                st.metric(
                    label="⏱️ Total Overlap",
                    value=f"{total_mins} min",
                    help="Total minutes of overlapping trading hours"
                )
            
            with col3:
                # Get market close times
                repo = get_market_repository()
                source_market = repo.get(source_code)
                target_market = repo.get(target_code)
                
                latest_close = max(
                    source_market.trading_hours.close,
                    target_market.trading_hours.close
                )
                st.metric(
                    label="🏁 Latest Close",
                    value=latest_close.strftime("%H:%M"),
                    help="Latest market close time (local)"
                )
            
            # Detailed overlap windows in expander
            with st.expander("📋 Overlap Window Details"):
                for i, window in enumerate(overlaps, 1):
                    st.markdown(f"""
                    **Window {i}**
                    - UTC: {window.start_utc.strftime('%H:%M')} - {window.end_utc.strftime('%H:%M')}
                    - Duration: {window.duration_minutes} minutes
                    """)
        else:
            st.warning("⚠️ No trading hour overlap found between these markets on this date")
            st.markdown("""
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-top: 10px;">
                <strong>Why no overlap?</strong><br>
                The selected markets may have non-overlapping trading hours, or one/both markets 
                may be closed (holiday/weekend) on this date.
            </div>
            """, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"Could not render timeline: {e}")
        # Show fallback text-based info
        st.markdown("**Fallback Information:**")
        calendar_service = get_calendar_service()
        try:
            overlaps = calendar_service.get_trading_overlap_for_date(source_code, target_code, trade_date)
            if overlaps:
                for i, window in enumerate(overlaps, 1):
                    st.markdown(f"- Window {i}: {window.start_utc.strftime('%H:%M')} - {window.end_utc.strftime('%H:%M')} UTC ({window.duration_minutes} min)")
        except:
            st.info("Unable to calculate overlap information")


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
    
    # Row 2: Timeline (Gantt Chart)
    render_timeline_chart(source_code, target_code, trade_date, execution_time)
    
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

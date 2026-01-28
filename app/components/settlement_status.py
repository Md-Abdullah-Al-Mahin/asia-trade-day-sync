"""
Settlement status widget component.
"""

import streamlit as st
from typing import Optional

from app.models import SettlementResult


def render_settlement_status(result: Optional[SettlementResult]):
    """
    Render the settlement status widget.

    Large, color-coded result card showing:
    - Clear status message
    - Settlement date
    - Key deadlines
    - Actionable recommendations
    """
    if result is None:
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

    status = result.status.value

    if status == "LIKELY":
        status_emoji = "🟢"
        status_color = "#28a745"
        bg_gradient = "linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%)"
        border_color = "#28a745"
        icon_bg = "#28a745"
    elif status == "AT_RISK":
        status_emoji = "🟡"
        status_color = "#856404"
        bg_gradient = "linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%)"
        border_color = "#ffc107"
        icon_bg = "#ffc107"
    else:
        status_emoji = "🔴"
        status_color = "#721c24"
        bg_gradient = "linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%)"
        border_color = "#dc3545"
        icon_bg = "#dc3545"

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

    if result.details:
        details = result.details
        st.markdown("#### 📋 Settlement Breakdown")
        col1, col2 = st.columns(2)

        with col1:
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
                <div style="background: #e8f5e9; border-radius: 5px; padding: 10px; margin: 5px 0; text-align: center;">
                    <small>Settlement: <strong>{settle_sell.date.strftime('%b %d')}</strong></small>
                </div>
                """, unsafe_allow_html=True)

        with col2:
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
                <div style="background: #e8f5e9; border-radius: 5px; padding: 10px; margin: 5px 0; text-align: center;">
                    <small>Settlement: <strong>{settle_buy.date.strftime('%b %d')}</strong></small>
                </div>
                """, unsafe_allow_html=True)

        if details.has_trading_overlap:
            overlap_extra = f"<br><small>Window: {details.overlap_start_utc.strftime('%H:%M')} - {details.overlap_end_utc.strftime('%H:%M')} UTC</small>" if details.overlap_start_utc and details.overlap_end_utc else ""
            st.markdown(f"""
            <div style="background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 8px; padding: 15px; margin: 15px 0; text-align: center;">
                <span style="font-size: 1.5em;">⏱️</span>
                <strong> Trading Hour Overlap: {details.overlap_duration_minutes or 0} minutes</strong>{overlap_extra}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: #fff3cd; border-radius: 8px; padding: 15px; margin: 15px 0; text-align: center;">
                <span style="font-size: 1.5em;">⚠️</span>
                <strong> No Trading Hour Overlap</strong>
                <br><small>Markets do not have overlapping trading hours on this date</small>
            </div>
            """, unsafe_allow_html=True)

    if result.deadlines:
        st.markdown("#### ⏰ Key Deadlines")
        for deadline in result.deadlines:
            if deadline.is_passed:
                icon, bg_color, text_color, status_text = "❌", "#f8d7da", "#721c24", "PASSED"
            elif deadline.time_remaining:
                icon, bg_color, text_color, status_text = "✅", "#d4edda", "#155724", deadline.time_remaining
            else:
                icon, bg_color, text_color, status_text = "📌", "#e2e3e5", "#383d41", ""
            time_str = deadline.local_time.strftime("%H:%M") if deadline.local_time else "N/A"
            deadline_name = deadline.description or deadline.deadline_type.value.replace("_", " ").title()
            st.markdown(f"""
            <div style="background: {bg_color}; border-radius: 8px; padding: 12px 15px; margin: 8px 0; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 1.2em;">{icon}</span>
                    <strong style="color: {text_color}; margin-left: 8px;">{deadline_name}</strong>
                    <span style="color: {text_color}; margin-left: 10px;">({deadline.market_code}) {time_str}</span>
                </div>
                <div>
                    <span style="background: rgba(0,0,0,0.1); padding: 4px 10px; border-radius: 15px; font-size: 0.85em; color: {text_color};">{status_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    if result.warnings:
        st.markdown("#### ⚠️ Warnings")
        for warning in result.warnings:
            st.markdown(f"""
            <div style="background: linear-gradient(90deg, #fff3cd 0%, #ffe69c 100%); border-left: 4px solid #ffc107; border-radius: 5px; padding: 12px 15px; margin: 8px 0;">
                <span style="font-size: 1.1em;">⚠️</span>
                <span style="margin-left: 8px; color: #856404;">{warning}</span>
            </div>
            """, unsafe_allow_html=True)

    if result.recommendations:
        st.markdown("#### 💡 Recommendations")
        for i, rec in enumerate(result.recommendations, 1):
            st.markdown(f"""
            <div style="background: linear-gradient(90deg, #e3f2fd 0%, #bbdefb 100%); border-left: 4px solid #2196f3; border-radius: 5px; padding: 12px 15px; margin: 8px 0;">
                <span style="background: #2196f3; color: white; border-radius: 50%; width: 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.8em; margin-right: 10px;">{i}</span>
                <span style="color: #0d47a1;">{rec}</span>
            </div>
            """, unsafe_allow_html=True)

    settle_str = result.settlement_date.strftime('%b %d') if result.settlement_date else 'TBD'
    st.markdown(f"""
    <div style="background: #f8f9fa; border-radius: 8px; padding: 10px 15px; margin-top: 20px; text-align: center; font-size: 0.85em; color: #666;">
        Analysis completed • {result.buy_market} ↔ {result.sell_market} •
        Trade: {result.trade_date.strftime('%b %d')} → Settlement: {settle_str}
    </div>
    """, unsafe_allow_html=True)

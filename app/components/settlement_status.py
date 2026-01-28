"""
Settlement status widget component.
"""

import streamlit as st
from typing import Optional

from app.models import SettlementResult


def render_settlement_status(result: Optional[SettlementResult]):
    """Render the settlement status widget with a simplified look."""
    if result is None:
        st.info("Configure trade parameters in the sidebar and click **Check Settlement** to analyze.")
        return

    status = result.status.value
    if status == "LIKELY":
        st.success(f"**Settlement likely** — {result.message}")
    elif status == "AT_RISK":
        st.warning(f"**Settlement at risk** — {result.message}")
    else:
        st.error(f"**Settlement unlikely** — {result.message}")

    st.caption(f"Trade: {result.trade_date.strftime('%b %d, %Y')} · {result.market_pair}")

    if result.settlement_date:
        st.metric(
            "Expected settlement",
            result.settlement_date.strftime("%A, %b %d"),
            result.settlement_cycle_label,
        )

    if result.details:
        details = result.details
        with st.expander("Settlement breakdown"):
            c1, c2 = st.columns(2)
            with c1:
                sell = details.trade_date_sell_market
                st.markdown(f"**Sell** {result.sell_market}")
                st.caption(f"Trading day: {'Yes' if sell and sell.is_trading_day else 'No'}")
                if details.settlement_date_sell_market:
                    st.caption(f"Settlement: {details.settlement_date_sell_market.date.strftime('%b %d')}")
            with c2:
                buy = details.trade_date_buy_market
                st.markdown(f"**Buy** {result.buy_market}")
                st.caption(f"Trading day: {'Yes' if buy and buy.is_trading_day else 'No'}")
                if details.settlement_date_buy_market:
                    st.caption(f"Settlement: {details.settlement_date_buy_market.date.strftime('%b %d')}")
            if details.has_trading_overlap:
                window = ""
                if details.overlap_start_utc and details.overlap_end_utc:
                    window = f" ({details.overlap_start_utc.strftime('%H:%M')}–{details.overlap_end_utc.strftime('%H:%M')} UTC)"
                st.caption(f"Overlap: {details.overlap_duration_minutes or 0} min{window}")
            else:
                st.caption("No trading hour overlap on this date.")

    if result.deadlines:
        st.write("**Deadlines**")
        for d in result.deadlines:
            time_str = d.local_time.strftime("%H:%M") if d.local_time else "—"
            name = d.description or d.deadline_type.value.replace("_", " ").title()
            status_str = "Passed" if d.is_passed else (d.time_remaining or "")
            st.caption(f"{name} ({d.market_code}) {time_str} — {status_str}")

    if result.warnings:
        for w in result.warnings:
            st.warning(w)

    if result.recommendations:
        for rec in result.recommendations:
            st.info(rec)

    if result.settlement_date:
        st.caption(f"{result.buy_market} ↔ {result.sell_market} · Trade {result.trade_date.strftime('%b %d')} → Settle {result.settlement_date.strftime('%b %d')}")

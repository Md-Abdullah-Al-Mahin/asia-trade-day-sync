"""
Timeline Chart Visualization using Plotly.

Creates dual-row Gantt charts showing trading hours, lunch breaks,
cut-off times, and execution time markers for cross-market analysis.
"""

import plotly.graph_objects as go
from datetime import date, time, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.models import get_market_repository, Market
from app.data import get_holiday_manager


def time_to_minutes(t: time) -> int:
    """Convert time to minutes since midnight."""
    return t.hour * 60 + t.minute


def minutes_to_time_str(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM string."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def get_market_times_in_utc(
    market: Market,
    target_date: date
) -> Dict:
    """
    Get market trading hours converted to UTC for a given date.
    
    Returns dictionary with UTC times for open, close, lunch break, and cut-off.
    """
    market_tz = ZoneInfo(market.timezone)
    utc_tz = ZoneInfo("UTC")
    
    # Create datetime objects in market timezone
    open_dt = datetime.combine(target_date, market.trading_hours.open, tzinfo=market_tz)
    close_dt = datetime.combine(target_date, market.trading_hours.close, tzinfo=market_tz)
    
    # Convert to UTC
    open_utc = open_dt.astimezone(utc_tz)
    close_utc = close_dt.astimezone(utc_tz)
    
    result = {
        "open_utc": open_utc,
        "close_utc": close_utc,
        "open_local": market.trading_hours.open,
        "close_local": market.trading_hours.close,
        "timezone": market.timezone,
        "utc_offset": open_utc.strftime("%z"),
    }
    
    # Add lunch break if exists
    if market.trading_hours.lunch_break:
        lunch_start_dt = datetime.combine(
            target_date, 
            market.trading_hours.lunch_break.start, 
            tzinfo=market_tz
        )
        lunch_end_dt = datetime.combine(
            target_date, 
            market.trading_hours.lunch_break.end, 
            tzinfo=market_tz
        )
        result["lunch_start_utc"] = lunch_start_dt.astimezone(utc_tz)
        result["lunch_end_utc"] = lunch_end_dt.astimezone(utc_tz)
        result["has_lunch"] = True
    else:
        result["has_lunch"] = False
    
    # Add depository cut-off if exists
    if market.depository_cut_off:
        cutoff_dt = datetime.combine(target_date, market.depository_cut_off, tzinfo=market_tz)
        result["cutoff_utc"] = cutoff_dt.astimezone(utc_tz)
        result["cutoff_local"] = market.depository_cut_off
    
    return result


def create_trading_hours_gantt(
    market_a_code: str,
    market_b_code: str,
    target_date: date,
    execution_time: Optional[datetime] = None,
    show_local_times: bool = True
) -> go.Figure:
    """
    Create a dual-row Gantt chart showing trading hours for two markets.
    
    Args:
        market_a_code: First market code (e.g., 'JP')
        market_b_code: Second market code (e.g., 'HK')
        target_date: Date to visualize
        execution_time: Optional execution time marker
        show_local_times: Show local times in labels
        
    Returns:
        Plotly Figure object
    """
    repo = get_market_repository()
    holiday_manager = get_holiday_manager()
    
    market_a = repo.get(market_a_code)
    market_b = repo.get(market_b_code)
    
    if not market_a or not market_b:
        raise ValueError(f"Market not found: {market_a_code} or {market_b_code}")
    
    # Check for holidays
    holiday_a = holiday_manager.get_holiday_info(market_a_code, target_date)
    holiday_b = holiday_manager.get_holiday_info(market_b_code, target_date)
    
    # Get market times in UTC
    times_a = get_market_times_in_utc(market_a, target_date)
    times_b = get_market_times_in_utc(market_b, target_date)
    
    # Create figure
    fig = go.Figure()
    
    # Clearly distinct: green = market A, blue = market B (no similar teals)
    colors = {
        "trading_a": "#059669",       # Green — Japan
        "trading_b": "#2563eb",       # Blue — Hong Kong
        "lunch": "#94a3b8",           # Slate gray — lunch break (obviously not trading)
        "closed": "#f1f5f9",         # Very light gray
        "holiday": "#b91c1c",         # Red
        "cutoff": "#ea580c",          # Orange
        "execution": "#7c3aed",       # Violet
        "overlap": "rgba(100, 116, 139, 0.2)",   # Subtle overlap band
    }
    
    # Y positions and bar size (larger bars for clarity)
    y_market_a = 1.0
    y_market_b = 0.0
    bar_height = 0.38
    
    # Time range for x-axis (0:00 to 24:00 UTC)
    x_start = datetime.combine(target_date, time(0, 0), tzinfo=ZoneInfo("UTC"))
    x_end = x_start + timedelta(hours=24)
    
    # Add background rectangles (closed periods)
    fig.add_shape(
        type="rect",
        x0=x_start, x1=x_end,
        y0=y_market_a - bar_height, y1=y_market_a + bar_height,
        fillcolor=colors["closed"],
        line=dict(width=0),
        layer="below"
    )
    fig.add_shape(
        type="rect",
        x0=x_start, x1=x_end,
        y0=y_market_b - bar_height, y1=y_market_b + bar_height,
        fillcolor=colors["closed"],
        line=dict(width=0),
        layer="below"
    )
    
    # Track trading sessions for overlap calculation
    a_sessions = []
    b_sessions = []
    
    # Draw Market A trading hours or holiday
    if holiday_a:
        # Holiday bar
        fig.add_shape(
            type="rect",
            x0=x_start, x1=x_end,
            y0=y_market_a - bar_height, y1=y_market_a + bar_height,
            fillcolor=colors["holiday"],
            opacity=0.6,
            line=dict(width=1, color=colors["holiday"]),
            layer="below"
        )
        # Add legend marker
        fig.add_trace(go.Scatter(
            x=[x_start + timedelta(hours=12)],
            y=[y_market_a],
            mode='markers+text',
            marker=dict(color=colors["holiday"], size=1),
            text=[f"🚫 {holiday_a.name}"],
            textposition="middle center",
            textfont=dict(size=11, color="white"),
            name=f"{market_a.name} Holiday",
            showlegend=True,
            hoverinfo='skip'
        ))
    else:
        # Trading hours
        if times_a["has_lunch"]:
            # Morning session
            fig.add_shape(
                type="rect",
                x0=times_a["open_utc"], x1=times_a["lunch_start_utc"],
                y0=y_market_a - bar_height, y1=y_market_a + bar_height,
                fillcolor=colors["trading_a"],
                line=dict(width=1, color="white"),
                layer="below"
            )
            a_sessions.append((times_a["open_utc"], times_a["lunch_start_utc"]))
            
            # Lunch break (clearly gray, no white border so it reads as "break")
            fig.add_shape(
                type="rect",
                x0=times_a["lunch_start_utc"], x1=times_a["lunch_end_utc"],
                y0=y_market_a - bar_height, y1=y_market_a + bar_height,
                fillcolor=colors["lunch"],
                line=dict(width=0),
                layer="below"
            )
            
            # Afternoon session
            fig.add_shape(
                type="rect",
                x0=times_a["lunch_end_utc"], x1=times_a["close_utc"],
                y0=y_market_a - bar_height, y1=y_market_a + bar_height,
                fillcolor=colors["trading_a"],
                line=dict(width=1, color="white"),
                layer="below"
            )
            a_sessions.append((times_a["lunch_end_utc"], times_a["close_utc"]))
        else:
            # Full trading session
            fig.add_shape(
                type="rect",
                x0=times_a["open_utc"], x1=times_a["close_utc"],
                y0=y_market_a - bar_height, y1=y_market_a + bar_height,
                fillcolor=colors["trading_a"],
                line=dict(width=1, color="white"),
                layer="below"
            )
            a_sessions.append((times_a["open_utc"], times_a["close_utc"]))
        
        # Add legend trace for Market A
        mid_a = times_a["open_utc"] + (times_a["close_utc"] - times_a["open_utc"]) / 2
        fig.add_trace(go.Scatter(
            x=[mid_a],
            y=[y_market_a],
            mode='markers',
            marker=dict(color=colors["trading_a"], size=14, symbol='square'),
            name=f"{market_a.name} Trading",
            showlegend=True,
            hovertemplate=f"{market_a.name}<br>{times_a['open_utc'].strftime('%H:%M')} - {times_a['close_utc'].strftime('%H:%M')} UTC<extra></extra>"
        ))
    
    # Draw Market B trading hours or holiday
    if holiday_b:
        fig.add_shape(
            type="rect",
            x0=x_start, x1=x_end,
            y0=y_market_b - bar_height, y1=y_market_b + bar_height,
            fillcolor=colors["holiday"],
            opacity=0.6,
            line=dict(width=1, color=colors["holiday"]),
            layer="below"
        )
        fig.add_trace(go.Scatter(
            x=[x_start + timedelta(hours=12)],
            y=[y_market_b],
            mode='markers+text',
            marker=dict(color=colors["holiday"], size=1),
            text=[f"🚫 {holiday_b.name}"],
            textposition="middle center",
            textfont=dict(size=11, color="white"),
            name=f"{market_b.name} Holiday",
            showlegend=True,
            hoverinfo='skip'
        ))
    else:
        if times_b["has_lunch"]:
            fig.add_shape(
                type="rect",
                x0=times_b["open_utc"], x1=times_b["lunch_start_utc"],
                y0=y_market_b - bar_height, y1=y_market_b + bar_height,
                fillcolor=colors["trading_b"],
                line=dict(width=1, color="white"),
                layer="below"
            )
            b_sessions.append((times_b["open_utc"], times_b["lunch_start_utc"]))
            
            fig.add_shape(
                type="rect",
                x0=times_b["lunch_start_utc"], x1=times_b["lunch_end_utc"],
                y0=y_market_b - bar_height, y1=y_market_b + bar_height,
                fillcolor=colors["lunch"],
                line=dict(width=0),
                layer="below"
            )
            
            fig.add_shape(
                type="rect",
                x0=times_b["lunch_end_utc"], x1=times_b["close_utc"],
                y0=y_market_b - bar_height, y1=y_market_b + bar_height,
                fillcolor=colors["trading_b"],
                line=dict(width=1, color="white"),
                layer="below"
            )
            b_sessions.append((times_b["lunch_end_utc"], times_b["close_utc"]))
        else:
            fig.add_shape(
                type="rect",
                x0=times_b["open_utc"], x1=times_b["close_utc"],
                y0=y_market_b - bar_height, y1=y_market_b + bar_height,
                fillcolor=colors["trading_b"],
                line=dict(width=1, color="white"),
                layer="below"
            )
            b_sessions.append((times_b["open_utc"], times_b["close_utc"]))
        
        mid_b = times_b["open_utc"] + (times_b["close_utc"] - times_b["open_utc"]) / 2
        fig.add_trace(go.Scatter(
            x=[mid_b],
            y=[y_market_b],
            mode='markers',
            marker=dict(color=colors["trading_b"], size=14, symbol='square'),
            name=f"{market_b.name} Trading",
            showlegend=True,
            hovertemplate=f"{market_b.name}<br>{times_b['open_utc'].strftime('%H:%M')} - {times_b['close_utc'].strftime('%H:%M')} UTC<extra></extra>"
        ))
    
    # Add lunch break to legend if any market has it
    if (not holiday_a and times_a["has_lunch"]) or (not holiday_b and times_b["has_lunch"]):
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='markers',
            marker=dict(color=colors["lunch"], size=14, symbol='square'),
            name="Lunch Break",
            showlegend=True
        ))
    
    # Calculate and draw overlap regions
    overlaps = []
    for a_start, a_end in a_sessions:
        for b_start, b_end in b_sessions:
            overlap_start = max(a_start, b_start)
            overlap_end = min(a_end, b_end)
            if overlap_start < overlap_end:
                overlaps.append((overlap_start, overlap_end))
    
    for o_start, o_end in overlaps:
        # Soft overlap band: solid fill, no dotted border
        fig.add_shape(
            type="rect",
            x0=o_start, x1=o_end,
            y0=y_market_b - bar_height - 0.05,
            y1=y_market_a + bar_height + 0.05,
            fillcolor=colors["overlap"],
            line=dict(width=0),
            layer="below"
        )
    
    # Add cut-off lines
    if not holiday_a and "cutoff_utc" in times_a:
        fig.add_shape(
            type="line",
            x0=times_a["cutoff_utc"], x1=times_a["cutoff_utc"],
            y0=y_market_a - bar_height - 0.05, y1=y_market_a + bar_height + 0.05,
            line=dict(color=colors["cutoff"], width=3, dash="dash")
        )
        fig.add_annotation(
            x=times_a["cutoff_utc"],
            y=y_market_a + bar_height + 0.12,
            text="Cut-off",
            showarrow=False,
            font=dict(size=10, color=colors["cutoff"])
        )
    
    if not holiday_b and "cutoff_utc" in times_b:
        fig.add_shape(
            type="line",
            x0=times_b["cutoff_utc"], x1=times_b["cutoff_utc"],
            y0=y_market_b - bar_height - 0.05, y1=y_market_b + bar_height + 0.05,
            line=dict(color=colors["cutoff"], width=3, dash="dash")
        )
    
    # Add cut-off to legend
    if (not holiday_a and "cutoff_utc" in times_a) or (not holiday_b and "cutoff_utc" in times_b):
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='lines',
            line=dict(color=colors["cutoff"], width=3, dash="dash"),
            name="Depository Cut-off",
            showlegend=True
        ))
    
    # Execution time: if naive, treat as source market (market_a) local time so the line lands in the right place
    if execution_time:
        if execution_time.tzinfo:
            exec_utc = execution_time.astimezone(ZoneInfo("UTC"))
        else:
            # Sidebar "10:00" = 10:00 in source market (e.g. Tokyo) → convert to UTC
            tz_a = ZoneInfo(market_a.timezone)
            exec_local = datetime.combine(target_date, execution_time.time(), tzinfo=tz_a)
            exec_utc = exec_local.astimezone(ZoneInfo("UTC"))
        
        fig.add_shape(
            type="line",
            x0=exec_utc, x1=exec_utc,
            y0=-0.5, y1=1.5,
            line=dict(color=colors["execution"], width=2)
        )
        # Label with local time so it's clear (e.g. "Execution 10:00 Tokyo")
        exec_local_str = exec_utc.astimezone(ZoneInfo(market_a.timezone)).strftime("%H:%M")
        tz_short = market_a.timezone.split("/")[-1].replace("_", " ")
        fig.add_trace(go.Scatter(
            x=[exec_utc],
            y=[1.6],
            mode="markers+text",
            marker=dict(color=colors["execution"], size=12, symbol="diamond"),
            text=[f"Execution {exec_local_str} {tz_short}"],
            textposition="top center",
            textfont=dict(size=10, color=colors["execution"]),
            name="Execution",
            showlegend=True,
            hovertemplate=f"Execution {exec_local_str} {tz_short} = {exec_utc.strftime('%H:%M')} UTC<extra></extra>"
        ))
    
    # Show both local and UTC so the chart is self-explanatory
    local_a = f"{times_a['open_local'].strftime('%H:%M')}–{times_a['close_local'].strftime('%H:%M')}"
    local_b = f"{times_b['open_local'].strftime('%H:%M')}–{times_b['close_local'].strftime('%H:%M')}"
    utc_a = f"{times_a['open_utc'].strftime('%H:%M')}–{times_a['close_utc'].strftime('%H:%M')}"
    utc_b = f"{times_b['open_utc'].strftime('%H:%M')}–{times_b['close_utc'].strftime('%H:%M')}"
    tickfont = dict(size=12, color="#1f2937")
    titlefont = dict(size=16, color="#111827")

    fig.update_layout(
        title=dict(
            text=f"When each market is open · {target_date.strftime('%d %b %Y')}",
            x=0.5,
            xanchor="center",
            font=titlefont,
        ),
        xaxis=dict(
            title=dict(text="Time (UTC)", font=dict(size=12, color="#374151")),
            type="date",
            range=[x_start, x_end],
            tickformat="%H:%M",
            dtick=7200000,
            showgrid=True,
            gridcolor="rgba(0,0,0,0.06)",
            zeroline=False,
            tickfont=tickfont,
        ),
        yaxis=dict(
            tickvals=[y_market_b, y_market_a],
            ticktext=[
                f"{market_b.name} ({market_b.code})  {local_b} local  →  {utc_b} UTC",
                f"{market_a.name} ({market_a.code})  {local_a} local  →  {utc_a} UTC",
            ],
            tickfont=tickfont,
            showgrid=False,
            range=[-0.6, 1.8],
            zeroline=False,
        ),
        height=420,
        margin=dict(l=220, r=48, t=56, b=52),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#374151"),
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="rgba(0,0,0,0.08)",
            borderwidth=1,
        ),
        hovermode="x unified",
        plot_bgcolor="#f8fafc",
        paper_bgcolor="rgba(255,255,255,0.98)",
    )
    
    return fig


def create_market_timeline(
    market_a_code: str,
    market_b_code: str,
    target_date: date,
    execution_time: Optional[datetime] = None
) -> go.Figure:
    """
    Create a comprehensive market timeline visualization.
    
    This is the main entry point for the timeline chart.
    Wraps create_trading_hours_gantt with additional features.
    
    Args:
        market_a_code: Source market code
        market_b_code: Target market code  
        target_date: Date to visualize
        execution_time: Optional execution time marker
        
    Returns:
        Plotly Figure object
    """
    return create_trading_hours_gantt(
        market_a_code=market_a_code,
        market_b_code=market_b_code,
        target_date=target_date,
        execution_time=execution_time,
        show_local_times=True
    )

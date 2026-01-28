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
    
    # Define colors
    colors = {
        "trading_a": "#28a745",      # Green for market A trading hours
        "trading_b": "#17a2b8",      # Teal for market B trading hours
        "lunch": "#FFD700",          # Gold for lunch break
        "closed": "#f0f0f0",         # Light gray for closed
        "holiday": "#dc3545",        # Red for holiday
        "cutoff": "#fd7e14",         # Orange for cut-off
        "execution": "#6f42c1",      # Purple for execution time
        "overlap": "rgba(255, 193, 7, 0.3)",  # Semi-transparent yellow for overlap
    }
    
    # Y positions for the two markets
    y_market_a = 1.0
    y_market_b = 0.0
    bar_height = 0.35
    
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
            
            # Lunch break
            fig.add_shape(
                type="rect",
                x0=times_a["lunch_start_utc"], x1=times_a["lunch_end_utc"],
                y0=y_market_a - bar_height, y1=y_market_a + bar_height,
                fillcolor=colors["lunch"],
                opacity=0.7,
                line=dict(width=1, color="white"),
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
            marker=dict(color=colors["trading_a"], size=12, symbol='square'),
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
                opacity=0.7,
                line=dict(width=1, color="white"),
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
            marker=dict(color=colors["trading_b"], size=12, symbol='square'),
            name=f"{market_b.name} Trading",
            showlegend=True,
            hovertemplate=f"{market_b.name}<br>{times_b['open_utc'].strftime('%H:%M')} - {times_b['close_utc'].strftime('%H:%M')} UTC<extra></extra>"
        ))
    
    # Add lunch break to legend if any market has it
    if (not holiday_a and times_a["has_lunch"]) or (not holiday_b and times_b["has_lunch"]):
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='markers',
            marker=dict(color=colors["lunch"], size=12, symbol='square'),
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
    
    for i, (o_start, o_end) in enumerate(overlaps):
        duration = int((o_end - o_start).total_seconds() / 60)
        # Draw overlap highlight spanning both markets
        fig.add_shape(
            type="rect",
            x0=o_start, x1=o_end,
            y0=y_market_b - bar_height - 0.05,
            y1=y_market_a + bar_height + 0.05,
            fillcolor=colors["overlap"],
            line=dict(width=2, color="#ffc107", dash="dot"),
            layer="below"
        )
        # Add annotation for first overlap only
        if i == 0:
            fig.add_annotation(
                x=o_start + (o_end - o_start) / 2,
                y=y_market_a + bar_height + 0.15,
                text=f"Overlap: {duration}m",
                showarrow=False,
                font=dict(size=10, color="#856404"),
                bgcolor="rgba(255, 243, 205, 0.9)",
                borderpad=3
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
            text=f"Cut-off",
            showarrow=False,
            font=dict(size=9, color=colors["cutoff"])
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
    
    # Add execution time marker if provided
    if execution_time:
        exec_utc = execution_time.astimezone(ZoneInfo("UTC")) if execution_time.tzinfo else \
                   datetime.combine(target_date, execution_time.time(), tzinfo=ZoneInfo("UTC"))
        
        fig.add_shape(
            type="line",
            x0=exec_utc, x1=exec_utc,
            y0=-0.5, y1=1.5,
            line=dict(color=colors["execution"], width=3)
        )
        fig.add_trace(go.Scatter(
            x=[exec_utc],
            y=[1.6],
            mode='markers+text',
            marker=dict(color=colors["execution"], size=12, symbol="diamond"),
            text=["⏱️ Execution"],
            textposition="top center",
            textfont=dict(size=10, color=colors["execution"]),
            name="Execution Time",
            showlegend=True,
            hovertemplate=f"Execution Time<br>{exec_utc.strftime('%H:%M')} UTC<extra></extra>"
        ))
    
    # Build y-axis labels
    local_hours_a = f"{times_a['open_local'].strftime('%H:%M')}-{times_a['close_local'].strftime('%H:%M')}"
    local_hours_b = f"{times_b['open_local'].strftime('%H:%M')}-{times_b['close_local'].strftime('%H:%M')}"
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f"<b>Trading Hours Timeline</b><br><sup>{target_date.strftime('%A, %B %d, %Y')} (Times in UTC)</sup>",
            x=0.5,
            xanchor='center',
            font=dict(size=16)
        ),
        xaxis=dict(
            title="Time (UTC)",
            type='date',
            range=[x_start, x_end],
            tickformat="%H:%M",
            dtick=7200000,  # 2-hour intervals in milliseconds
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            zeroline=False,
        ),
        yaxis=dict(
            tickvals=[y_market_b, y_market_a],
            ticktext=[
                f"<b>{market_b.name}</b> ({market_b.code})<br><span style='font-size:10px'>{local_hours_b} local</span>",
                f"<b>{market_a.name}</b> ({market_a.code})<br><span style='font-size:10px'>{local_hours_a} local</span>"
            ],
            showgrid=False,
            range=[-0.6, 1.8],
            zeroline=False,
        ),
        height=320,
        margin=dict(l=120, r=40, t=80, b=60),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=10),
            bgcolor="rgba(255,255,255,0.8)"
        ),
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
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

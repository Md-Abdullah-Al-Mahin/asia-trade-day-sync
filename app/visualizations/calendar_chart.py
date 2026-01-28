"""
Calendar Month View Visualization using Plotly.

Creates color-coded calendar showing trading status for two markets.
"""

import plotly.graph_objects as go
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import calendar

from app.models import get_market_repository
from app.data import get_holiday_manager


# Muted palette (readable on light and dark)
COLORS = {
    "common_open": "#22c55e",       # Muted green
    "holiday_a_only": "#f97316",    # Muted orange
    "holiday_b_only": "#14b8a6",    # Muted teal
    "common_holiday": "#b91c1c",    # Muted red
    "weekend": "#e4e4e7",           # Neutral gray
    "selected": "#7c3aed",          # Muted violet
    "today": "#eab308",             # Muted amber
}


def get_day_status(
    market_a_code: str,
    market_b_code: str,
    check_date: date
) -> Tuple[str, str, str]:
    """
    Get the trading status for a day.
    
    Returns:
        Tuple of (status_code, color, tooltip)
    """
    holiday_manager = get_holiday_manager()
    
    # Check if weekend
    if check_date.weekday() >= 5:
        return ("weekend", COLORS["weekend"], "Weekend")
    
    # Check holidays for both markets
    holiday_a = holiday_manager.get_holiday_info(market_a_code, check_date)
    holiday_b = holiday_manager.get_holiday_info(market_b_code, check_date)
    
    is_holiday_a = holiday_a is not None and holiday_a.source.value != "weekend"
    is_holiday_b = holiday_b is not None and holiday_b.source.value != "weekend"
    
    if is_holiday_a and is_holiday_b:
        # Both markets have holiday
        names = []
        if holiday_a:
            names.append(f"{market_a_code}: {holiday_a.name}")
        if holiday_b:
            names.append(f"{market_b_code}: {holiday_b.name}")
        return ("common_holiday", COLORS["common_holiday"], "\\n".join(names))
    elif is_holiday_a:
        return ("holiday_a", COLORS["holiday_a_only"], f"{market_a_code}: {holiday_a.name}")
    elif is_holiday_b:
        return ("holiday_b", COLORS["holiday_b_only"], f"{market_b_code}: {holiday_b.name}")
    else:
        return ("common_open", COLORS["common_open"], "Both markets open")


def create_calendar_month_view(
    market_a_code: str,
    market_b_code: str,
    year: int,
    month: int,
    selected_date: Optional[date] = None
) -> go.Figure:
    """
    Create a color-coded calendar month view.
    
    Args:
        market_a_code: First market code (e.g., 'JP')
        market_b_code: Second market code (e.g., 'HK')
        year: Year to display
        month: Month to display (1-12)
        selected_date: Optional selected/highlighted date
        
    Returns:
        Plotly Figure object
    """
    repo = get_market_repository()
    market_a = repo.get(market_a_code)
    market_b = repo.get(market_b_code)
    
    if not market_a or not market_b:
        raise ValueError(f"Market not found: {market_a_code} or {market_b_code}")
    
    # Get calendar data
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdayscalendar(year, month)
    
    # Day names for header
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # Create figure
    fig = go.Figure()
    
    # Cell dimensions (fixed grid; size comes from figure height)
    cell_width = 1
    cell_height = 1
    padding = 0.06
    
    # Calculate grid positions
    n_weeks = len(month_days)
    
    # Day name headers
    header_font = dict(size=12, color="#1f2937")
    for col, day_name in enumerate(day_names):
        x = col * cell_width + cell_width / 2
        y = n_weeks * cell_height + 0.5
        fig.add_annotation(
            x=x, y=y,
            text=day_name,
            showarrow=False,
            font=header_font,
            xanchor="center",
            yanchor="middle"
        )
    
    # Add calendar cells
    today = date.today()
    
    for week_idx, week in enumerate(month_days):
        row = n_weeks - 1 - week_idx  # Reverse row order (top to bottom)
        
        for col, day in enumerate(week):
            if day == 0:
                continue  # Empty cell
            
            current_date = date(year, month, day)
            x = col * cell_width
            y = row * cell_height
            
            # Get day status
            status, color, tooltip = get_day_status(market_a_code, market_b_code, current_date)
            
            # Check if this is the selected date
            is_selected = selected_date and current_date == selected_date
            is_today = current_date == today
            
            # Cell color and border (softer selected/today)
            if is_selected:
                cell_color = COLORS["selected"]
                border_color = "#5b21b6"
                border_width = 2
                text_color = "white"
            elif is_today:
                cell_color = color
                border_color = COLORS["today"]
                border_width = 2
                text_color = "white" if status in ["common_holiday", "holiday_a", "holiday_b"] else "#18181b"
            else:
                cell_color = color
                border_color = "rgba(255,255,255,0.6)"
                border_width = 1
                text_color = "white" if status in ["common_holiday", "holiday_a", "holiday_b"] else "#18181b"
            
            # Add cell rectangle
            fig.add_shape(
                type="rect",
                x0=x + padding,
                x1=x + cell_width - padding,
                y0=y + padding,
                y1=y + cell_height - padding,
                fillcolor=cell_color,
                line=dict(color=border_color, width=border_width),
                layer="below"
            )
            
            # Day number (larger for readability)
            fig.add_annotation(
                x=x + cell_width / 2,
                y=y + cell_height / 2,
                text=str(day),
                showarrow=False,
                font=dict(
                    size=15 if is_selected or is_today else 14,
                    color=text_color,
                    family="Arial"
                ),
                xanchor="center",
                yanchor="middle"
            )
            
            # Add invisible scatter point for hover
            hover_text = f"<b>{current_date.strftime('%B %d, %Y')}</b><br>{tooltip}"
            if is_selected:
                hover_text += "<br><b>Selected Date</b>"
            if is_today:
                hover_text += "<br><b>Today</b>"
            
            fig.add_trace(go.Scatter(
                x=[x + cell_width / 2],
                y=[y + cell_height / 2],
                mode='markers',
                marker=dict(size=30, color='rgba(0,0,0,0)'),
                hovertemplate=hover_text + "<extra></extra>",
                showlegend=False
            ))
    
    # Legend with clear labels
    legend_items = [
        ("Both open", COLORS["common_open"]),
        (f"{market_a.name} closed", COLORS["holiday_a_only"]),
        (f"{market_b.name} closed", COLORS["holiday_b_only"]),
        ("Both closed", COLORS["common_holiday"]),
        ("Weekend", COLORS["weekend"]),
    ]
    if selected_date:
        legend_items.append(("Selected", COLORS["selected"]))
    for name, color in legend_items:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(size=12, color=color, symbol="square"),
            name=name,
            showlegend=True,
        ))

    month_name = calendar.month_name[month]
    fig.update_layout(
        title=dict(
            text=f"{month_name} {year} · {market_a.code} vs {market_b.code}",
            x=0.5,
            xanchor="center",
            font=dict(size=16, color="#111827")
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-0.2, 7.2],
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-0.5, n_weeks + 1],
            scaleanchor="x",
            scaleratio=1,
            fixedrange=True,
        ),
        height=460,
        margin=dict(l=24, r=24, t=56, b=56),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.1,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#374151"),
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="rgba(0,0,0,0.08)",
            borderwidth=1,
        ),
        plot_bgcolor="#f8fafc",
        paper_bgcolor="rgba(255,255,255,0.98)",
        hovermode="closest",
    )
    
    return fig


def create_multi_month_view(
    market_a_code: str,
    market_b_code: str,
    start_date: date,
    months: int = 3,
    selected_date: Optional[date] = None
) -> List[go.Figure]:
    """
    Create multiple month calendar views.
    
    Args:
        market_a_code: First market code
        market_b_code: Second market code
        start_date: Starting date (will use this month)
        months: Number of months to generate
        selected_date: Optional selected date
        
    Returns:
        List of Plotly Figure objects
    """
    figures = []
    current = date(start_date.year, start_date.month, 1)
    
    for _ in range(months):
        fig = create_calendar_month_view(
            market_a_code=market_a_code,
            market_b_code=market_b_code,
            year=current.year,
            month=current.month,
            selected_date=selected_date
        )
        figures.append(fig)
        
        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    
    return figures


def get_month_summary(
    market_a_code: str,
    market_b_code: str,
    year: int,
    month: int
) -> Dict:
    """
    Get summary statistics for a month.
    
    Returns:
        Dictionary with counts of different day types
    """
    cal = calendar.Calendar()
    
    counts = {
        "total_days": 0,
        "weekdays": 0,
        "weekends": 0,
        "common_open": 0,
        "holiday_a_only": 0,
        "holiday_b_only": 0,
        "common_holiday": 0,
    }
    
    for day in cal.itermonthdays(year, month):
        if day == 0:
            continue
        
        counts["total_days"] += 1
        current_date = date(year, month, day)
        
        if current_date.weekday() >= 5:
            counts["weekends"] += 1
        else:
            counts["weekdays"] += 1
            status, _, _ = get_day_status(market_a_code, market_b_code, current_date)
            
            if status == "common_open":
                counts["common_open"] += 1
            elif status == "holiday_a":
                counts["holiday_a_only"] += 1
            elif status == "holiday_b":
                counts["holiday_b_only"] += 1
            elif status == "common_holiday":
                counts["common_holiday"] += 1
    
    return counts

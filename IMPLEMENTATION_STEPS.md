# Cross-Market T+1 Settlement Dashboard - Python Implementation Steps

## Project Overview
Build a Python-based dashboard to determine settlement viability for cross-market trades across Asian markets, considering trading hours, holidays, and cut-off times.

**Note:** This is a personal project focused on functionality over production infrastructure.

---

## Phase 1: Project Setup & Foundation

### Step 1.1: Initialize Project Structure
```
asia-trade-day-sync/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Streamlit dashboard entry
│   ├── config.py               # Configuration settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── market.py           # Market data models
│   │   ├── holiday.py          # Holiday calendar models
│   │   └── settlement.py       # Settlement calculation models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── calendar_service.py # Holiday/calendar logic
│   │   ├── settlement_engine.py # Core settlement logic
│   │   └── timezone_service.py # Timezone conversions
│   └── data/
│       └── markets.json        # Market configuration
├── tests/
│   ├── __init__.py
│   ├── test_settlement_engine.py
│   └── test_calendar_service.py
├── requirements.txt
└── README.md
```

### Step 1.2: Set Up Virtual Environment & Dependencies
Create `requirements.txt`:
```
# Core
pydantic>=2.5.0

# Date/Time & Calendar
python-dateutil>=2.8.2
pytz>=2024.1
holidays>=0.40
exchange-calendars>=4.5.0

# Dashboard
streamlit>=1.30.0
plotly>=5.18.0

# Testing
pytest>=7.4.0
```

---

## Phase 2: Data Models

### Step 2.1: Define Market Data Model
Create dataclasses/Pydantic models for:
- Market code (e.g., JP, HK, SG, IN, AU)
- Market name
- Timezone (IANA format)
- Standard trading hours (open/close in local time)
- Lunch break times (if applicable)
- Settlement cycle (T+1, T+2)
- Depository cut-off times

### Step 2.2: Define Holiday Calendar Model
Structure for holiday data:
- Market code
- Date
- Holiday name
- Holiday type (full day, half day, special closure)

### Step 2.3: Define Settlement Result Model
Pydantic models for:
- `SettlementCheckRequest`: trade_date, buy_market, sell_market, execution_time, instrument_type
- `SettlementResult`: status (LIKELY/AT_RISK/UNLIKELY), message, settlement_date, deadlines
- `MarketStatus`: market_code, is_open, current_session, next_open, next_close

---

## Phase 3: Core Services Implementation

### Step 3.1: Timezone Service
Implement `timezone_service.py`:
```python
# Key functions:
- convert_to_utc(local_time, timezone)
- convert_from_utc(utc_time, timezone)
- get_market_local_time(market_code)
- calculate_overlap_window(market_a, market_b, date)
```

### Step 3.2: Calendar Service
Implement `calendar_service.py`:
```python
# Key functions using exchange_calendars + holidays libraries:
- is_trading_day(market_code, date) -> bool
- is_settlement_day(market_code, date) -> bool
- get_holidays_for_range(market_code, start_date, end_date)
- get_next_business_day(market_code, date)
- get_common_business_days(market_a, market_b, start_date, end_date)
```

### Step 3.3: Settlement Engine (Core Logic)
Implement `settlement_engine.py`:
```python
# Main settlement calculation logic:

class SettlementEngine:
    def check_settlement(
        self,
        trade_date: date,
        buy_market: str,
        sell_market: str,
        execution_time: datetime,
        instrument_type: str
    ) -> SettlementResult:
        """
        Core algorithm:
        1. Validate trade date is common business day
        2. Check execution time against both markets' hours
        3. Verify execution time vs cut-off times
        4. Calculate T+1 settlement date for both markets
        5. Find common settlement date
        6. Return status with detailed message
        """
        pass
    
    def _validate_trade_date(self, date, market_a, market_b) -> ValidationResult
    def _check_cut_off_times(self, execution_time, market) -> bool
    def _calculate_settlement_date(self, trade_date, market) -> date
    def _find_common_settlement_date(self, market_a, market_b, trade_date) -> date
    def _determine_status(self, checks) -> SettlementStatus
```

### Step 3.4: Market Status Service
Implement market status helpers:
```python
# Key functions:
- get_current_market_status(market_code)
- get_trading_hours_for_date(market_code, date)
- is_market_open_now(market_code)
- get_time_until_close(market_code)
- get_time_until_cut_off(market_code)
```

---

## Phase 4: Data Integration

### Step 4.1: Seed Initial Market Data
Create JSON configuration for Asian markets:
- Japan (TSE) - JP / XTKS
- Hong Kong (HKEX) - HK / XHKG
- Singapore (SGX) - SG / XSES
- India (NSE/BSE) - IN / XNSE
- Australia (ASX) - AU / XASX
- South Korea (KRX) - KR / XKRX
- Taiwan (TWSE) - TW / XTAI
- China (SSE/SZSE) - CN / XSHG

### Step 4.2: Holiday Data Sources
Use these free sources:
1. **`exchange_calendars`** - Trading hours, exchange holidays, lunch breaks
2. **`holidays` library** - Public/bank holidays
3. **Manual overrides** - For special closures (typhoons, etc.)

### Step 4.3: Handle Special Cases
Document and handle:
- Typhoon closures (HK, TW) - manual override
- Lunar New Year variations
- Half-day trading sessions
- Post-holiday settlement adjustments

---

## Phase 5: Streamlit Dashboard

### Step 5.1: Implement Dashboard Layout
```python
# main.py - Streamlit dashboard

import streamlit as st
import plotly.graph_objects as go

# Layout:
# 1. Sidebar - Control Panel
#    - Date picker for Trade Date
#    - Market pair dropdowns
#    - Instrument type selector
#    - "Check Settlement" button

# 2. Main Area - Results
#    - Settlement Status Widget (big colored box)
#    - Dual Timeline Gantt Chart
#    - Calendar Month View
```

### Step 5.2: Implement Settlement Status Widget
Large, color-coded result card:
- 🟢 **SETTLEMENT LIKELY** - Green box
- 🟡 **SETTLEMENT AT RISK** - Yellow box  
- 🔴 **SETTLEMENT UNLIKELY** - Red box

Include:
- Clear status message
- Settlement date
- Key deadlines
- Actionable recommendations

### Step 5.3: Implement Gantt Chart Visualization
```python
# Using Plotly for timeline visualization
def create_market_timeline(market_a, market_b, date):
    """
    Create dual-row Gantt chart showing:
    - Trading hours (green bars)
    - Non-trading hours (gray)
    - Holidays (red bar across day)
    - Lunch breaks (hatched/lighter)
    - Cut-off times (amber vertical line)
    - Execution time marker (draggable or input)
    """
    pass
```

### Step 5.4: Implement Calendar Month View
Color-coded calendar showing:
- Common business days (green)
- Holidays in Market A only (orange)
- Holidays in Market B only (blue)
- Common holidays (red)
- Selected trade date (highlighted)

### Step 5.5: Add Interactive Features
- Slider or input for execution time
- Hover tooltips with details
- Click on calendar day to select trade date
- Current time indicators

---

## Phase 6: Testing

### Step 6.1: Unit Tests
```python
# test_settlement_engine.py
- test_common_business_day_validation
- test_holiday_detection
- test_cut_off_time_check
- test_settlement_date_calculation
- test_cross_timezone_scenarios
```

### Step 6.2: Scenario Tests
Test specific real-world scenarios:
- Trade on Lunar New Year Eve
- Trade during overlapping lunch breaks
- Trade at end of week before long holiday
- Cross-timezone edge cases (e.g., Sydney vs Tokyo)

---

## Phase 7: Future Enhancements (Optional)

### Step 7.1: What-If Scenarios
- Simulate trades across 3+ markets
- "Find best execution window" feature

### Step 7.2: Historical Analysis
- "How many risky days in Q4?"
- Calendar heatmap of settlement risk

### Step 7.3: Alerts
- Simple email/desktop notification for upcoming restricted periods

---

## Implementation Priority Order

| Priority | Phase | Complexity |
|----------|-------|------------|
| 1 | Phase 1: Project Setup | Low |
| 2 | Phase 2: Data Models | Low |
| 3 | Phase 4: Data Integration | Medium |
| 4 | Phase 3: Core Services | High |
| 5 | Phase 5: Streamlit Dashboard | Medium |
| 6 | Phase 6: Testing | Medium |
| 7 | Phase 7: Enhancements | Optional |

---

## Quick Start Commands

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dashboard
streamlit run app/main.py

# 4. Run tests
pytest tests/ -v
```

---

## Key Technical Decisions

1. **Streamlit** - Simple Python-only dashboard, no separate frontend needed
2. **exchange_calendars** - Accurate trading schedules maintained by quant community
3. **Plotly** - Interactive charts that integrate well with Streamlit
4. **Pydantic** - Clean data validation and type hints
5. **JSON config** - Simple market data storage, no database needed

---

## Success Criteria

- [ ] Can check settlement viability for any two Asian markets
- [ ] Handles holidays and special closures correctly
- [ ] Provides clear, actionable status messages
- [ ] Visual timeline shows trading hours and overlap windows
- [ ] Calendar view highlights common business days
- [ ] Core settlement logic has test coverage

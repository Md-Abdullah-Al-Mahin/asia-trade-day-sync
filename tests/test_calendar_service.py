"""
Tests for the Calendar Service.
"""

import pytest
from datetime import date

from app.services.calendar_service import CalendarService


class TestCalendarService:
    """Test cases for CalendarService."""
    
    @pytest.fixture
    def service(self):
        """Create a CalendarService instance."""
        return CalendarService()
    
    # TODO: Implement tests in Phase 6
    
    def test_is_trading_day_weekday(self, service):
        """Test that normal weekday is a trading day."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_is_trading_day_weekend(self, service):
        """Test that weekend is not a trading day."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_is_trading_day_holiday(self, service):
        """Test that holiday is not a trading day."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_get_next_business_day_normal(self, service):
        """Test next business day from a normal weekday."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_get_next_business_day_friday(self, service):
        """Test next business day from Friday is Monday."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_get_next_business_day_before_holiday(self, service):
        """Test next business day skips holiday."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_get_common_business_days(self, service):
        """Test finding common business days between two markets."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_get_holidays_for_range(self, service):
        """Test getting holidays within a date range."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")
    
    def test_holiday_info_retrieval(self, service):
        """Test retrieving holiday details for a specific date."""
        # TODO: Implement
        pytest.skip("To be implemented in Phase 6")

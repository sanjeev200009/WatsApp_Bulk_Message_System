import time
import pytest
from unittest.mock import MagicMock, patch
from src.rate_limiter import RateLimiter
from src.config import settings

class TestRateLimiter:
    @pytest.fixture
    def limiter(self):
        # Reset any global state or create fresh instance
        settings.DAILY_LIMIT = 5
        settings.SEND_DELAY_SECONDS = 0.1
        return RateLimiter() # New instance per test

    def test_daily_limit_enforcement(self, limiter):
        limiter.daily_limit = 2
        limiter.sent_count = 0
        
        assert limiter.can_send("u1") is True
        limiter.record_success("u1")
        
        assert limiter.can_send("u2") is True
        limiter.record_success("u2")
        
        assert limiter.can_send("u3") is False # Limit reached

    def test_deduplication_in_run(self, limiter):
        limiter.record_success("u1")
        assert limiter.can_send("u1") is False # Already sent
        assert limiter.can_send("u2") is True

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_slot(self, mock_time, mock_sleep, limiter):
        # Initial state
        mock_time.return_value = 100.0
        limiter.last_send_time = 99.95 # 0.05s ago
        settings.SEND_DELAY_SECONDS = 0.1
        
        limiter.wait_for_slot()
        
        # Should sleep for difference (0.1 - 0.05 = 0.05)
        mock_sleep.assert_called_with(pytest.approx(0.05))

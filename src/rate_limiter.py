import time
from datetime import datetime, timedelta
from typing import Set
from .config import settings
from .logger import logger, result_logger

class RateLimiter:
    """
    Manages sending rates, daily limits, and idempotency.
    """
    def __init__(self):
        self.daily_limit = settings.DAILY_LIMIT
        self.sent_count = 0
        self.sent_users: Set[str] = set()
        self.last_send_time = 0
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        
    def can_send(self, user_id: str) -> bool:
        """
        Check if we can send a message to this user.
        Checks: daily limit, duplicate send in this run.
        """
        if self.sent_count >= self.daily_limit:
            logger.warning("Daily limit reached. stopping sends.")
            return False
            
        if str(user_id) in self.sent_users:
            logger.info(f"Skipping user {user_id}: Already sent in this run.")
            return False
            
        return True
        
    def wait_for_slot(self):
        """
        Enforce minimum delay between sends.
        """
        now = time.time()
        elapsed = now - self.last_send_time
        
        if elapsed < settings.SEND_DELAY_SECONDS:
            wait_time = settings.SEND_DELAY_SECONDS - elapsed
            time.sleep(wait_time)
            
    def record_success(self, user_id: str):
        """
        Record a successful send.
        """
        self.sent_count += 1
        self.sent_users.add(str(user_id))
        self.last_send_time = time.time()
        self.consecutive_failures = 0  # Reset failure counter on success
        
    def record_failure(self):
        """
        Record a failure (logs only, but updates timing to prevent hammering).
        """
        self.last_send_time = time.time()
        self.consecutive_failures += 1
        
    def should_stop_due_to_errors(self) -> bool:
        """
        Check if we should stop sending due to consecutive failures.
        """
        return self.consecutive_failures >= self.max_consecutive_failures

# Global rate limiter instance
limiter = RateLimiter()

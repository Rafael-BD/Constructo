import time
from datetime import datetime, timedelta
from typing import Dict

class RateLimiter:
    def __init__(self, requests_per_minute: int, delay_between_requests: float):
        self.requests_per_minute = requests_per_minute
        self.delay_between_requests = delay_between_requests
        self.requests_timeline: list[float] = []
        self.last_request_time = 0.0
        
    def wait_if_needed(self):
        """Wait if we're exceeding the rate limit"""
        current_time = time.time()
        
        # Remove requests older than 1 minute
        minute_ago = current_time - 60
        self.requests_timeline = [t for t in self.requests_timeline if t > minute_ago]
        
        # Check if we need to wait for rate limit
        if len(self.requests_timeline) >= self.requests_per_minute:
            sleep_time = self.requests_timeline[0] - minute_ago
            if sleep_time > 0:
                time.sleep(sleep_time)
                
        # Apply delay between requests if needed
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.delay_between_requests:
            time.sleep(self.delay_between_requests - time_since_last_request)
        
        # Record this request
        self.last_request_time = time.time()
        self.requests_timeline.append(self.last_request_time)

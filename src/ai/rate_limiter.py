import time
import asyncio
from datetime import datetime, timedelta
from collections import deque

class RateLimiter:
    def __init__(self, requests_per_minute: int = 10, delay_between_requests: float = 5.0):
        self.requests_per_minute = requests_per_minute
        self.delay_between_requests = delay_between_requests
        self.request_times = deque(maxlen=requests_per_minute)
        self.last_request_time = None
        self.request_count = 0
        
    async def wait_if_needed_async(self):
        """Rate limiting with exact timing"""
        current_time = datetime.now()
        
        if self.last_request_time:
            while True:
                current_time = datetime.now()
                time_since_last = (current_time - self.last_request_time).total_seconds()
                
                if time_since_last < self.delay_between_requests:
                    delay = self.delay_between_requests - time_since_last
                    await asyncio.sleep(delay)
                else:
                    break
        
        current_time = datetime.now()
        
        # Remove old timestamps
        while self.request_times and (current_time - self.request_times[0]) > timedelta(minutes=1):
            self.request_times.popleft()
        
        # Check rate limit per minute
        while len(self.request_times) >= self.requests_per_minute:
            current_time = datetime.now()
            oldest_request = self.request_times[0]
            wait_time = (oldest_request + timedelta(minutes=1) - current_time).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            else:
                break
        
        current_time = datetime.now()
        self.request_times.append(current_time)
        self.last_request_time = current_time

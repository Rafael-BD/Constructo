import time
import asyncio
from datetime import datetime, timedelta
from collections import deque

class RateLimiter:
    def __init__(self, requests_per_minute: int = 10, delay_between_requests: float = 5.0):
        print(f"Initializing RateLimiter with: {requests_per_minute} req/min, {delay_between_requests}s delay")
        self.requests_per_minute = requests_per_minute
        self.delay_between_requests = delay_between_requests
        self.request_times = deque(maxlen=requests_per_minute)
        self.last_request_time = None
        self.request_count = 0
        
    async def wait_if_needed_async(self):
        """Rate limiting with exact timing"""
        current_time = datetime.now()
        
        # Primeiro, garantir o delay mínimo
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
        
        # Remover timestamps antigos
        while self.request_times and (current_time - self.request_times[0]) > timedelta(minutes=1):
            self.request_times.popleft()
        
        # Verificar limite por minuto
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
    
    def wait_if_needed(self):
        """Sync version for backward compatibility"""
        current_time = datetime.now()
        self.request_count += 1
        
        print(f"\n[API Request #{self.request_count}] at {current_time.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"  - Config: {self.requests_per_minute} req/min, {self.delay_between_requests}s delay")
        print(f"  - Requests in last minute: {len(self.request_times)}")
        
        if self.last_request_time:
            time_since_last = (current_time - self.last_request_time).total_seconds()
            print(f"  - Time since last request: {time_since_last:.3f}s")
            
            # Garantir delay mínimo entre requisições
            if time_since_last < self.delay_between_requests:
                delay = self.delay_between_requests - time_since_last
                print(f"  - Enforcing minimum delay: {delay:.3f}s")
                time.sleep(delay)
                current_time = datetime.now()
        
        # Remover timestamps antigos
        while self.request_times and (current_time - self.request_times[0]) > timedelta(minutes=1):
            self.request_times.popleft()
            
        # Verificar limite por minuto
        if len(self.request_times) >= self.requests_per_minute:
            oldest_request = self.request_times[0]
            wait_time = (oldest_request + timedelta(minutes=1) - current_time).total_seconds()
            if wait_time > 0:
                print(f"  - Rate limit reached ({len(self.request_times)}/{self.requests_per_minute}). Waiting {wait_time:.2f}s")
                time.sleep(wait_time)
                current_time = datetime.now()
        
        # Registrar nova requisição
        self.request_times.append(current_time)
        self.last_request_time = current_time
        print(f"  - Request allowed at {current_time.strftime('%H:%M:%S.%f')[:-3]}")

import time
from typing import Dict, List
from fastapi import HTTPException

class SlidingWindowRateLimiter:
    """
    In-memory sliding window rate limiter per principal.
    Guarantees demo endpoints cannot be abused or exhausted by runaway scripts.
    """

    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, principal_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old timestamps
        timestamps = self._history.get(principal_id, [])
        valid_timestamps = [t for t in timestamps if t > window_start]

        if len(valid_timestamps) >= self.max_requests:
            self._history[principal_id] = valid_timestamps
            return False

        valid_timestamps.append(now)
        self._history[principal_id] = valid_timestamps
        return True

    def check(self, principal_id: str):
        if not self.is_allowed(principal_id):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: Max {self.max_requests} requests per {self.window_seconds}s allowed per principal."
            )

# Global default limiter (20 requests / 60s per principal)
default_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60)

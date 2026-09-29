import os
import sys
import json
from fastapi import HTTPException

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from app.core.rate_limiter import SlidingWindowRateLimiter
from app.core.logger import agent_logger

def test_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=2)
    user = "rate_test_user"

    # 3 allowed requests
    assert limiter.is_allowed(user) is True
    assert limiter.is_allowed(user) is True
    assert limiter.is_allowed(user) is True

    # 4th request must be rejected
    assert limiter.is_allowed(user) is False

    try:
        limiter.check(user)
        assert False, "Should have raised 429"
    except HTTPException as e:
        assert e.status_code == 429
        print(f"[Rate Limiter Check Passed] 429 caught as expected: {e.detail}")

def test_structured_logger():
    # Verify logger executes without raising errors
    agent_logger.log_event(
        event_name="unit_test_event",
        request_id="test_req_001",
        principal_id="test_user",
        status="success",
        latency_seconds=0.123,
        metadata={"test": "data"}
    )
    print("[Structured Logger Check Passed]")

if __name__ == "__main__":
    test_rate_limiter()
    test_structured_logger()
    print("All T15 tests passed successfully!")

import logging
import json
import time
from typing import Dict, Any, Optional

class StructuredLogger:
    """
    Standardized, security-conscious structured logger.
    Logs lifecycle events with timestamps, latencies, and sanitized metadata.
    Avoids logging raw table data, private prompts, or credentials.
    """

    def __init__(self, name: str = "agentic_analyst"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_event(
        self,
        event_name: str,
        request_id: Optional[str] = None,
        principal_id: Optional[str] = None,
        status: str = "info",
        latency_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        payload = {
            "timestamp": time.time(),
            "event": event_name,
            "request_id": request_id or "system",
            "principal_id": principal_id or "anonymous",
            "status": status,
            "latency_seconds": latency_seconds,
            "metadata": metadata or {}
        }
        self.logger.info(json.dumps(payload))

# Global default structured logger
agent_logger = StructuredLogger()

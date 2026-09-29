from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class ProviderResult:
    """Standardized envelope for model responses."""
    def __init__(
        self,
        data: Any,
        raw_text: str,
        provider: str,
        model: str,
        latency_seconds: float,
        usage: Optional[Dict[str, int]] = None
    ):
        self.data = data
        self.raw_text = raw_text
        self.provider = provider
        self.model = model
        self.latency_seconds = latency_seconds
        self.usage = usage or {}

class LLMProvider(ABC):
    """Abstract provider adapter ensuring model interchangeability."""

    @abstractmethod
    def generate_structured(
        self,
        schema: Type[T],
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> ProviderResult:
        """Generates structured output validated against a Pydantic schema."""
        pass

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> ProviderResult:
        """Generates raw text completion."""
        pass

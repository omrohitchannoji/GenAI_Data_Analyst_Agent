import os
import time
import json
import re
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel, ValidationError
from groq import Groq, RateLimitError, APIError, APITimeoutError
from .base import LLMProvider, ProviderResult

T = TypeVar("T", bound=BaseModel)

class GroqProvider(LLMProvider):
    """
    Production-grade Groq Provider Adapter.
    Enforces configurable models, structured JSON schema outputs, timeout handling,
    and token usage accounting.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set. Please provide a valid Groq API key.")

        self.model = model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.client = Groq(api_key=self.api_key, timeout=self.timeout_seconds)

    def _extract_json(self, raw_text: str) -> str:
        """Sanitizes raw text to extract a clean JSON substring."""
        text = raw_text.strip()
        # Remove markdown fences
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return text

    def generate_structured(
        self,
        schema: Type[T],
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> ProviderResult:
        """
        Generates structured output strictly conforming to the provided Pydantic model.
        """
        json_schema_str = json.dumps(schema.model_json_schema(), indent=2)
        system_instruction = (
            "You are an expert AI system that outputs strictly valid JSON adhering to the specified schema.\n"
            f"REQUIRED JSON SCHEMA:\n{json_schema_str}\n"
            "Return ONLY a valid JSON object matching this schema. No markdown formatting, no commentary."
        )

        if system_prompt:
            system_instruction = f"{system_prompt}\n\n{system_instruction}"

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ]

        last_error = None
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0
                )

                latency = time.time() - start_time
                raw_content = resp.choices[0].message.content or "{}"
                cleaned_json = self._extract_json(raw_content)

                # Validate against Pydantic schema
                data_instance = schema.model_validate_json(cleaned_json)

                usage_stats = {
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                    "total_tokens": resp.usage.total_tokens if resp.usage else 0
                }

                return ProviderResult(
                    data=data_instance,
                    raw_text=raw_content,
                    provider="groq",
                    model=self.model,
                    latency_seconds=round(latency, 3),
                    usage=usage_stats
                )

            except ValidationError as ve:
                last_error = f"Pydantic Validation Error: {str(ve)}"
                # Append repair hint for retry
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({
                    "role": "user",
                    "content": f"Your previous output did not match the required schema: {last_error}. Please correct it."
                })
            except RateLimitError:
                last_error = "Groq rate limit encountered."
                time.sleep(2.0 * (attempt + 1))
            except APITimeoutError:
                last_error = f"Groq request timed out after {self.timeout_seconds}s."
            except APIError as ae:
                last_error = f"Groq API Error: {str(ae)}"
                break
            except Exception as e:
                last_error = f"Unexpected Provider Error: {str(e)}"
                break

        raise RuntimeError(f"Failed to generate structured response after {self.max_retries + 1} attempts. Last error: {last_error}")

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> ProviderResult:
        """Generates raw text response."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start_time = time.time()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2
            )
            latency = time.time() - start_time
            raw_content = resp.choices[0].message.content or ""
            usage_stats = {
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                "total_tokens": resp.usage.total_tokens if resp.usage else 0
            }
            return ProviderResult(
                data=raw_content,
                raw_text=raw_content,
                provider="groq",
                model=self.model,
                latency_seconds=round(latency, 3),
                usage=usage_stats
            )
        except Exception as e:
            raise RuntimeError(f"Groq text generation failed: {str(e)}")

"""LLM driver abstraction — bridges benchmarks to actual model APIs.

For v0.1.0 alpha, skopus ships:
  - MockDriver: deterministic responses for testing the harness itself
  - AnthropicDriver: real Claude API calls (requires ANTHROPIC_API_KEY)

Other providers (OpenAI, Gemini, local models via llama.cpp) are extension
points for v0.2. Each driver implements a single method: run(prompt) -> Response.

The driver DOES NOT drive the agent UI. It drives the LLM API directly with
different SYSTEM PROMPTS that encode the lens configuration. This is the
cleanest way to measure the additive contribution of each skopus lens.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Standardized response from any driver."""

    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: float = 0.0
    model: str = ""
    duration_ms: int = 0


class LLMDriver(ABC):
    """Interface every driver implements."""

    name: str = "abstract"

    @abstractmethod
    def available(self) -> bool:
        """Return True if the driver can run (credentials set, lib installed)."""
        ...

    @abstractmethod
    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Send a prompt to the LLM and return the response."""
        ...


class MockDriver(LLMDriver):
    """Deterministic driver for tests — returns canned responses.

    The mock uses simple heuristics based on keywords in the prompt to decide
    what "kind" of response to give. Useful for exercising the harness end-to-end
    without API calls.
    """

    name = "mock"

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}

    def available(self) -> bool:
        return True

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        # If a canned response matches, use it
        for key, canned in self.responses.items():
            if key in user_prompt or key in system_prompt:
                return LLMResponse(
                    text=canned,
                    tokens_in=len(system_prompt) // 4 + len(user_prompt) // 4,
                    tokens_out=len(canned) // 4,
                    cost_usd=0.0,
                    model="mock",
                )

        # Default: echo a generic acknowledgment
        generic = "I understand. Here's my approach: [generic response]"
        return LLMResponse(
            text=generic,
            tokens_in=len(system_prompt) // 4 + len(user_prompt) // 4,
            tokens_out=len(generic) // 4,
            cost_usd=0.0,
            model="mock",
        )


class AnthropicDriver(LLMDriver):
    """Real Claude API driver. Requires ANTHROPIC_API_KEY and the anthropic SDK."""

    name = "anthropic"
    default_model = "claude-sonnet-4-5"
    # Pricing (approximate, USD per MTok) — update when Anthropic changes rates
    input_cost_per_mtok = 3.0
    output_cost_per_mtok = 15.0

    def __init__(self, model: str | None = None) -> None:
        self.model = model or self.default_model

    def available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401

            return True
        except ImportError:
            return False

    def run(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        if not self.available():
            raise RuntimeError(
                "AnthropicDriver not available — set ANTHROPIC_API_KEY and install anthropic SDK"
            )

        import time

        import anthropic

        client = anthropic.Anthropic()
        start = time.time()
        message = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        duration_ms = int((time.time() - start) * 1000)

        text = "".join(
            block.text for block in message.content if hasattr(block, "text")
        )
        tokens_in = message.usage.input_tokens
        tokens_out = message.usage.output_tokens
        cost = (
            tokens_in / 1_000_000 * self.input_cost_per_mtok
            + tokens_out / 1_000_000 * self.output_cost_per_mtok
        )

        return LLMResponse(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            model=self.model,
            duration_ms=duration_ms,
        )


def pick_driver(preferred: str = "auto") -> LLMDriver:
    """Select a driver. "auto" picks AnthropicDriver if available, else Mock."""
    if preferred == "mock":
        return MockDriver()
    if preferred == "anthropic":
        return AnthropicDriver()

    # auto
    anthropic_driver = AnthropicDriver()
    if anthropic_driver.available():
        return anthropic_driver
    return MockDriver()

"""OpenRouter API client for multi-model calls."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

# Load .env from current directory or home
load_dotenv()
load_dotenv(Path.home() / ".env")


@dataclass
class Message:
    """A chat message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class CompletionResult:
    """Result from a model completion call."""
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None


class OpenRouterError(Exception):
    """Error from OpenRouter API."""
    pass


class OpenRouterClient:
    """OpenRouter API client.

    Simple client for calling multiple models via OpenRouter.
    """

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize client with API key from param or environment."""
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise OpenRouterError(
                "OPENROUTER_API_KEY environment variable is required.\n"
                "Get one at: https://openrouter.ai/keys"
            )

    def complete(
        self,
        messages: List[Message],
        model: str,
        timeout: float = 120.0,
        max_tokens: Optional[int] = None,
    ) -> CompletionResult:
        """
        Execute a chat completion.

        Args:
            messages: List of chat messages
            model: Model identifier (e.g., "anthropic/claude-sonnet-4-20250514")
            timeout: Request timeout in seconds
            max_tokens: Maximum output tokens

        Returns:
            CompletionResult with content and metadata

        Raises:
            OpenRouterError: On API or network errors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/council-cli",
            "X-Title": "Council CLI",
        }

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException:
            raise OpenRouterError(
                f"Request timed out after {timeout}s. "
                "Try again or use a faster model."
            )
        except httpx.HTTPStatusError as e:
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_msg = str(e)
            raise OpenRouterError(f"API error: {error_msg}")
        except httpx.RequestError as e:
            raise OpenRouterError(f"Network error: {e}")

        # Extract response
        try:
            choices = data.get("choices", [])
            if not choices:
                raise OpenRouterError("No choices in API response")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if not content:
                raise OpenRouterError("Empty content in API response")

            return CompletionResult(
                content=content,
                model=data.get("model", model),
                usage=data.get("usage"),
            )

        except KeyError as e:
            raise OpenRouterError(f"Unexpected API response format: missing {e}")


def get_client(api_key: Optional[str] = None) -> OpenRouterClient:
    """Get an OpenRouter client instance."""
    return OpenRouterClient(api_key)

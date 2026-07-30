"""
Multi-AI Model Client Layer
Supports DeepSeek (primary) with extensible architecture for future models.
"""
import json
import time
import requests
from abc import ABC, abstractmethod
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, AI_TEMPERATURE, AI_MAX_TOKENS


class BaseAIClient(ABC):
    """Abstract base for AI model clients."""

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        pass

    @abstractmethod
    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        pass


class DeepSeekClient(BaseAIClient):
    """DeepSeek API client (OpenAI-compatible)."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.model = model or DEEPSEEK_MODEL

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": AI_TEMPERATURE,
            "max_tokens": AI_MAX_TOKENS,
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        raw = self.chat(system_prompt, user_prompt)
        # strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        return json.loads(cleaned)


class OpenAIClient(BaseAIClient):
    """Future: OpenAI/ChatGPT client."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError("OpenAI client - configure API key to enable")

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        raise NotImplementedError("OpenAI client - configure API key to enable")


class GeminiClient(BaseAIClient):
    """Future: Google Gemini client."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        self.api_key = api_key
        self.model = model

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError("Gemini client - configure API key to enable")

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        raise NotImplementedError("Gemini client - configure API key to enable")


# === Factory ===
AI_REGISTRY = {
    "deepseek": DeepSeekClient,
    "openai": OpenAIClient,
    "gemini": GeminiClient,
}


def get_ai_client(provider: str = "deepseek", **kwargs) -> BaseAIClient:
    """Get an AI client by provider name."""
    cls = AI_REGISTRY.get(provider)
    if not cls:
        raise ValueError(f"Unknown AI provider: {provider}. Available: {list(AI_REGISTRY.keys())}")
    return cls(**kwargs)

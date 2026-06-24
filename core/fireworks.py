"""
Fireworks AI client — all LLM and embedding calls go through here.
Uses AMD GPU hardware via Fireworks API (OpenAI-compatible endpoint).
Never import openai directly in agents/connectors — use this client.
"""

import json
from typing import AsyncGenerator

import httpx

from config import config


class FireworksClient:
    def __init__(self):
        # Text completions client configs (Groq -> Fireworks)
        self.api_key = config.GROQ_API_KEY or config.FIREWORKS_API_KEY
        self.base_url = config.GROQ_BASE_URL if config.GROQ_API_KEY else config.FIREWORKS_BASE_URL
        self.model = config.GROQ_MODEL if config.GROQ_API_KEY else config.FIREWORKS_MODEL

        # Embeddings client configs (Gemini -> Fireworks)
        self.embed_api_key = config.GEMINI_API_KEY or config.FIREWORKS_API_KEY
        self.embed_base_url = config.GEMINI_BASE_URL if config.GEMINI_API_KEY else config.FIREWORKS_BASE_URL
        self.embed_model = config.GEMINI_EMBED_MODEL if config.GEMINI_API_KEY else config.FIREWORKS_EMBED_MODEL

    # ── Text completion ───────────────────────────────────────────────────────

    async def complete(self, prompt: str, system: str = None, max_tokens: int = 2000) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def stream(
        self, prompt: str, system: str = None, max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    # ── Embeddings ────────────────────────────────────────────────────────────

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.embed_base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.embed_api_key}"},
                json={
                    "model": self.embed_model,
                    "input": text[:8000],  # safe truncation
                },
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.embed_base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.embed_api_key}"},
                json={
                    "model": self.embed_model,
                    "input": [t[:8000] for t in texts],
                },
            )
            response.raise_for_status()
            items = sorted(response.json()["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in items]


# Singleton — import and use directly
fireworks = FireworksClient()

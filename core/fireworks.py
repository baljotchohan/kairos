"""
Fireworks AI client — all LLM and embedding calls go through here.
Uses AMD GPU hardware via Fireworks API (OpenAI-compatible endpoint).
Never import openai directly in agents/connectors — use this client.

Provider priority for text completions: Fireworks (AMD hardware, hackathon
requirement) → Groq → Gemini. On 429 (rate limit) or a dead key, automatically
falls back to the next provider.
"""

import json
from typing import AsyncGenerator

import httpx

from config import config


def _providers() -> list[tuple[str, str, str]]:
    """Return (api_key, base_url, model) in priority order, skipping unconfigured.

    Single source of truth is config.text_providers() — Fireworks (AMD) primary,
    then Groq + Gemini as fallbacks.
    """
    return [(k, u, m) for _name, k, u, m in config.text_providers()]


class FireworksClient:
    def __init__(self):
        # Embeddings: Gemini → Fireworks
        self.embed_api_key = config.GEMINI_API_KEY or config.FIREWORKS_API_KEY
        self.embed_base_url = config.GEMINI_BASE_URL if config.GEMINI_API_KEY else config.FIREWORKS_BASE_URL
        self.embed_model = config.GEMINI_EMBED_MODEL if config.GEMINI_API_KEY else config.FIREWORKS_EMBED_MODEL

    # ── Text completion ───────────────────────────────────────────────────────

    async def complete(self, prompt: str, system: str = None, max_tokens: int = 2000) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_err = None
        for api_key, base_url, model in _providers():
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": max_tokens,
                            "temperature": 0.1,
                        },
                    )
                    if response.status_code == 429:
                        print(f"[AI] Rate limited on {base_url} ({model}) — trying next provider")
                        last_err = f"429 on {model}"
                        continue
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                # Any failure here — a dead/invalid key (401/403), a provider
                # outage (5xx), or a network-level error (timeout/connection
                # refused, which isn't even an httpx.HTTPStatusError) — should
                # roll to the next provider, matching this function's own
                # docstring ("falls back to the next provider on 429 or a
                # dead key"). Only catching HTTPStatusError and re-raising
                # anything non-429 used to abort the whole call on the very
                # first provider tried, and silently dropped network errors
                # through uncaught entirely.
                print(f"[AI] {base_url} ({model}) failed ({str(e)[:140]}) — trying next provider")
                last_err = str(e)
                continue
        raise RuntimeError(f"All AI providers rate-limited or unavailable. Last error: {last_err}")

    async def stream(
        self, prompt: str, system: str = None, max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Find first non-rate-limited provider
        chosen = None
        for api_key, base_url, model in _providers():
            try:
                async with httpx.AsyncClient(timeout=10) as probe:
                    r = await probe.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                    )
                    if r.status_code == 429:
                        print(f"[AI] Rate limited on {base_url} ({model}) — trying next provider")
                        continue
                    chosen = (api_key, base_url, model)
                    break
            except Exception:
                chosen = (api_key, base_url, model)
                break

        if not chosen:
            yield "Error: all AI providers are currently rate-limited. Please try again in a few minutes."
            return

        api_key, base_url, model = chosen
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
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
                f"{self.embed_base_url.rstrip('/')}/embeddings",
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
                f"{self.embed_base_url.rstrip('/')}/embeddings",
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

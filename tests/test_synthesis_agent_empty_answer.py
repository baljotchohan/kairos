"""Tests for agents/synthesis_agent.py's execute() — specifically that a
clean (non-exception) LLM completion with zero content tokens still produces
a real, user-visible answer instead of blank chat content.

Observed live: a low-signal input (e.g. "hlo") classified under the "search"
intent with zero relevant decisions could produce an empty completion. The
chat bubble still rendered intent/confidence/traces (those come from
elsewhere), but the answer text itself was blank — looked broken even though
nothing raised. This predates the mid-stream-interruption fix (which only
guards the exception path, not a stream that completes normally with no
content), so it needed its own guard."""

from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from agents.synthesis_agent import SynthesisAgent


class _EmptyMemory:
    def hybrid_search(self, *args, **kwargs):
        return []


async def _empty_async_stream():
    return
    yield  # pragma: no cover - makes this an async generator with 0 items


@pytest.mark.asyncio
async def test_streaming_empty_completion_produces_fallback_answer():
    agent = SynthesisAgent(_EmptyMemory())
    captured_tokens = []

    async def fake_stream_callback(msg):
        if msg.get("type") == "token":
            captured_tokens.append(msg["content"])

    async def fake_call(*args, **kwargs):
        return _empty_async_stream()

    with patch.object(agent, "_chat_completion_with_fallback", new=fake_call):
        result = await agent.execute("hlo", stream_callback=fake_stream_callback)

    assert result["answer"].strip()
    assert captured_tokens  # the fallback must actually reach the client as a token


@pytest.mark.asyncio
async def test_non_streaming_empty_completion_produces_fallback_answer():
    agent = SynthesisAgent(_EmptyMemory())

    def _fake_response(content):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    async def fake_call(*args, **kwargs):
        return _fake_response(None)  # some providers return None for an empty completion

    with patch.object(agent, "_chat_completion_with_fallback", new=fake_call):
        result = await agent.execute("hlo")  # no stream_callback -> non-streaming branch

    assert result["answer"].strip()


@pytest.mark.asyncio
async def test_streaming_normal_completion_is_unaffected():
    """The fallback must only kick in for a genuinely empty completion —
    a real answer must pass through untouched."""
    agent = SynthesisAgent(_EmptyMemory())

    async def fake_stream_callback(msg):
        pass

    async def real_stream():
        chunk = SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello there!"))])
        yield chunk

    async def fake_call(*args, **kwargs):
        return real_stream()

    with patch.object(agent, "_chat_completion_with_fallback", new=fake_call):
        result = await agent.execute("hlo", stream_callback=fake_stream_callback)

    assert result["answer"] == "Hello there!"

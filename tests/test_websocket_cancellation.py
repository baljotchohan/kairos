"""Tests for api/websocket.py's _run_cancellably — proves an in-flight
query/ingest is actually cancelled on client disconnect instead of running to
completion and wasting LLM tokens/compute for an abandoned request.

Uses a minimal fake WebSocket (duck-typed, only needs an async receive())
rather than a full TestClient WS session, so cancellation timing is
deterministic instead of depending on real thread/event-loop scheduling.
"""

import asyncio

import pytest
from fastapi import WebSocketDisconnect

from api.websocket import _run_cancellably


class FakeWebSocket:
    def __init__(self):
        self._messages: list[dict] = []

    async def receive(self):
        while not self._messages:
            await asyncio.sleep(0.005)
        return self._messages.pop(0)


@pytest.mark.asyncio
async def test_run_cancellably_cancels_work_on_disconnect():
    fake_ws = FakeWebSocket()
    cancelled = asyncio.Event()

    async def slow_work():
        try:
            await asyncio.sleep(10)
            return "should never reach here"
        except asyncio.CancelledError:
            cancelled.set()
            raise

    task = asyncio.create_task(_run_cancellably(fake_ws, slow_work()))
    await asyncio.sleep(0.02)  # let the race start before "disconnecting"
    fake_ws._messages.append({"type": "websocket.disconnect", "code": 1000})

    with pytest.raises(WebSocketDisconnect):
        await task

    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_run_cancellably_returns_result_when_work_finishes_first():
    fake_ws = FakeWebSocket()

    async def quick_work():
        await asyncio.sleep(0.01)
        return "answer"

    result = await _run_cancellably(fake_ws, quick_work())
    assert result == "answer"


@pytest.mark.asyncio
async def test_run_cancellably_drops_unexpected_non_disconnect_message():
    """Our own frontend never sends a second message while a query is
    streaming, but if something did, it must not corrupt the single-flight
    request/response contract — the in-flight work should still complete
    and return its real result rather than being clobbered."""
    fake_ws = FakeWebSocket()

    async def quick_work():
        await asyncio.sleep(0.03)
        return "answer"

    task = asyncio.create_task(_run_cancellably(fake_ws, quick_work()))
    await asyncio.sleep(0.005)
    fake_ws._messages.append({"type": "websocket.receive", "text": "unexpected concurrent message"})

    result = await task
    assert result == "answer"

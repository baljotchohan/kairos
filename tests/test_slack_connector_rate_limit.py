"""Tests for connectors/slack_connector.py's rate-limit handling.

Every pagination loop in this connector catches a bare `except Exception: break`
around Slack API calls, treating a 429 identically to genuine end-of-data —
a rate-limited request silently returned partial results as if complete, with
no retry. Rather than hand-writing a retry loop (as github_connector.py has
to, since httpx has no built-in equivalent), slack_sdk ships an official
AsyncRateLimitErrorRetryHandler that respects Slack's Retry-After header."""

import asyncio
from unittest.mock import patch

import pytest

from connectors.slack_connector import SlackConnector


class _FakeAioResponse:
    def __init__(self, status, body, headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}
        self.content_type = "application/json"

    async def json(self, **kw):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
async def test_client_retries_automatically_after_a_429():
    connector = SlackConnector(token="xoxb-fake-token-1234567890123456789012345")
    client = connector._get_client()

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return _FakeAioResponse(429, {"ok": False, "error": "ratelimited"}, headers={"Retry-After": "0"})
        return _FakeAioResponse(200, {"ok": True, "channels": [], "response_metadata": {}})

    with patch("aiohttp.ClientSession.request", side_effect=fake_request):
        result = await client.conversations_list(types="public_channel", limit=10)

    assert result.get("ok") is True
    assert len(calls) == 2  # one rate-limited attempt + one successful retry


def test_retry_handler_is_attached_to_every_constructed_client():
    from slack_sdk.http_retry.builtin_async_handlers import AsyncRateLimitErrorRetryHandler

    connector = SlackConnector(token="xoxb-fake-token-1234567890123456789012345")
    client = connector._get_client()

    assert any(isinstance(h, AsyncRateLimitErrorRetryHandler) for h in client.retry_handlers)

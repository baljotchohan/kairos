"""Tests for connectors/github_connector.py's rate-limit handling.

A bare `resp.raise_for_status()` made a 429/secondary-rate-limit response
indistinguishable from any other HTTP error to callers — they caught broadly
and just stopped paginating, so a rate-limited request silently returned
whatever partial data had already been fetched as if it were the complete
result, with zero backoff or retry."""

from unittest.mock import MagicMock

import pytest

from connectors.github_connector import GitHubConnector


class _FakeResp:
    def __init__(self, status, headers=None, json_body=None):
        self.status_code = status
        self.headers = headers or {}
        self._json = json_body if json_body is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json


@pytest.mark.asyncio
async def test_get_with_retry_retries_once_after_429_then_succeeds():
    connector = GitHubConnector(access_token="ghp_faketoken1234567890")
    calls = []

    async def fake_get(url, params=None):
        calls.append(1)
        if len(calls) == 1:
            return _FakeResp(429, headers={"retry-after": "0"})
        return _FakeResp(200, json_body={"ok": True})

    client = MagicMock()
    client.get = fake_get

    result = await connector._get_with_retry(client, "https://api.github.com/whatever")

    assert result.json() == {"ok": True}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_get_with_retry_gives_up_after_max_retries():
    connector = GitHubConnector(access_token="ghp_faketoken1234567890")
    calls = []

    async def always_rate_limited(url, params=None):
        calls.append(1)
        return _FakeResp(429, headers={"retry-after": "0"})

    client = MagicMock()
    client.get = always_rate_limited

    with pytest.raises(Exception):
        await connector._get_with_retry(client, "https://api.github.com/whatever", max_retries=2)

    assert len(calls) == 3  # initial attempt + 2 retries


@pytest.mark.asyncio
async def test_get_with_retry_does_not_retry_non_rate_limit_errors():
    """A genuine 404/other error must surface immediately — retry logic is
    specifically for rate limiting, not a general-purpose retry-everything."""
    connector = GitHubConnector(access_token="ghp_faketoken1234567890")
    calls = []

    async def not_found(url, params=None):
        calls.append(1)
        return _FakeResp(404)

    client = MagicMock()
    client.get = not_found

    with pytest.raises(Exception):
        await connector._get_with_retry(client, "https://api.github.com/whatever")

    assert len(calls) == 1  # no retry attempted for a plain 404

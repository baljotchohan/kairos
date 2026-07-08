"""Tests for connectors/notion_connector.py's rate-limit handling.

Every pagination loop (search_pages, get_page_text, get_database_rows) used
to catch a bare `except Exception: break` around a raw httpx call with
`resp.raise_for_status()`, treating a 429 identically to genuine
end-of-pagination — a rate-limited request silently returned whatever
partial data had already been fetched as if it were the complete result."""

from unittest.mock import MagicMock

import pytest

from connectors.notion_connector import NotionConnector


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
async def test_request_with_retry_retries_once_after_429_then_succeeds():
    connector = NotionConnector(api_key="secret_faketoken")
    calls = []

    async def fake_request(method, url, headers=None, json=None, params=None):
        calls.append(1)
        if len(calls) == 1:
            return _FakeResp(429, headers={"retry-after": "0"})
        return _FakeResp(200, json_body={"ok": True})

    client = MagicMock()
    client.request = fake_request

    result = await connector._request_with_retry(client, "POST", "https://api.notion.com/v1/search", json={})

    assert result.json() == {"ok": True}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_request_with_retry_gives_up_after_max_retries():
    connector = NotionConnector(api_key="secret_faketoken")
    calls = []

    async def always_rate_limited(method, url, headers=None, json=None, params=None):
        calls.append(1)
        return _FakeResp(429, headers={"retry-after": "0"})

    client = MagicMock()
    client.request = always_rate_limited

    with pytest.raises(Exception):
        await connector._request_with_retry(client, "GET", "https://api.notion.com/v1/blocks/x/children", max_retries=2)

    assert len(calls) == 3  # initial attempt + 2 retries


@pytest.mark.asyncio
async def test_request_with_retry_does_not_retry_non_rate_limit_errors():
    connector = NotionConnector(api_key="secret_faketoken")
    calls = []

    async def not_found(method, url, headers=None, json=None, params=None):
        calls.append(1)
        return _FakeResp(404)

    client = MagicMock()
    client.request = not_found

    with pytest.raises(Exception):
        await connector._request_with_retry(client, "GET", "https://api.notion.com/v1/blocks/x/children")

    assert len(calls) == 1

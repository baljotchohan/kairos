"""Tests for connectors/jira_connector.py's rate-limit handling.

Every sync call site used a bare `resp.raise_for_status()` inside a broad
`except Exception` — a 429 was indistinguishable from any other error, so a
rate-limited request silently returned whatever partial data had already
been accumulated (or an empty result) as if it were complete."""

from unittest.mock import patch

import pytest

from connectors.jira_connector import JiraConnector


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


def _connector():
    return JiraConnector(access_token="fake-token", cloud_id="fake-cloud-id")


def test_request_with_retry_retries_once_after_429_then_succeeds():
    connector = _connector()
    calls = []

    def fake_request(method, url, auth=None, headers=None, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return _FakeResp(429, headers={"retry-after": "0"})
        return _FakeResp(200, json_body={"values": []})

    with patch("httpx.request", side_effect=fake_request):
        resp = connector._request_with_retry("GET", "https://api.atlassian.com/ex/jira/fake/rest/api/3/project/search")

    assert resp.json() == {"values": []}
    assert len(calls) == 2


def test_request_with_retry_gives_up_after_max_retries():
    connector = _connector()
    calls = []

    def always_rate_limited(method, url, auth=None, headers=None, **kwargs):
        calls.append(1)
        return _FakeResp(429, headers={"retry-after": "0"})

    with patch("httpx.request", side_effect=always_rate_limited):
        with pytest.raises(Exception):
            connector._request_with_retry("GET", "https://x/issue/1", max_retries=2)

    assert len(calls) == 3


def test_request_with_retry_respects_caller_supplied_headers_override():
    """_search_issues passes a merged headers dict (adds Content-Type) — the
    retry helper must use that instead of silently falling back to the
    connector's default headers, and must not raise a duplicate-keyword error."""
    connector = _connector()
    seen_headers = {}

    def fake_request(method, url, auth=None, headers=None, **kwargs):
        seen_headers.update(headers or {})
        return _FakeResp(200, json_body={"issues": [], "isLast": True})

    with patch("httpx.request", side_effect=fake_request):
        connector._request_with_retry(
            "POST", "https://x/search/jql",
            json={"jql": "status = Done"},
            headers={**connector._headers, "Content-Type": "application/json"},
        )

    assert seen_headers.get("Content-Type") == "application/json"


def test_no_raw_httpx_calls_remain_outside_the_retry_helper():
    """Guards against a future edit reintroducing a bare httpx.get/post call
    that bypasses rate-limit retry entirely."""
    import inspect
    import connectors.jira_connector as jira_mod

    source = inspect.getsource(jira_mod)
    assert "httpx.get(" not in source
    assert "httpx.post(" not in source

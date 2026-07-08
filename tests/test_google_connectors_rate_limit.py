"""Tests for gmail_connector.py / drive_connector.py's rate-limit handling.

Every .execute() call in both connectors is wrapped in a bare
`except Exception: break`/`return []`, which used to treat a 429 from the
Gmail/Drive API identically to genuine end-of-pagination — a rate-limited
call silently returned whatever partial data had already been fetched.
googleapiclient has a built-in exponential-backoff retry for 429/5xx via
`execute(num_retries=N)`; this verifies it's actually wired up and works,
not just present in the diff."""

import json

from googleapiclient.discovery import build
from googleapiclient.http import HttpMockSequence


def test_gmail_style_call_retries_past_a_429_via_num_retries():
    http = HttpMockSequence([
        ({"status": "429"}, json.dumps({"error": {"message": "rate limited"}}).encode()),
        ({"status": "200"}, json.dumps({"emailAddress": "test@example.com", "messagesTotal": 5, "threadsTotal": 2}).encode()),
    ])
    svc = build("gmail", "v1", http=http, cache_discovery=False)

    result = svc.users().getProfile(userId="me").execute(num_retries=3)

    assert result["emailAddress"] == "test@example.com"


def test_gmail_style_call_without_num_retries_fails_immediately_on_429():
    """Sanity check that the retry behavior is actually attributable to
    num_retries, not some other mock artifact — without it, the same 429
    sequence should raise."""
    from googleapiclient.errors import HttpError

    http = HttpMockSequence([
        ({"status": "429"}, json.dumps({"error": {"message": "rate limited"}}).encode()),
        ({"status": "200"}, json.dumps({"emailAddress": "test@example.com"}).encode()),
    ])
    svc = build("gmail", "v1", http=http, cache_discovery=False)

    try:
        svc.users().getProfile(userId="me").execute()  # no num_retries
        raised = False
    except HttpError:
        raised = True

    assert raised


def test_all_execute_call_sites_pass_num_retries():
    """Guards against a future edit accidentally reintroducing a bare
    .execute() call that silently drops the retry behavior."""
    import inspect
    import connectors.gmail_connector as gmail_mod
    import connectors.drive_connector as drive_mod

    for mod in (gmail_mod, drive_mod):
        source = inspect.getsource(mod)
        assert ".execute()" not in source, f"{mod.__name__} has a bare .execute() with no num_retries"

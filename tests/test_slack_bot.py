"""Tests for connectors/slack_bot.py's per-workspace routing.

A single Socket Mode connection (one SLACK_APP_TOKEN) receives app_mention
events for EVERY workspace this Slack app is installed to. The bot used to
answer ALL of them using whichever user connected Slack FIRST — a real
cross-tenant leak: a second team connecting their own Slack workspace would
see answers scoped to the first user's KAIROS memory, not their own."""

from unittest.mock import patch, AsyncMock

import pytest

from connectors.slack_bot import SlackBot


@pytest.fixture
def bot():
    b = SlackBot(orchestrator=None)
    b._team_creds = {
        "TEAM_A": ("xoxb-team-a-token-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "user-alice"),
        "TEAM_B": ("xoxb-team-b-token-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "user-bob"),
    }
    b._bot_user_ids = {"TEAM_A": "BOTALICE", "TEAM_B": "BOTBOB"}
    return b


def _mock_slack_client():
    patcher = patch("slack_sdk.web.async_client.AsyncWebClient")
    mock_cls = patcher.start()
    instance = mock_cls.return_value
    instance.chat_postMessage = AsyncMock(return_value={"ts": "123.456"})
    instance.chat_update = AsyncMock(return_value={"ok": True})
    return patcher


@pytest.mark.asyncio
async def test_mention_routes_to_the_mentioning_workspaces_own_user(bot):
    captured = {}

    async def fake_query_kairos(question, user_id):
        captured["user_id"] = user_id
        return ("answer", [], 0.9)

    bot._query_kairos = fake_query_kairos
    patcher = _mock_slack_client()
    try:
        event = {"channel": "C1", "ts": "1.1", "text": "<@BOTBOB> what did we decide", "user": "U999", "team": "TEAM_B"}
        await bot._handle_mention(event, {"team_id": "TEAM_B"})
    finally:
        patcher.stop()

    assert captured["user_id"] == "user-bob"


@pytest.mark.asyncio
async def test_two_different_workspaces_never_cross_contaminate(bot):
    """The core regression: TEAM_A's mention must never be answered using
    TEAM_B's (or any other) user_id, and vice versa."""
    captured = []

    async def fake_query_kairos(question, user_id):
        captured.append(user_id)
        return ("answer", [], 0.9)

    bot._query_kairos = fake_query_kairos
    patcher = _mock_slack_client()
    try:
        await bot._handle_mention(
            {"channel": "C1", "ts": "1.1", "text": "<@BOTALICE> hi", "user": "U1", "team": "TEAM_A"},
            {"team_id": "TEAM_A"},
        )
        await bot._handle_mention(
            {"channel": "C2", "ts": "2.1", "text": "<@BOTBOB> hi", "user": "U2", "team": "TEAM_B"},
            {"team_id": "TEAM_B"},
        )
    finally:
        patcher.stop()

    assert captured == ["user-alice", "user-bob"]


@pytest.mark.asyncio
async def test_mention_from_unrecognized_workspace_is_dropped_not_misattributed(bot):
    """A workspace with no matching KAIROS connection must be ignored
    entirely — never silently answered using some other connected user's
    memory."""
    captured = {}

    async def fake_query_kairos(question, user_id):
        captured["user_id"] = user_id
        return ("answer", [], 0.9)

    bot._query_kairos = fake_query_kairos
    patcher = _mock_slack_client()
    try:
        event = {"channel": "C3", "ts": "3.1", "text": "hey", "user": "U777", "team": "TEAM_UNKNOWN"}
        await bot._handle_mention(event, {"team_id": "TEAM_UNKNOWN"})
    finally:
        patcher.stop()

    assert "user_id" not in captured


@pytest.mark.asyncio
async def test_self_mention_is_ignored_per_workspace(bot):
    """Each workspace has its own bot user id — a bot message in TEAM_A must
    not be mistaken for a self-mention using TEAM_B's bot user id or
    vice versa."""
    called = {"count": 0}

    async def fake_query_kairos(question, user_id):
        called["count"] += 1
        return ("answer", [], 0.9)

    bot._query_kairos = fake_query_kairos
    patcher = _mock_slack_client()
    try:
        # TEAM_A's own bot posting — must be ignored
        await bot._handle_mention(
            {"channel": "C1", "ts": "1.1", "text": "hi", "user": "BOTALICE", "team": "TEAM_A"},
            {"team_id": "TEAM_A"},
        )
    finally:
        patcher.stop()

    assert called["count"] == 0

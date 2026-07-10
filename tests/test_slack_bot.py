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
    # (bot_token, user_uid, owner_slack_id). owner_slack_id is the Slack member
    # id of whoever connected the workspace — only they may query via @mention.
    b._team_creds = {
        "TEAM_A": ("xoxb-team-a-token-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "user-alice", "UALICE"),
        "TEAM_B": ("xoxb-team-b-token-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "user-bob", "UBOB"),
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
        # Mention comes from the workspace OWNER (UBOB) — allowed.
        event = {"channel": "C1", "ts": "1.1", "text": "<@BOTBOB> what did we decide", "user": "UBOB", "team": "TEAM_B"}
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
            {"channel": "C1", "ts": "1.1", "text": "<@BOTALICE> hi", "user": "UALICE", "team": "TEAM_A"},
            {"team_id": "TEAM_A"},
        )
        await bot._handle_mention(
            {"channel": "C2", "ts": "2.1", "text": "<@BOTBOB> hi", "user": "UBOB", "team": "TEAM_B"},
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


@pytest.mark.asyncio
async def test_non_owner_member_cannot_query_owners_memory(bot):
    """The access-control fix: a DIFFERENT workspace member mentioning the bot
    must NOT reach the owner's KAIROS memory — otherwise any coworker could
    read the owner's full cross-source private decisions (Gmail/Drive/Jira/…)
    just by being in the same Slack workspace."""
    captured = {}

    async def fake_query_kairos(question, user_id):
        captured["user_id"] = user_id
        return ("answer", [], 0.9)

    bot._query_kairos = fake_query_kairos
    patcher = _mock_slack_client()
    try:
        # A coworker (UEVE), NOT the owner (UBOB), mentions the bot in TEAM_B.
        event = {"channel": "C1", "ts": "1.1", "text": "<@BOTBOB> why do we pay this vendor", "user": "UEVE", "team": "TEAM_B"}
        await bot._handle_mention(event, {"team_id": "TEAM_B"})
    finally:
        patcher.stop()

    assert "user_id" not in captured  # memory was never queried


@pytest.mark.asyncio
async def test_legacy_connection_without_owner_id_fails_closed(bot):
    """A connection made before owner_slack_id was captured (empty string) must
    fail closed — we can't verify the asker is the owner, so we refuse rather
    than risk leaking the owner's memory to whoever mentions the bot."""
    captured = {}

    async def fake_query_kairos(question, user_id):
        captured["user_id"] = user_id
        return ("answer", [], 0.9)

    # Legacy: owner_slack_id is empty.
    bot._team_creds["TEAM_B"] = (
        "xoxb-team-b-token-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "user-bob", "",
    )
    bot._query_kairos = fake_query_kairos
    patcher = _mock_slack_client()
    try:
        event = {"channel": "C1", "ts": "1.1", "text": "<@BOTBOB> what did we decide", "user": "UBOB", "team": "TEAM_B"}
        await bot._handle_mention(event, {"team_id": "TEAM_B"})
    finally:
        patcher.stop()

    assert "user_id" not in captured  # refused even for the (unverifiable) owner

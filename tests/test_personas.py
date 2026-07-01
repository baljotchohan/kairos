"""Tests for core/personas.py — per-user agent display name/tone overrides."""

import pytest

from core.personas import AgentPersonaStore, DEFAULT_PERSONAS


@pytest.fixture
def store(tmp_path):
    return AgentPersonaStore(db_path=str(tmp_path / "test.db"))


def test_list_for_user_returns_all_defaults_when_no_overrides(store):
    personas = store.list_for_user("user-a")
    keys = {p["agent_key"] for p in personas}
    assert keys == set(DEFAULT_PERSONAS.keys())
    assert all(p["is_default"] for p in personas)


def test_upsert_overrides_display_name(store):
    result = store.upsert("user-a", "slack_agent", display_name="Watchtower", tone_preset="concise")
    assert result["display_name"] == "Watchtower"
    assert result["tone_preset"] == "concise"
    assert result["is_default"] is False

    fetched = store.get("user-a", "slack_agent")
    assert fetched["display_name"] == "Watchtower"


def test_upsert_scoped_per_user(store):
    store.upsert("user-a", "slack_agent", display_name="Watchtower")
    b_view = store.get("user-b", "slack_agent")
    assert b_view["is_default"] is True
    assert b_view["display_name"] != "Watchtower"


def test_upsert_rejects_unknown_agent_key(store):
    with pytest.raises(ValueError):
        store.upsert("user-a", "not_a_real_agent", display_name="X")


def test_upsert_rejects_invalid_tone_preset(store):
    with pytest.raises(ValueError):
        store.upsert("user-a", "slack_agent", tone_preset="sarcastic")


def test_reset_restores_default(store):
    store.upsert("user-a", "slack_agent", display_name="Watchtower")
    reset = store.reset("user-a", "slack_agent")
    assert reset["is_default"] is True
    assert store.get("user-a", "slack_agent")["display_name"] == reset["display_name"]


def test_partial_update_preserves_other_field(store):
    store.upsert("user-a", "slack_agent", display_name="Watchtower", tone_preset="analyst")
    updated = store.upsert("user-a", "slack_agent", tone_preset="concise")
    assert updated["display_name"] == "Watchtower"
    assert updated["tone_preset"] == "concise"

"""Tests for agents/synthesis_agent.py's extract_decisions() — specifically its
tolerance of malformed-but-JSON-valid LLM output, which previously crashed with
an uncaught AttributeError and permanently poisoned that ingestion item (it never
got marked processed, so it kept re-failing every cycle)."""

import json
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from core.memory import KairosMemory
from agents.synthesis_agent import SynthesisAgent, ExtractionFailedError

TEST_UID = "testuser"


@pytest.fixture
def memory(tmp_path):
    chroma_path = str(tmp_path / "chroma")
    db_path = str(tmp_path / "test.db")
    vault_path = str(tmp_path / "vault")
    with patch("core.memory.FireworksEmbeddingFunction") as mock_ef:
        from chromadb.utils import embedding_functions
        mock_ef.return_value = embedding_functions.DefaultEmbeddingFunction()
        mem = KairosMemory(chroma_path=chroma_path, db_path=db_path, obsidian_vault=vault_path)
    return mem


def _fake_llm_response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.asyncio
async def test_extract_decisions_skips_non_dict_list_elements(memory):
    agent = SynthesisAgent(memory)
    raw = json.dumps([
        "a stray string the LLM sometimes emits",
        None,
        {"title": "Valid Decision", "summary": "A real decision.", "date": "2024-01-01"},
    ])
    with patch.object(agent, "_chat_completion_with_fallback", new=AsyncMock(return_value=_fake_llm_response(raw))):
        stored = await agent.extract_decisions({"text": "some source content", "source": "slack"}, user_id=TEST_UID)

    assert len(stored) == 1
    assert stored[0].title == "Valid Decision"


@pytest.mark.asyncio
async def test_extract_decisions_all_non_dict_returns_empty(memory):
    agent = SynthesisAgent(memory)
    raw = json.dumps(["just", "strings", 42, None])
    with patch.object(agent, "_chat_completion_with_fallback", new=AsyncMock(return_value=_fake_llm_response(raw))):
        stored = await agent.extract_decisions({"text": "some source content", "source": "slack"}, user_id=TEST_UID)

    assert stored == []


@pytest.mark.asyncio
async def test_extract_decisions_raises_on_llm_call_failure(memory):
    """A genuine extraction FAILURE (full provider-chain exhaustion) must
    raise, not return [] — returning [] made it indistinguishable from "the
    model looked and found nothing", which caused core/orchestrator.py to
    permanently mark that ingestion item as processed even though it was
    never actually looked at, silently and permanently losing that decision."""
    agent = SynthesisAgent(memory)

    async def failing_call(*args, **kwargs):
        raise RuntimeError("all providers down")

    with patch.object(agent, "_chat_completion_with_fallback", new=failing_call):
        with pytest.raises(ExtractionFailedError):
            await agent.extract_decisions({"text": "some source content", "source": "slack"}, user_id=TEST_UID)


@pytest.mark.asyncio
async def test_extract_decisions_raises_on_malformed_json(memory):
    """A malformed (non-JSON) model response is also a genuine failure, not
    a legitimate "no decisions" result — must raise for the same reason as
    the LLM-call-failure case above."""
    agent = SynthesisAgent(memory)
    with patch.object(agent, "_chat_completion_with_fallback", new=AsyncMock(return_value=_fake_llm_response("not json at all {{{"))):
        with pytest.raises(ExtractionFailedError):
            await agent.extract_decisions({"text": "some source content", "source": "slack"}, user_id=TEST_UID)


@pytest.mark.asyncio
async def test_extract_decisions_legitimate_empty_result_does_not_raise(memory):
    """The model successfully looking at content and finding nothing is NOT
    a failure — it must return [] cleanly so the item is correctly marked
    processed (and not endlessly retried)."""
    agent = SynthesisAgent(memory)
    with patch.object(agent, "_chat_completion_with_fallback", new=AsyncMock(return_value=_fake_llm_response(json.dumps([])))):
        stored = await agent.extract_decisions({"text": "some source content", "source": "slack"}, user_id=TEST_UID)

    assert stored == []

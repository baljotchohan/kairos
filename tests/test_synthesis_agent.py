"""Tests for agents/synthesis_agent.py's extract_decisions() — specifically its
tolerance of malformed-but-JSON-valid LLM output, which previously crashed with
an uncaught AttributeError and permanently poisoned that ingestion item (it never
got marked processed, so it kept re-failing every cycle)."""

import json
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from core.memory import KairosMemory
from agents.synthesis_agent import SynthesisAgent

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

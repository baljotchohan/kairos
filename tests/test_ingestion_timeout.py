"""Tests for core/orchestrator.py's run_ingestion() lock timeout.

async with lock already releases correctly on a raised EXCEPTION — the gap
was a HANG (a connector/LLM call that never returns rather than raising)
inside the LangGraph pipeline, which held that user's ingestion lock forever.
From that point, trigger_ingestion() on both MCP transports would perpetually
report "a sync is already running", with no self-healing path short of a
process restart."""

import asyncio
from unittest.mock import patch

import pytest

from config import config
import core.orchestrator as orch_mod


class _HangingGraph:
    async def ainvoke(self, state):
        await asyncio.sleep(999)


def _bare_orchestrator():
    o = orch_mod.KairosOrchestrator.__new__(orch_mod.KairosOrchestrator)
    o.ingestion_locks = {}
    return o


@pytest.mark.asyncio
async def test_run_ingestion_times_out_instead_of_hanging_forever():
    with patch.object(config, "INGESTION_TIMEOUT_SECONDS", 0.2):
        orchestrator = _bare_orchestrator()
        orchestrator._graph = _HangingGraph()

        result = await orchestrator.run_ingestion("user-frank")

        assert result["status"] == "timeout"
        assert result["decisions_extracted"] == 0


@pytest.mark.asyncio
async def test_lock_is_released_after_a_timeout_not_stuck_forever():
    with patch.object(config, "INGESTION_TIMEOUT_SECONDS", 0.2):
        orchestrator = _bare_orchestrator()
        orchestrator._graph = _HangingGraph()

        await orchestrator.run_ingestion("user-frank")

        assert not orchestrator.ingestion_locks["user-frank"].locked()


@pytest.mark.asyncio
async def test_second_ingestion_call_proceeds_after_first_timed_out():
    """The regression this guards against: without a timeout, a hang left
    the lock held forever, so trigger_ingestion() on both MCP transports
    would perpetually report "a sync is already running" for that user."""
    with patch.object(config, "INGESTION_TIMEOUT_SECONDS", 0.1):
        orchestrator = _bare_orchestrator()
        orchestrator._graph = _HangingGraph()
        await orchestrator.run_ingestion("user-frank")

        orchestrator._graph = _HangingGraph()
        result = await orchestrator.run_ingestion("user-frank")

        assert result["status"] == "timeout"

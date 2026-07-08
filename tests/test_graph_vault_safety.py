"""Tests for core/graph.py using user_id as a filesystem path segment.

user_id is assumed to always be a Firebase UID, never raw user input — but
that assumption has one documented exception (api/auth.py's DEBUG-only
`sim-`/`simulated-` bypass, which derives it from token content). If that
assumption ever breaks, an unsanitized user_id in the Obsidian vault path
(`KAIROS_{user_id}`) could escape the vault directory via `../` segments."""

import os
import tempfile

import pytest

from core.graph import DecisionGraph, DecisionNode


def _node(user_id: str) -> DecisionNode:
    return DecisionNode(
        id="n1", title="Test Decision", summary="s", date="2026-01-01",
        participants=[], source="slack", source_url="https://x", topics=[],
        outcome="", raw_text="", metadata={}, user_id=user_id,
    )


def test_add_decision_sanitizes_path_traversal_in_user_id():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        vault_path = os.path.join(tmp, "vault")
        graph = DecisionGraph(db_path=db_path)

        malicious_uid = "sim-guest-uid-../../../../tmp/pwned"
        graph.add_decision(_node(malicious_uid), vault_path=vault_path)

        escaped = os.path.exists(os.path.join(tmp, "tmp", "pwned"))
        assert not escaped, "path traversal escaped the vault directory"

        written = os.listdir(vault_path)
        assert all(".." not in name and "/" not in name for name in written)


def test_export_to_obsidian_sanitizes_path_traversal_in_user_id():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        vault_path = os.path.join(tmp, "vault")
        graph = DecisionGraph(db_path=db_path)

        malicious_uid = "../../../../etc/pwned"
        graph.add_decision(_node(malicious_uid), vault_path=None)  # store without vault write first
        graph.export_to_obsidian(vault_path=vault_path, user_id=malicious_uid)

        escaped = os.path.exists(os.path.join(tmp, "etc", "pwned"))
        assert not escaped, "path traversal escaped the vault directory"


def test_normal_user_id_still_produces_expected_folder_name():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        vault_path = os.path.join(tmp, "vault")
        graph = DecisionGraph(db_path=db_path)

        graph.add_decision(_node("firebase-uid-abc123"), vault_path=vault_path)

        assert os.path.isdir(os.path.join(vault_path, "KAIROS_firebase-uid-abc123"))

"""Tests for api/main.py's CORS origin allowlist.

The old regex (`[a-z0-9-]*kairos[a-z0-9-]*\\.(vercel\\.app|hf\\.space)`)
matched ANY project containing the substring "kairos" anywhere in the
hostname — Vercel and Hugging Face Spaces are shared hosting platforms where
anyone can self-register a project like "kairos-phish.vercel.app" or
"x-kairos-y.hf.space", both of which satisfied the old pattern. It's
anchored to the actual project slug now."""

import re

from api.main import _ALLOWED_ORIGIN_REGEX


def _matches(origin: str) -> bool:
    return bool(re.fullmatch(_ALLOWED_ORIGIN_REGEX, origin))


def test_allows_production_vercel_domain():
    assert _matches("https://kairos-memory-os.vercel.app")


def test_allows_vercel_preview_subdomains():
    assert _matches("https://kairos-memory-os-git-main-baljots-projects.vercel.app")
    assert _matches("https://kairos-memory-os-abc123.vercel.app")


def test_allows_hf_space_domain():
    assert _matches("https://kairos-memory-os.hf.space")


def test_rejects_lookalike_project_names_containing_kairos_substring():
    """The exact vulnerability this regex used to have: any Vercel/HF project
    whose name merely CONTAINS "kairos" would pass."""
    assert not _matches("https://kairos-phish.vercel.app")
    assert not _matches("https://x-kairos-y.hf.space")
    assert not _matches("https://evilkairos-memory-os.vercel.app")
    assert not _matches("https://totally-unrelated-kairos-app.vercel.app")


def test_rejects_non_vercel_non_hf_hosts():
    assert not _matches("https://kairos-memory-os.attacker.com")
    assert not _matches("http://kairos-memory-os.vercel.app")  # not https

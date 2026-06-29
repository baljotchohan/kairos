"""
KAIROS — Central configuration.
All env vars live here. Import `config` everywhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Fireworks AI (AMD hardware — OpenAI-compatible) ────────────────────────
    FIREWORKS_API_KEY: str = os.getenv("FIREWORKS_API_KEY", "")
    FIREWORKS_BASE_URL: str = "https://api.fireworks.ai/inference/v1"
    FIREWORKS_MODEL: str = os.getenv(
        "FIREWORKS_MODEL",
        "accounts/fireworks/models/qwen2p5-72b-instruct"
    )
    # Cheap/fast Fireworks model for high-volume ingestion extraction — keeps
    # cost + latency down vs. running the 72B on every Slack/email/Drive item.
    FIREWORKS_MODEL_FAST: str = os.getenv(
        "FIREWORKS_MODEL_FAST",
        "accounts/fireworks/models/llama-v3p1-8b-instruct"
    )
    FIREWORKS_EMBED_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"

    # ── Groq API (Text Completions) ─────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    GROQ_MODEL_LARGE: str = "llama-3.3-70b-versatile"

    # ── Gemini API (Embeddings) ─────────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_EMBED_MODEL: str = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")

    # ── Memory ─────────────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./kairos.db")
    OBSIDIAN_VAULT: str = os.getenv("OBSIDIAN_VAULT", "./obsidian_vault")

    # ── Slack ──────────────────────────────────────────────────────────────────
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_APP_TOKEN: str = os.getenv("SLACK_APP_TOKEN", "")
    SLACK_CLIENT_ID: str = os.getenv("SLACK_CLIENT_ID", "")
    SLACK_CLIENT_SECRET: str = os.getenv("SLACK_CLIENT_SECRET", "")

    # ── Google Workspace (Gmail + Drive) ───────────────────────────────────────
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REFRESH_TOKEN: str = os.getenv("GOOGLE_REFRESH_TOKEN", "")

    # ── Zoom ───────────────────────────────────────────────────────────────────
    ZOOM_ACCOUNT_ID: str = os.getenv("ZOOM_ACCOUNT_ID", "")
    ZOOM_CLIENT_ID: str = os.getenv("ZOOM_CLIENT_ID", "")
    ZOOM_CLIENT_SECRET: str = os.getenv("ZOOM_CLIENT_SECRET", "")

    # ── Jira ───────────────────────────────────────────────────────────────────
    JIRA_URL: str = os.getenv("JIRA_URL", "")
    JIRA_EMAIL: str = os.getenv("JIRA_EMAIL", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    JIRA_CLIENT_ID: str = os.getenv("JIRA_CLIENT_ID", "")
    JIRA_CLIENT_SECRET: str = os.getenv("JIRA_CLIENT_SECRET", "")
    # Jira has no per-user OAuth yet — its credentials are global env vars. To avoid
    # serving the deployer's private Jira to EVERY user, the global Jira connector is
    # only attached for this owner uid (defaults to the demo user). Other users see
    # Jira as "not connected" until real per-user Jira OAuth lands.
    JIRA_OWNER_UID: str = os.getenv("JIRA_OWNER_UID", "") or os.getenv("DEMO_USER_ID", "demo-helios")

    # ── App ────────────────────────────────────────────────────────────────────
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    # Demo seed is OFF by default — KAIROS runs on real ingested data.
    SEED_DEMO_DATA: bool = os.getenv("SEED_DEMO_DATA", "false").lower() == "true"
    # The Helios Tech sample decisions are scoped to this synthetic demo user so
    # they only ever appear for the demo login — never in a real user's view. A
    # login whose email matches DEMO_LOGIN_EMAIL is mapped to DEMO_USER_ID (auth.py).
    DEMO_USER_ID: str = os.getenv("DEMO_USER_ID", "demo-helios")
    DEMO_LOGIN_EMAIL: str = os.getenv("DEMO_LOGIN_EMAIL", "demo@kairos.app")

    # ── Ingestion ──────────────────────────────────────────────────────────────
    SLACK_LOOKBACK_DAYS: int = int(os.getenv("SLACK_LOOKBACK_DAYS", "30"))
    EMAIL_LOOKBACK_DAYS: int = int(os.getenv("EMAIL_LOOKBACK_DAYS", "30"))
    INGEST_INTERVAL_MINUTES: int = int(os.getenv("INGEST_INTERVAL_MINUTES", "12"))
    MAX_MESSAGES_PER_CHANNEL: int = int(os.getenv("MAX_MESSAGES_PER_CHANNEL", "500"))
    # Throttle decision extraction to stay under the LLM provider's token/min
    # limit (Groq free tier = 6000 TPM). Items beyond the cap are picked up on
    # the next ingestion cycle (extraction is idempotent).
    MAX_EXTRACT_PER_CYCLE: int = int(os.getenv("MAX_EXTRACT_PER_CYCLE", "24"))
    EXTRACT_DELAY_SECONDS: float = float(os.getenv("EXTRACT_DELAY_SECONDS", "4"))

    # ── Text-generation provider chain ──────────────────────────────────────────
    # Single source of truth for which LLM providers serve text completions, in
    # priority order. Fireworks (AMD hardware) is PRIMARY per the hackathon's
    # "all AI via Fireworks" requirement and because its paid credits give far
    # higher rate limits than Groq's free tier (6k TPM, which a 5-agent system
    # blows through instantly). Groq + Gemini remain as automatic fallbacks so a
    # single provider hiccup never takes the product down.
    # Providers that returned an auth error (401/403) this process — skipped on
    # subsequent calls so an invalid/expired key costs one failed request, not a
    # latency tax on every call. Cleared on restart (paste a good key + restart).
    _dead_providers: set = set()

    def mark_provider_dead(self, base_url: str):
        """Disable a provider for the rest of the process (bad/expired key)."""
        self._dead_providers.add(base_url)

    def text_providers(self, fast: bool = False) -> list[tuple[str, str, str, str]]:
        """Ordered (name, api_key, base_url, model) for configured text providers.

        `fast=True` selects cheaper/faster models for high-volume ingestion
        extraction; `fast=False` selects the strongest models for user-facing answers.
        Providers with no API key — or ones disabled after an auth failure — are skipped.
        """
        fw_model = self.FIREWORKS_MODEL_FAST if fast else self.FIREWORKS_MODEL
        groq_model = self.GROQ_MODEL if fast else self.GROQ_MODEL_LARGE
        chain = [
            ("fireworks", self.FIREWORKS_API_KEY, self.FIREWORKS_BASE_URL, fw_model),
            ("groq", self.GROQ_API_KEY, self.GROQ_BASE_URL, groq_model),
            ("gemini", self.GEMINI_API_KEY, self.GEMINI_BASE_URL, self.GEMINI_MODEL),
        ]
        return [(n, k, u, m) for (n, k, u, m) in chain if k and u not in self._dead_providers]

    def primary_text(self, fast: bool = False) -> tuple[str, str, str]:
        """(api_key, base_url, model) for the highest-priority configured provider.

        Used by agents to build their default client. Falls back to Fireworks
        defaults if nothing is configured (so imports never crash).
        """
        chain = self.text_providers(fast=fast)
        if not chain:
            return ("", self.FIREWORKS_BASE_URL, self.FIREWORKS_MODEL)
        _name, key, url, model = chain[0]
        return (key, url, model)


config = Config()

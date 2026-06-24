"""
Email Agent — fetches Gmail messages and uses Fireworks AI to extract decisions
from email threads (approvals, rejections, contracts, strategy sign-offs).

Returns a list of DecisionNode objects ready to be stored in KairosMemory.
"""

from __future__ import annotations

import json
import uuid

from config import config
from core.fireworks import fireworks
from core.graph import DecisionNode


DECISION_SYSTEM = """You are an organizational memory AI. Extract decisions from email content.

A decision in email typically looks like:
- Subject lines with "approved", "rejected", "decision", "going with", "signed off"
- Body containing: contract approvals, vendor selections, hiring decisions, strategy sign-offs
- Phrases like: "we've decided to", "approved to proceed", "we will NOT be", "signed the contract"
- Budget approvals, policy changes, architectural decisions communicated via email

IGNORE: newsletters, automated notifications, scheduling emails, casual updates with no decision.

Return a JSON object:
{
  "is_decision": true or false,
  "title": "Short title (max 10 words)",
  "summary": "1-2 sentences describing the decision",
  "participants": ["Name or email1", "Name or email2"],
  "outcome": "What was decided",
  "topics": ["topic1", "topic2"],
  "alternatives_considered": ["option A", "option B"],
  "decision_maker": "Name/email of the person who made the final call",
  "decision_keywords": ["approved", "contract", "vendor", etc.]
}

If NO decision found, return exactly: {"is_decision": false}
Return ONLY valid JSON. No markdown fences, no explanation."""


from typing import Any

from agents.base_agent import BaseAgent, AgentTool, AgentResult

class EmailAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="email_agent",
            description="Fetches and extracts decisions from email threads",
            max_iterations=1
        )

    def _register_tools(self):
        self.register_tool(AgentTool(
            name="fetch_emails",
            description="Fetch raw emails for a lookback window.",
            handler=self.fetch
        ))
        self.register_tool(AgentTool(
            name="extract_email_decisions",
            description="Fetch and extract structured decision nodes from Gmail.",
            handler=self.run
        ))

    async def execute(self, input_data: Any, **kwargs) -> Any:
        days = input_data if isinstance(input_data, int) else None
        return await self.run(lookback_days=days)

    async def fetch(self, lookback_days: int = None) -> list[dict]:
        """Fetch raw email content from Gmail to pass to the synthesis agent."""
        days = lookback_days or config.EMAIL_LOOKBACK_DAYS
        if not config.GOOGLE_REFRESH_TOKEN:
            print("[EmailAgent] No GOOGLE_REFRESH_TOKEN configured — skipping")
            return []

        from connectors.gmail_connector import GmailConnector
        connector = GmailConnector()
        emails = await connector.get_messages(days_back=days, max_results=200)
        
        results = []
        for email_msg in emails:
            subject = email_msg.get("subject", "")
            body = email_msg.get("body", "")
            from_ = email_msg.get("from_", "")
            to = email_msg.get("to", "")
            date = email_msg.get("date", "")
            source_url = email_msg.get("source_url", "")
            
            full_text = f"Subject: {subject}\nFrom: {from_}\nTo: {to}\n\n{body}"
            if len(full_text.strip()) < 80:
                continue
            
            text_lower = full_text.lower()
            decision_signals = [
                "approved", "rejected", "decided", "decision", "going with",
                "signed off", "contract", "agreement", "vendor", "budget",
                "will not be", "moving forward", "we're choosing", "hired",
                "terminated", "cancelled", "signed", "authorize", "authorised",
            ]
            if not any(sig in text_lower for sig in decision_signals):
                continue

            results.append({
                "text": full_text,
                "source": "Email",
                "source_url": source_url,
                "date": date,
            })
        return results

    async def run(self, lookback_days: int = None) -> list[DecisionNode]:
        """
        Fetch emails from Gmail and extract decision nodes via Fireworks AI.
        """
        days = lookback_days or config.EMAIL_LOOKBACK_DAYS

        if not config.GOOGLE_REFRESH_TOKEN:
            print("[EmailAgent] No GOOGLE_REFRESH_TOKEN configured — skipping")
            return []

        print(f"[EmailAgent] Starting ingestion ({days} days lookback)")

        from connectors.gmail_connector import GmailConnector
        connector = GmailConnector()

        emails = await connector.get_messages(days_back=days, max_results=200)
        print(f"[EmailAgent] Processing {len(emails)} emails")

        decisions: list[DecisionNode] = []
        for email_msg in emails:
            extracted = await self._extract_decision(email_msg)
            if extracted:
                decisions.append(extracted)

        print(f"[EmailAgent] Extracted {len(decisions)} decisions")
        return decisions

    async def _extract_decision(self, email_msg: dict) -> DecisionNode | None:
        """Call Fireworks AI on a single email to determine if it contains a decision."""
        subject = email_msg.get("subject", "")
        body = email_msg.get("body", "")
        from_ = email_msg.get("from_", "")
        to = email_msg.get("to", "")
        date = email_msg.get("date", "")
        source_url = email_msg.get("source_url", "")
        participants = email_msg.get("participants", [])

        # Heuristic pre-filter: skip very short or clearly non-decision emails
        full_text = f"Subject: {subject}\nFrom: {from_}\nTo: {to}\n\n{body}"
        if len(full_text.strip()) < 80:
            return None

        # Quick keyword scan — skip if no decision signals at all
        text_lower = full_text.lower()
        decision_signals = [
            "approved", "rejected", "decided", "decision", "going with",
            "signed off", "contract", "agreement", "vendor", "budget",
            "will not be", "moving forward", "we're choosing", "hired",
            "terminated", "cancelled", "signed", "authorize", "authorised",
        ]
        if not any(sig in text_lower for sig in decision_signals):
            return None

        prompt = (
            f"From: {from_}\n"
            f"To: {to}\n"
            f"Date: {date}\n"
            f"Subject: {subject}\n\n"
            f"Body:\n---\n{body[:4000]}\n---\n\n"
            f"Is there a decision in this email? Extract it if so."
        )

        try:
            raw = await fireworks.complete(prompt, system=DECISION_SYSTEM, max_tokens=600)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
        except Exception as e:
            print(f"[EmailAgent] extraction error for '{subject}': {e}")
            return None

        if not data.get("is_decision"):
            return None

        title = data.get("title", "").strip()
        summary = data.get("summary", "").strip()
        if not title or not summary:
            return None

        return DecisionNode(
            id=str(uuid.uuid4()),
            title=title,
            summary=summary,
            date=date,
            participants=data.get("participants", participants),
            source="Email",
            source_url=source_url,
            topics=data.get("topics", []),
            outcome=data.get("outcome", ""),
            raw_text=full_text[:2000],
            metadata={
                "alternatives_considered": data.get("alternatives_considered", []),
                "decision_maker": data.get("decision_maker", from_),
                "subject": subject,
                "decision_keywords": data.get("decision_keywords", []),
            },
        )

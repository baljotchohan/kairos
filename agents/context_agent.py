"""
KAIROS Context Agent — Query Context Resolution.

Enriches queries with:
  - User conversation history (resolves "it", "that decision", etc.)
  - User profile context (role, interests, department)
  - Pronoun and reference resolution
  - Builds complete context object for the synthesis agent

Runs AFTER IntentAgent, BEFORE SynthesisAgent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import AsyncOpenAI

from config import config
from agents.base_agent import BaseAgent
from agents.intent_agent import QueryIntent
from core.user_memory import UserMemory, UserProfile


# ── Context Result ───────────────────────────────────────────────────────────

@dataclass
class ResolvedContext:
    """Complete resolved context for the synthesis agent."""
    original_query: str
    resolved_query: str          # Query with pronouns/references resolved
    intent: QueryIntent
    user_profile: Optional[dict] = None
    conversation_history: list[dict] = field(default_factory=list)
    personalization_prompt: str = ""   # Injected into system prompt
    memory_context_used: int = 0       # How many past interactions were used

    def to_dict(self) -> dict:
        return {
            "original_query": self.original_query,
            "resolved_query": self.resolved_query,
            "intent": self.intent.to_dict(),
            "user_profile": self.user_profile,
            "conversation_history_length": len(self.conversation_history),
            "personalization_prompt": self.personalization_prompt[:200],
            "memory_context_used": self.memory_context_used,
        }


# ── Resolution Prompt ────────────────────────────────────────────────────────

RESOLVE_SYSTEM = """You are a query resolution engine for KAIROS, a Company Organizational Memory system.

Your job is to take a user query that may contain pronouns, references, or vague language,
and rewrite it as a fully self-contained, explicit query.

Rules:
- Replace "it", "that", "this", "the decision" with specific references from conversation history
- Replace "he", "she", "they" with actual names if identifiable from context
- Expand abbreviations or shorthand
- Keep the rewritten query natural and concise
- If the query is already self-contained, return it as-is

Return ONLY the rewritten query text. No JSON, no markdown, no explanation."""


# ── Context Agent ────────────────────────────────────────────────────────────

class ContextAgent(BaseAgent):
    """
    Resolves query context by combining:
    - User conversation history
    - User profile (learned preferences)
    - Pronoun/reference resolution via LLM
    """

    def __init__(self, user_memory: UserMemory):
        super().__init__(
            name="context_agent",
            description="Resolves query context, pronouns, and references using conversation history and user profiles",
            max_iterations=1,
        )
        self.user_memory = user_memory

        # LLM client — Fireworks (AMD) primary; Groq + Gemini auto-fallback.
        api_key, base_url, self.model = config.primary_text()
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def execute(self, input_data: Any, **kwargs) -> ResolvedContext:
        """Resolve query context with user history and profile."""
        question = input_data if isinstance(input_data, str) else str(input_data)
        user_id = kwargs.get("user_id", "anonymous")
        intent: QueryIntent = kwargs.get("intent", QueryIntent(
            intent="search", confidence=0.5, search_strategy="semantic", rewritten_query=question
        ))

        self.think(f"Resolving context for user '{user_id}' with intent '{intent.intent}'")

        # 1. Get user profile
        profile = self.user_memory.get_profile(user_id)
        profile_dict = {
            "display_name": profile.display_name,
            "department": profile.department,
            "role_context": profile.role_context,
            "frequent_topics": profile.frequent_topics,
            "total_queries": profile.total_queries,
        }

        # 2. Get conversation history
        conversation_history = self.user_memory.get_current_session_context(
            user_id, max_turns=6
        )
        memory_count = len(conversation_history)

        self.observe(f"Found {memory_count} turns in current session, profile has {profile.total_queries} total queries")

        # 3. Resolve references if this is a follow-up or has history
        resolved_query = question
        if intent.requires_history and conversation_history:
            resolved_query = await self._resolve_references(question, conversation_history)
            self.think(f"Resolved query: \"{resolved_query[:80]}...\"")
        elif intent.rewritten_query:
            resolved_query = intent.rewritten_query

        # 4. Build personalization prompt
        personalization = self._build_personalization(profile)

        return ResolvedContext(
            original_query=question,
            resolved_query=resolved_query,
            intent=intent,
            user_profile=profile_dict,
            conversation_history=conversation_history,
            personalization_prompt=personalization,
            memory_context_used=memory_count,
        )

    async def _resolve_references(self, query: str, history: list[dict]) -> str:
        """Use LLM to resolve pronouns and references in the query."""
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content'][:300]}"
            for msg in history[-4:]
        ])

        prompt = f"""Conversation history:
{history_text}

New query to resolve: {query}

Rewrite the query to be fully self-contained:"""

        try:
            response = await self._chat_completion_with_fallback(
                client=self._client,
                model=self.model,
                messages=[
                    {"role": "system", "content": RESOLVE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=200,
            )
            resolved = response.choices[0].message.content.strip()
            # Sanity check — don't use if it's too different or empty
            if resolved and len(resolved) > 5:
                return resolved
            return query
        except Exception as e:
            self.observe(f"Reference resolution failed: {e}")
            return query

    def _build_personalization(self, profile: UserProfile) -> str:
        """Build a personalization prompt based on user profile."""
        parts = []

        if profile.display_name:
            parts.append(f"The user's name is {profile.display_name}.")

        if profile.department:
            parts.append(f"They work in the {profile.department} department.")

        if profile.role_context:
            parts.append(f"Context: {profile.role_context}")

        if profile.frequent_topics:
            topics = ", ".join(profile.frequent_topics[:5])
            parts.append(f"They frequently ask about: {topics}.")

        if profile.interaction_summary:
            parts.append(f"User history summary: {profile.interaction_summary}")

        if not parts:
            return ""

        return "User personalization context:\n" + "\n".join(parts)

    async def evaluate_confidence(self, input_data: Any, output: Any) -> float:
        """Higher confidence when we have more context."""
        if isinstance(output, ResolvedContext):
            base = 0.5
            if output.memory_context_used > 0:
                base += 0.15
            if output.user_profile and output.user_profile.get("role_context"):
                base += 0.15
            if output.resolved_query != output.original_query:
                base += 0.1
            return min(base, 1.0)
        return 0.5

    async def resolve(self, question: str, user_id: str, intent: QueryIntent) -> ResolvedContext:
        """Convenience method for direct context resolution."""
        result = await self.run(question, user_id=user_id, intent=intent)
        return result.output if result.success else ResolvedContext(
            original_query=question,
            resolved_query=question,
            intent=intent,
        )

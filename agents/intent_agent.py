"""
KAIROS Intent Agent — Query Intent Classification.

Runs BEFORE the synthesis agent to classify user queries and extract entities.
Determines the optimal retrieval strategy and detects follow-up queries
that reference previous conversational context.

Intent Categories:
  - search: General knowledge lookup ("Why do we use React?")
  - follow_up: References previous context ("Tell me more about that")
  - comparison: Comparing options ("What were the alternatives?")
  - timeline: Temporal queries ("When was this decided?")
  - person_lookup: People-focused ("Who approved this?")
  - what_if: Hypothetical ("What if we switched to Vue?")
  - summary: Aggregation ("How many decisions in Q3?")
  - store_decision: User is telling KAIROS to record a NEW decision ("add a decision that...", "remember that we decided...")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from config import config
from agents.base_agent import BaseAgent, AgentTool


# ── Intent Result ────────────────────────────────────────────────────────────

@dataclass
class QueryIntent:
    intent: str               # search | follow_up | comparison | timeline | person_lookup | what_if | summary | store_decision
    confidence: float         # 0.0 - 1.0
    entities: dict = field(default_factory=dict)  # extracted entities
    search_strategy: str = "semantic"  # semantic | structured | hybrid | graph
    requires_history: bool = False     # needs conversation history
    rewritten_query: str = ""          # clarified/expanded version of the query

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "entities": self.entities,
            "search_strategy": self.search_strategy,
            "requires_history": self.requires_history,
            "rewritten_query": self.rewritten_query,
        }


# ── Classification Prompt ────────────────────────────────────────────────────

INTENT_SYSTEM = """You are an intent classifier for KAIROS, a Company Organizational Memory system.

Classify the user's query into exactly one intent category and extract key entities.

Intent categories:
- "greeting": Casual conversation, greetings, small talk, thanks, or meta questions about KAIROS itself ("hi", "hello", "how are you", "who are you", "what can you do", "thanks", "help"). NOT a request to look up a past decision.
- "live_data": The user wants their CURRENT, real data from a connected tool right now — listing, counting, or looking up actual files, emails, messages, pages, tickets, repos, or recordings. IF THE QUERY NAMES A SPECIFIC CONNECTED TOOL (Slack, Gmail, Drive, Notion, Jira, Zoom, GitHub) AND asks to list/show/get/count/fetch its content, it is ALWAYS live_data — even if the wording is "list all" or "everything" (do NOT call that "summary"). Examples: "what's in my drive", "how many files do I have", "show my last email", "list my recent slack messages", "what are my jira tickets", "my zoom recordings", "list all data in notion", "list all my notion pages", "show me everything in notion", "list my github repos", "what are my open PRs", "search my github issues", "give me all my drive files". This is a LIVE lookup of the user's own data, NOT a past company decision.
- "search": General lookup of past decisions or organizational knowledge
- "follow_up": References previous conversation context ("tell me more", "that decision", "it", "what about...")
- "comparison": Comparing alternatives or options that were considered
- "timeline": Questions about when something happened or chronological ordering
- "person_lookup": Questions focused on who did something or who was involved
- "what_if": Hypothetical or counterfactual questions
- "summary": Aggregation or overview of STORED DECISIONS already in KAIROS memory ("how many decisions in Q3", "overview of our vendor decisions"). NOT for listing live data from a connected tool — if a tool (Slack/Gmail/Drive/Notion/Jira/Zoom/GitHub) is named, use live_data instead.
- "store_decision": The user is TELLING KAIROS to record a new decision, not asking a question about an existing one. Examples: "add a decision that we're hiring interns next week", "remember that we decided to use Postgres", "note in memory that the vendor contract was renewed", "add to the graph: we're launching in March". The giveaway is an imperative verb (add/remember/note/record/log) aimed at KAIROS itself plus a statement of fact, not a question.

Extract entities:
- people: Names of people mentioned
- topics: Technical or business topics mentioned
- dates: Any date references (absolute or relative)
- sources: Mentioned data sources (slack, email, drive, jira, meeting)

Determine search strategy:
- "semantic": Best for open-ended, natural language queries
- "structured": Best for specific filters (person, date range, topic)
- "hybrid": Combine both semantic + structured
- "graph": Best for relationship/connection queries

Return JSON only:
{
  "intent": "search",
  "confidence": 0.95,
  "entities": {"people": [], "topics": [], "dates": [], "sources": []},
  "search_strategy": "semantic",
  "requires_history": false,
  "rewritten_query": "expanded version of the query for better search"
}"""


# ── Intent Agent ─────────────────────────────────────────────────────────────

class IntentAgent(BaseAgent):
    """
    Classifies user query intent, extracts entities, and determines
    the optimal retrieval strategy before the synthesis agent runs.
    """

    def __init__(self):
        super().__init__(
            name="intent_agent",
            description="Classifies query intent, extracts entities, and determines retrieval strategy",
            max_iterations=1,
        )

        # LLM client — Fireworks (AMD) primary; Groq + Gemini auto-fallback.
        api_key, base_url, self.model = config.primary_text()
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        # Intent classification is cheap and latency-sensitive — a good fit for
        # Gemma 4's 26B-A4B mixture-of-experts (3.8B active params, so it runs
        # at small-model cost/latency) instead of the flagship reasoning model,
        # on the same AMD Instinct hardware Fireworks serves everything from.
        # Falls back to the primary provider chain above if this is unavailable.
        self._gemma_client = (
            AsyncOpenAI(api_key=config.FIREWORKS_API_KEY, base_url=config.FIREWORKS_BASE_URL)
            if config.FIREWORKS_API_KEY else None
        )

    async def execute(self, input_data: Any, **kwargs) -> QueryIntent:
        """Classify intent of a user query."""
        question = input_data if isinstance(input_data, str) else str(input_data)
        conversation_history = kwargs.get("conversation_history", [])

        self.think(f"Classifying intent for query: \"{question[:80]}...\"")

        # Build prompt with conversation context if available
        prompt = f"<user_query>{question}</user_query>"
        if conversation_history:
            history_text = "\n".join([
                f"{msg['role'].upper()}: {msg['content'][:200]}"
                for msg in conversation_history[-4:]
            ])
            prompt = f"<conversation_history>\n{history_text}\n</conversation_history>\n\n<user_query>{question}</user_query>"
            self.think("Including conversation history for follow-up detection")

        try:
            messages = [
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": prompt},
            ]

            response = None
            if self._gemma_client:
                try:
                    response = await self._gemma_client.chat.completions.create(
                        model=config.FIREWORKS_MODEL_GEMMA,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=500,
                    )
                    self.think("Classified via Gemma 4 26B-A4B (AMD Instinct, Fireworks)")
                except Exception as gemma_err:
                    self.observe(
                        f"Gemma 4 classification failed ({str(gemma_err)[:120]}); "
                        f"falling back to primary provider chain"
                    )

            if response is None:
                response = await self._chat_completion_with_fallback(
                    client=self._client,
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=500,
                )

            raw = response.choices[0].message.content.strip()

            import re
            match = re.search(r"(\{.*\})", raw, re.DOTALL)
            raw_json = match.group(1) if match else raw

            data = json.loads(raw_json)

            intent = QueryIntent(
                intent=data.get("intent", "search"),
                confidence=data.get("confidence", 0.5),
                entities=data.get("entities", {}),
                search_strategy=data.get("search_strategy", "semantic"),
                requires_history=data.get("requires_history", False),
                rewritten_query=data.get("rewritten_query", question),
            )

            self.observe(
                f"Intent: {intent.intent} (confidence: {intent.confidence:.0%}), "
                f"Strategy: {intent.search_strategy}, "
                f"Entities: {json.dumps(intent.entities)}"
            )

            return intent

        except Exception as e:
            self.observe(f"Classification failed: {e}. Falling back to default search intent.")
            return QueryIntent(
                intent="search",
                confidence=0.3,
                search_strategy="semantic",
                rewritten_query=question,
            )

    async def evaluate_confidence(self, input_data: Any, output: Any) -> float:
        """Use the classified intent's own confidence."""
        if isinstance(output, QueryIntent):
            return output.confidence
        return 0.5

    async def classify(self, question: str, conversation_history: list[dict] | None = None) -> QueryIntent:
        """Convenience method for direct classification."""
        result = await self.run(question, conversation_history=conversation_history or [])
        return result.output if result.success else QueryIntent(
            intent="search", confidence=0.3, search_strategy="semantic", rewritten_query=question
        )

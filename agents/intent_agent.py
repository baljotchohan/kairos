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
import re
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

INTENT_SYSTEM = """You are the ROUTER for KAIROS, a Company Organizational Memory system. Your only job: read the user's message, decide which ONE downstream handler should answer it, and extract entities. Reason about what the user actually WANTS — do not pattern-match on isolated keywords.

STEP 1 — Ignore conversational filler before deciding. Leading words such as "ok", "ok so", "so", "hey", "hi kairos", "please", "can you", "could you", "i want to", "now", "alright" carry NO routing meaning. Route on the real request underneath. "ok so what is my last mail" is the SAME request as "what is my last email".

STEP 2 — Pick EXACTLY ONE intent:

- "store_decision": The user is HANDING YOU A FACT to record/remember, not asking a question. Signal: an imperative aimed at KAIROS — add / record / remember / note / log / save / store / track / "put in memory" / "for the record" — followed by a statement of something that is or will be true. Examples: "add decision we are hiring interns next week", "remember that we decided to use Postgres", "note that the vendor contract was renewed", "log a decision: launching in March", "store this: Raj approved the AWS migration". It is STILL store_decision if phrased loosely or if the user asks you to fill in the date ("add the date yourself").

- "live_data": The user wants their OWN CURRENT data pulled LIVE from a connected tool right now — listing, counting, reading, searching, or fetching real emails, files, messages, pages, tickets, repos, PRs, issues, or recordings. This covers ANY reference to their mailbox (mail, email, e-mail, inbox, unread, "last mail", "latest message"), Drive/files, Slack messages, Notion pages, Jira tickets, Zoom recordings, or GitHub repos/PRs/issues — whether or not they name the tool. If they ask to "list/show/get/count/read/fetch/check my <thing a connected tool holds>", it is live_data. Examples: "what is my last mail", "how many unread emails do I have", "show my latest email from finance", "list all files in my drive", "what's in my drive", "any recent slack messages", "list my notion pages", "my open PRs", "what are my jira tickets". This is a LIVE lookup of the user's own data — NOT past company history, NOT an aggregate over stored memory.

- "greeting": Casual talk, greetings, thanks, or meta questions about KAIROS itself ("hi", "hello", "how are you", "who are you", "what can you do", "thanks", "help"). NOT a data lookup.

- "search": A QUESTION about a PAST company decision or organizational knowledge already captured in memory ("why do we use React?", "what did we decide about the vendor?", "has anyone tried a mobile app before?"). Use when the user ASKS why/what/how about history — not recording, not live data.

- "follow_up": Refers to the previous turn ("tell me more", "that decision", "what about it", "and then?"). Needs conversation history.

- "comparison": Comparing alternatives that were considered ("what were the other options?", "React vs Vue reasons").

- "timeline": When something happened / chronological order ("when was this decided?", "what happened first?").

- "person_lookup": Focused on WHO ("who approved this?", "who was involved?").

- "what_if": Hypothetical / counterfactual ("what if we had chosen Vue?").

- "summary": Aggregate/overview of STORED DECISIONS already in memory ("how many decisions in Q3?", "overview of our vendor decisions"). NOT for listing live tool data — if it's the user's live mailbox/drive/messages/tickets, use live_data.

STEP 3 — When torn, apply this priority:
1. Is the user handing you a fact to SAVE? → store_decision
2. Is the user asking for their own live tool data (mail/files/messages/tickets/repos/recordings)? → live_data
3. Is it chit-chat or "what can you do"? → greeting
4. Otherwise it's a question about history → search / comparison / timeline / person_lookup / what_if / summary

Extract entities:
- people: names mentioned
- topics: technical or business topics
- dates: any date reference (absolute or relative)
- sources: connected tools referenced (slack, gmail, drive, jira, zoom, notion, github)

Search strategy (best guess; use "semantic" for live_data / store_decision / greeting):
- "semantic": open-ended natural language
- "structured": specific filters (person, date range, topic)
- "hybrid": both
- "graph": relationship/connection queries

Return ONLY a JSON object — no prose, no markdown fences, no explanation:
{
  "intent": "live_data",
  "confidence": 0.96,
  "entities": {"people": [], "topics": [], "dates": [], "sources": ["gmail"]},
  "search_strategy": "semantic",
  "requires_history": false,
  "rewritten_query": "clean, filler-stripped version of the request"
}

Worked examples:
- "ok so what is my last mail" -> {"intent":"live_data","confidence":0.97,"entities":{"people":[],"topics":[],"dates":[],"sources":["gmail"]},"search_strategy":"semantic","requires_history":false,"rewritten_query":"what is my last email"}
- "how many unread emails do I have from finance" -> {"intent":"live_data","confidence":0.95,"entities":{"people":[],"topics":["finance"],"dates":[],"sources":["gmail"]},"search_strategy":"semantic","requires_history":false,"rewritten_query":"how many unread emails from finance"}
- "ok add decision we are hiring interns in next week with date add by yourself" -> {"intent":"store_decision","confidence":0.95,"entities":{"people":[],"topics":["hiring","interns"],"dates":["next week"],"sources":[]},"search_strategy":"semantic","requires_history":false,"rewritten_query":"record a decision: we are hiring interns next week"}
- "list all files in my drive" -> {"intent":"live_data","confidence":0.96,"entities":{"people":[],"topics":[],"dates":[],"sources":["drive"]},"search_strategy":"semantic","requires_history":false,"rewritten_query":"list all files in my drive"}
- "why did we choose React over Vue" -> {"intent":"comparison","confidence":0.9,"entities":{"people":[],"topics":["React","Vue"],"dates":[],"sources":[]},"search_strategy":"hybrid","requires_history":false,"rewritten_query":"why did we choose React over Vue"}
- "hey what can you do" -> {"intent":"greeting","confidence":0.97,"entities":{"people":[],"topics":[],"dates":[],"sources":[]},"search_strategy":"semantic","requires_history":false,"rewritten_query":"what can KAIROS do"}"""


# ── Robust JSON extraction ───────────────────────────────────────────────────

def _extract_json_object(raw: str) -> dict:
    """Pull the router's JSON out of a model response, tolerantly.

    Reasoning models (e.g. gpt-oss) prepend a <think>…</think> analysis pass and
    may wrap output in ```json fences or trail prose after the object. A naive
    ``json.loads`` throws on all of that and the caller then silently defaults to
    ``search`` — the exact bug that dropped 'add a decision…' and 'what is my
    last mail' into the dead memory-search path. Returns {} if nothing parses so
    the caller can decide how to fall back."""
    if not raw:
        return {}
    text = raw.strip()
    # Drop chain-of-thought preludes some reasoning models emit before the answer.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<\|.*?\|>", "", text, flags=re.DOTALL)  # harmony/channel markers
    # Strip ```json … ``` fences.
    text = re.sub(r"```(?:json)?", "", text).strip()

    # Fast path: the whole thing is the object.
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Otherwise scan for the first balanced {...} and parse it. More robust than a
    # greedy ``\{.*\}`` regex, which over-captures when reasoning text contains
    # stray braces or when the object is truncated.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return {}


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
        # Gemma's mixture-of-experts (small active-param count, so it runs at
        # small-model cost/latency) instead of the flagship reasoning model, on
        # the same AMD Instinct hardware Fireworks serves everything from.
        # Falls back to the primary provider chain above if this is unavailable.
        self._gemma_client = (
            AsyncOpenAI(api_key=config.FIREWORKS_API_KEY, base_url=config.FIREWORKS_BASE_URL)
            if config.FIREWORKS_API_KEY else None
        )
        # If the configured Gemma model isn't actually served (e.g. the default
        # name isn't provisioned on this account), the first call 404s. Latch
        # that so we stop paying a failed round-trip on EVERY subsequent
        # classification and go straight to the primary provider chain instead.
        self._gemma_dead = False

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

            # max_tokens headroom matters: gpt-oss (the benchmarked primary model,
            # see config.py) can emit a brief reasoning preamble before the JSON on
            # some queries. A too-small budget truncates the object mid-way, the
            # parse fails, and we silently default to "search" — which is exactly
            # how "add a decision…" and "what is my last mail" ended up dead in the
            # memory-search path. Normal responses use ~130 tokens; 900 is pure
            # headroom against the occasional longer one, not the common case.
            response = None
            if self._gemma_client and config.FIREWORKS_MODEL_GEMMA and not self._gemma_dead:
                try:
                    response = await self._gemma_client.chat.completions.create(
                        model=config.FIREWORKS_MODEL_GEMMA,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=900,
                    )
                    self.think("Classified via Gemma (AMD Instinct, Fireworks)")
                except Exception as gemma_err:
                    self._gemma_dead = True
                    self.observe(
                        f"Gemma classification unavailable ({str(gemma_err)[:120]}); "
                        f"using primary provider chain for the rest of this session"
                    )

            if response is None:
                response = await self._chat_completion_with_fallback(
                    client=self._client,
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=900,
                )

            raw = (response.choices[0].message.content or "").strip()
            data = _extract_json_object(raw)

            # Last-ditch salvage: if we couldn't parse a full object (e.g. the
            # response was truncated after "intent"), still pull the intent label
            # out with a narrow regex rather than blindly defaulting to search.
            if not data:
                m = re.search(r'"intent"\s*:\s*"([a-z_]+)"', raw)
                if m:
                    data = {"intent": m.group(1), "confidence": 0.6}
                else:
                    raise ValueError(f"no parseable intent JSON in model output: {raw[:160]!r}")

            intent = QueryIntent(
                intent=data.get("intent", "search"),
                confidence=data.get("confidence", 0.5),
                entities=data.get("entities", {}),
                search_strategy=data.get("search_strategy", "semantic"),
                requires_history=data.get("requires_history", False),
                rewritten_query=data.get("rewritten_query") or question,
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

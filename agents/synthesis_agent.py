"""
KAIROS Synthesis Agent — THE BRAIN.

Takes raw content (Slack, email, Drive, meetings) and extracts decisions,
or synthesizes natural-language answers using user context, ReAct reasoning,
and confidence scoring.

Now inherits from BaseAgent to participate in the advanced multi-agent system.
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Any

from openai import OpenAI, AsyncOpenAI

from config import config
from agents.base_agent import BaseAgent
from core.memory import KairosMemory
from core.graph import DecisionNode
from agents.context_agent import ResolvedContext


# ── Prompts ───────────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM = """You are KAIROS, a Company Organizational Memory system.
Your job is to capture important company moments from communications.

Extract any of the following (cast the net WIDE):
- A choice between alternatives ("we chose X over Y because...")
- An approval or sign-off ("approved to proceed with...")
- A rejection or cancellation ("decided NOT to...")
- A policy change ("going forward we will...")
- A strategic pivot or direction statement ("we are moving to X")
- A hiring, vendor, or budget decision
- A technical architecture choice
- A strategic announcement ("we are launching X in 2027")
- A company milestone, plan, or commitment ("we will expand to US")
- Any statement about what the company IS doing, WILL do, or WON'T do

IGNORE ONLY: pure greetings ("hi", "hello"), scheduling chats with no decisions,
and reactions/emoji-only messages.

Return a JSON array. Each object must have:
{
  "title": "Short title (max 10 words)",
  "summary": "1-2 sentences summarizing the decision or announcement",
  "context": "Why was this made? What problem or opportunity triggered it?",
  "alternatives": ["option A", "option B that was rejected"],
  "decision_maker": "Name of person who made/approved the decision",
  "participants": ["Person A", "Person B"],
  "date": "YYYY-MM-DD (estimate if unclear)",
  "outcome": "What was the result or next step?",
  "topics": ["topic1", "topic2"],
  "source": "slack|email|drive|meeting|jira",
  "source_url": "URL or empty string"
}

If nothing important found, return: []
Return ONLY valid JSON. No markdown, no explanation."""

SYNTHESIS_SYSTEM = """You are KAIROS, the Company Organizational Memory system.
You answer questions about a company's past decisions using the decisions retrieved from memory below.

Rules:
1. Base any claim about a company decision ONLY on the provided KAIROS Memories. Never invent or guess a decision, date, person, or outcome that isn't in the context.
2. When the memories DO cover the question: cite specific decisions as [Decision Title](source_url), say WHO decided and WHEN, and mention alternatives considered and the outcome when available. Never say "nothing found" or "no recorded decision" if the memory context below is non-empty — treat every retrieved memory as something you must acknowledge, even if it's only a partial or tangential match to the exact question asked. A question naming a specific thing ("the X project", "the auth decision") is usually about a TOPIC — if there's no exact match but the retrieved memories are related, say so explicitly ("no decision specifically about X, but here's related context I found: ...") rather than defaulting to "not found."
3. When the memories DON'T cover the question (the context below is genuinely empty or entirely unrelated): don't fake it and don't give a robotic refusal. Say plainly that you have no recorded decision on this yet, then offer a concrete next step — e.g. "I don't have a recorded decision about X. If your team discussed it in Slack, Drive, email, Jira or Zoom, connect or re-ingest that source and I'll find it." You may invite them to ask about their live connected data (files, emails, messages).
4. If the question isn't about company decisions at all (general knowledge, small talk, coding help), answer briefly and helpfully, but make clear that's general information — not from the company's memory.
5. Never tell the user to "contact the administrators" or invent fake guidance/sources.
6. Tailor tone to the user's role/background if provided.

Format: structured, professional markdown with emojis and clear sections. The renderer
only turns "## Header" into an actual heading when it starts its own line — a header
glued onto the end of a sentence renders as literal "## " text, which looks broken.
Follow this style:
- Start with a **bold one-line summary** of the answer — no separate "Summary:" label, just bold the sentence.
- Every "## Section header" MUST be on its own line, with a blank line before AND after it — never mid-paragraph or right after a period.
- Use ## Section headers with emojis for distinct topics (e.g. "## 📅 Decision Timeline", "## 👤 Key People", "## ⚠️ Risks Noted", "## 🔗 Sources")
- Use bullet lists (- item) for multiple facts; **bold** key names, dates, and decisions
- Cite sources as [Decision Title](url) — never raw URLs
- End with a "## 💡 Key Takeaway" line only if it adds something beyond the opening summary — don't repeat the same sentence twice
- Be thorough but scannable — no wall of text
"""


# ── Synthesis Agent ───────────────────────────────────────────────────────────

class SynthesisAgent(BaseAgent):
    def __init__(self, memory: KairosMemory):
        super().__init__(
            name="synthesis_agent",
            description="Synthesizes answers from retrieved organizational memory with user personalization",
            max_iterations=2,
        )
        self.memory = memory

        # Fireworks (AMD) is the primary provider; Groq + Gemini are automatic
        # fallbacks inside _chat_completion_with_fallback. See config.text_providers.
        api_key, base_url, self.model = config.primary_text()

        self._sync_client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self._async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    # ── Decision extraction (for ingestion pipeline) ──────────────────────────

    async def extract_decisions(self, content: dict, user_id: str | None = None) -> list[DecisionNode]:
        """
        Given a content dict (from any connector), extract decisions using LLM
        and store them in memory. Used in background ingestion.
        """
        text = content.get("text", "")
        if len(text.strip()) < 10:
            return []

        source_type = content.get("source", "unknown")
        source_url = content.get("source_url", "")
        content_date = content.get("date", "")

        prompt = f"""Source type: {source_type}
Date: {content_date}
<source_content>
{text[:3000]}
</source_content>

Extract all decisions from the above content."""

        try:
            response = await self._chat_completion_with_fallback(
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1200,
                fast=True,  # high-volume ingestion → cheap/fast model tier
            )

            raw = response.choices[0].message.content.strip()
            import re
            match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
            raw_json = match.group(1) if match else raw

            decisions_data = json.loads(raw_json)
            if not isinstance(decisions_data, list):
                return []

        except Exception as e:
            print(f"[Synthesis] extraction error: {e}")
            return []

        # Store each extracted decision
        stored = []
        for d in decisions_data:
            # The LLM occasionally returns a well-formed JSON array containing a
            # non-object element (e.g. a stray string). d.get(...) below would
            # raise AttributeError, which propagates uncaught out of this method —
            # the caller (orchestrator._synthesize) catches it per-batch but never
            # marks the item processed, so it gets re-sent and re-fails on every
            # future ingestion cycle instead of just being skipped once.
            if not isinstance(d, dict):
                continue
            if not d.get("title") or not d.get("summary"):
                continue

            node = DecisionNode(
                id=self.memory.make_id(title=d.get("title"), source_url=d.get("source_url", source_url), user_id=user_id),
                title=d.get("title", ""),
                summary=d.get("summary", ""),
                date=d.get("date", content_date or "unknown"),
                participants=d.get("participants", []),
                source=d.get("source", source_type),
                source_url=d.get("source_url", source_url),
                topics=d.get("topics", []),
                outcome=d.get("outcome", ""),
                raw_text=text[:2000],
                metadata={
                    "context": d.get("context", ""),
                    "alternatives": d.get("alternatives", []),
                    "decision_maker": d.get("decision_maker", ""),
                },
                user_id=user_id or "",
            )
            self.memory.store(node, user_id=user_id)
            stored.append(node)

        if stored:
            print(f"[Synthesis] Extracted {len(stored)} decisions from {source_type}")

        return stored

    def _persona_for(self, user_id: str | None) -> dict | None:
        """Fetch this user's persona override for the synthesis agent, if any."""
        if not user_id:
            return None
        try:
            from core.personas import AgentPersonaStore
            return AgentPersonaStore(db_path=self.memory.db_path).get(user_id, "synthesis_agent")
        except Exception as e:
            print(f"[Synthesis] persona lookup failed: {e}")
            return None

    # ── Query answering / ReAct execution ──────────────────────────────────────

    async def execute(self, input_data: Any, **kwargs) -> dict:
        """
        Synthesize answer for query.
        input_data: question (str)
        kwargs: resolved_context (ResolvedContext)
        """
        question = input_data if isinstance(input_data, str) else str(input_data)
        resolved_context: ResolvedContext = kwargs.get("resolved_context")
        user_id = kwargs.get("user_id")

        # 1. Retrieve decisions using hybrid search (scoped to the asking user)
        self.think("Searching KAIROS memory using hybrid vector + structured + graph retrieval")
        search_query = resolved_context.resolved_query if resolved_context else question
        relevant = self.memory.hybrid_search(search_query, n_results=6, user_id=user_id)
        self.observe(f"Retrieved {len(relevant)} relevant decisions from memory.")

        # 2. Inject user profile personalization
        personalization = ""
        if resolved_context and resolved_context.personalization_prompt:
            personalization = resolved_context.personalization_prompt
            self.think(f"Applying user personalization context: {personalization[:100]}...")

        # 3. Build prompt
        context_blocks = []
        for i, node in enumerate(relevant, 1):
            meta = node.metadata or {}
            block = f"""Decision {i}: {node.title}
ID: {node.id}
Date: {node.date}
Summary: {node.summary}
Decision Maker: {meta.get('decision_maker', 'Unknown')}
Participants: {', '.join(node.participants)}
Context: {meta.get('context', '')}
Alternatives: {', '.join(meta.get('alternatives', []))}
Outcome: {node.outcome}
Source: {node.source} — {node.source_url}
Topics: {', '.join(node.topics)}"""
            context_blocks.append(block)

        context = "\n\n---\n\n".join(context_blocks) if context_blocks else "No relevant decisions found in memory."

        prompt = f"""User Question: {search_query}

{personalization}

Relevant KAIROS Memories:
---
{context}
---

Provide your synthesis answer:"""

        self.think("Synthesizing final response based on retrieved decisions and user profile context")

        system_prompt = self.apply_persona(SYNTHESIS_SYSTEM, self._persona_for(user_id))

        stream_callback = kwargs.get("stream_callback")
        if stream_callback:
            # Run in streaming mode
            response_stream = await self._chat_completion_with_fallback(
                client=self._async_client,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
                stream=True,
            )
            answer_parts = []
            async for chunk in response_stream:
                if not chunk.choices:
                    continue
                token = chunk.choices[0].delta.content
                if token:
                    answer_parts.append(token)
                    await stream_callback({"type": "token", "content": token})
            answer = "".join(answer_parts)
        else:
            # Call LLM non-streaming
            response = await self._chat_completion_with_fallback(
                client=self._async_client,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            answer = response.choices[0].message.content
        
        # Self-reflection / evaluation
        confidence = await self.evaluate_confidence(question, {"answer": answer, "relevant_count": len(relevant)})

        return {
            "answer": answer,
            "sources": [
                {
                    "id": n.id,
                    "title": n.title,
                    "date": n.date,
                    "source": n.source,
                    "source_url": n.source_url,
                }
                for n in relevant
            ],
            "query": question,
            "confidence": confidence,
            "relevant_count": len(relevant),
        }

    async def evaluate_confidence(self, _input_data: Any, output: Any) -> float:
        """Evaluate response quality & completeness."""
        if isinstance(output, dict):
            relevant_count = output.get("relevant_count", 0)
            answer = output.get("answer", "")
            
            # Simple heuristic
            if "I do not have information" in answer or "No relevant decisions" in answer:
                return 0.2
            if relevant_count == 0:
                return 0.1
            if relevant_count >= 3 and len(answer) > 300:
                return 0.95
            return 0.75
        return 0.70

    # ── Streaming version for WebSockets ──────────────────────────────────────

    async def answer_query_stream(self, question: str, resolved_context: ResolvedContext, user_id: str | None = None) -> AsyncIterator[str]:
        """Stream answer tokens. Yields trace metadata, followed by text tokens."""
        search_query = resolved_context.resolved_query if resolved_context else question
        relevant = self.memory.hybrid_search(search_query, n_results=6, user_id=user_id)
        
        personalization = ""
        if resolved_context and resolved_context.personalization_prompt:
            personalization = resolved_context.personalization_prompt

        context_blocks = []
        for i, node in enumerate(relevant, 1):
            meta = node.metadata or {}
            block = f"""Decision {i}: {node.title}
Date: {node.date} | Source: {node.source}
Summary: {node.summary}
Decision Maker: {meta.get('decision_maker', 'Unknown')}
Outcome: {node.outcome}"""
            context_blocks.append(block)

        context = "\n\n---\n\n".join(context_blocks) if context_blocks else "No relevant decisions found."

        prompt = f"""User Question: {search_query}

{personalization}

KAIROS Memory Context:
---
{context}
---

Answer the question clearly and specifically:"""

        system_prompt = self.apply_persona(SYNTHESIS_SYSTEM, self._persona_for(user_id))

        stream = await self._chat_completion_with_fallback(
            client=self._async_client,
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            token = chunk.choices[0].delta.content
            if token:
                yield token

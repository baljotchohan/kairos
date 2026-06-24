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
Answer the user's question using ONLY the decisions provided below as context.

Rules (STRICT):
1. ONLY use information from the provided KAIROS Memories. Never invent, guess, or use outside knowledge.
2. If the memories don't contain a relevant answer, say exactly: "KAIROS has no recorded decision on this topic yet."
3. Cite specific decisions with [Decision Title](source_url) when possible.
4. Include WHO made the decision and WHEN.
5. Mention alternatives considered and outcomes if available.
6. Tailor your answer to the user's role/background if provided.

Format: clear, professional markdown. Be concise — one or two paragraphs max unless detail is explicitly needed.
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
        
        # Use Groq for text completions, fallback to Fireworks if not set
        api_key = config.GROQ_API_KEY or config.FIREWORKS_API_KEY
        base_url = config.GROQ_BASE_URL if config.GROQ_API_KEY else config.FIREWORKS_BASE_URL
        self.model = config.GROQ_MODEL if config.GROQ_API_KEY else config.FIREWORKS_MODEL
        
        self._sync_client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self._async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    # ── Decision extraction (for ingestion pipeline) ──────────────────────────

    async def extract_decisions(self, content: dict) -> list[DecisionNode]:
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
{text[:6000]}
</source_content>

Extract all decisions from the above content."""

        try:
            response = await self._chat_completion_with_fallback(
                client=self._async_client,
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            raw = response.choices[0].message.content.strip()
            import re
            match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
            raw_json = match.group(1) if match else raw

            decisions_data = json.loads(raw_json)
            if not isinstance(decisions_data, list):
                return []

        except (json.JSONDecodeError, Exception) as e:
            print(f"[Synthesis] extraction error: {e}")
            return []

        # Store each extracted decision
        stored = []
        for d in decisions_data:
            if not d.get("title") or not d.get("summary"):
                continue

            node = DecisionNode(
                id=self.memory.make_id(title=d.get("title"), source_url=d.get("source_url", source_url)),
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
            )
            self.memory.store(node)
            stored.append(node)

        if stored:
            print(f"[Synthesis] Extracted {len(stored)} decisions from {source_type}")

        return stored

    # ── Query answering / ReAct execution ──────────────────────────────────────

    async def execute(self, input_data: Any, **kwargs) -> dict:
        """
        Synthesize answer for query.
        input_data: question (str)
        kwargs: resolved_context (ResolvedContext)
        """
        question = input_data if isinstance(input_data, str) else str(input_data)
        resolved_context: ResolvedContext = kwargs.get("resolved_context")
        
        # 1. Retrieve decisions using hybrid search
        self.think("Searching KAIROS memory using hybrid vector + structured + graph retrieval")
        search_query = resolved_context.resolved_query if resolved_context else question
        relevant = self.memory.hybrid_search(search_query, n_results=6)
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

        stream_callback = kwargs.get("stream_callback")
        if stream_callback:
            # Run in streaming mode
            response_stream = await self._chat_completion_with_fallback(
                client=self._async_client,
                model=self.model,
                messages=[
                    {"role": "system", "content": SYNTHESIS_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
                stream=True,
            )
            answer_parts = []
            async for chunk in response_stream:
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
                    {"role": "system", "content": SYNTHESIS_SYSTEM},
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

    async def answer_query_stream(self, question: str, resolved_context: ResolvedContext) -> AsyncIterator[str]:
        """Stream answer tokens. Yields trace metadata, followed by text tokens."""
        search_query = resolved_context.resolved_query if resolved_context else question
        relevant = self.memory.hybrid_search(search_query, n_results=6)
        
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

        stream = await self._chat_completion_with_fallback(
            client=self._async_client,
            model=self.model,
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
            stream=True,
        )

        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

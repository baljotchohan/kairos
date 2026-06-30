"""
KAIROS Orchestrator — Coordinates ingestion and query pipelines.

Ingestion Flow (LangGraph):
  [Slack Agent]  ──┐
  [Email Agent]  ──┤
  [Drive Agent]  ──┼──► [Jira Connector] ──► [Synthesis Agent] ──► [Memory Store]
  [Meeting Agent]──┘

Query Flow (Multi-Agent System):
  [User Query] ──► [Intent Agent] ──► [Context Agent] ──► [Research/Synthesis Agent]
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Callable, TypedDict, Awaitable

log = logging.getLogger(__name__)

from langgraph.graph import StateGraph, END

from config import config

from agents.context_agent import ResolvedContext
from core.memory import KairosMemory
from core.user_memory import UserMemory


# ── Pipeline State ────────────────────────────────────────────────────────────

class KairosState(TypedDict):
    user_id: str
    slack_data: list[dict]
    email_data: list[dict]
    drive_data: list[dict]
    meeting_data: list[dict]
    jira_data: list[dict]
    decisions_extracted: int
    errors: list[str]
    status: str


# ── Orchestrator ──────────────────────────────────────────────────────────────

class KairosOrchestrator:
    """
    Coordinates KAIROS agents for both background ingestion (via LangGraph)
    and user-aware query answering (via Multi-Agent Pipeline).
    """

    def __init__(self, memory: KairosMemory):
        self.memory = memory
        self.user_memory = UserMemory(db_path=memory.db_path)
        self.ingestion_locks = {}

        # Lazy imports to avoid circular dependencies
        from agents.slack_agent import SlackAgent
        from agents.email_agent import EmailAgent
        from agents.drive_agent import DriveAgent
        from agents.meeting_agent import MeetingAgent
        from agents.synthesis_agent import SynthesisAgent
        from agents.intent_agent import IntentAgent
        from agents.context_agent import ContextAgent
        from agents.research_agent import ResearchAgent
        from agents.live_data_agent import LiveDataAgent
        from connectors.jira_connector import JiraConnector

        # Ingestion agents & connectors
        self.slack_agent = SlackAgent()
        self.email_agent = EmailAgent()
        self.drive_agent = DriveAgent()
        self.meeting_agent = MeetingAgent()
        self.jira_connector = JiraConnector()
        self.synthesis_agent = SynthesisAgent(memory=memory)

        # Query agents
        self.intent_agent = IntentAgent()
        self.context_agent = ContextAgent(user_memory=self.user_memory)
        self.research_agent = ResearchAgent(memory=memory)
        # Live data agent — queries the user's connected sources on-demand
        self.live_data_agent = LiveDataAgent(memory=memory)

        # Lightweight LLM client for conversational (greeting/small-talk) replies.
        # Fireworks (AMD) primary; Groq + Gemini auto-fallback. See config.text_providers.
        from openai import AsyncOpenAI
        _api_key, _base_url, self._chat_model = config.primary_text()
        self._chat_client = AsyncOpenAI(api_key=_api_key, base_url=_base_url)

        self._graph = self._build_graph()

    # ── Ingestion Graph construction ───────────────────────────────────────────

    def _build_graph(self):
        g = StateGraph(KairosState)

        g.add_node("gather_slack", self._gather_slack)
        g.add_node("gather_email", self._gather_email)
        g.add_node("gather_drive", self._gather_drive)
        g.add_node("gather_meetings", self._gather_meetings)
        g.add_node("gather_jira", self._gather_jira)
        g.add_node("synthesize", self._synthesize)

        g.set_entry_point("gather_slack")
        g.add_edge("gather_slack", "gather_email")
        g.add_edge("gather_email", "gather_drive")
        g.add_edge("gather_drive", "gather_meetings")
        g.add_edge("gather_meetings", "gather_jira")
        g.add_edge("gather_jira", "synthesize")
        g.add_edge("synthesize", END)

        return g.compile()

    # ── Node implementations ───────────────────────────────────────────────────

    async def _gather_slack(self, state: KairosState) -> dict:
        try:
            data = await self.slack_agent.fetch(user_id=state.get("user_id"))
            return {"slack_data": data, "status": "slack_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Slack: {e}"]
            return {"slack_data": [], "errors": errs}

    async def _gather_email(self, state: KairosState) -> dict:
        try:
            data = await self.email_agent.fetch(user_id=state.get("user_id"))
            return {"email_data": data, "status": "email_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Gmail: {e}"]
            return {"email_data": [], "errors": errs}

    async def _gather_drive(self, state: KairosState) -> dict:
        try:
            data = await self.drive_agent.fetch(user_id=state.get("user_id"))
            return {"drive_data": data, "status": "drive_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Drive: {e}"]
            return {"drive_data": [], "errors": errs}

    async def _gather_meetings(self, state: KairosState) -> dict:
        try:
            data = await self.meeting_agent.fetch(user_id=state.get("user_id"))
            return {"meeting_data": data, "status": "meetings_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Meetings: {e}"]
            return {"meeting_data": [], "errors": errs}

    async def _gather_jira(self, state: KairosState) -> dict:
        # Jira creds are global env (no per-user OAuth yet) — only ingest the
        # deployer's Jira for the authorized owner uid, never for other users.
        if state.get("user_id") != config.JIRA_OWNER_UID:
            return {"jira_data": [], "status": "jira_skipped"}
        try:
            issues = await self.jira_connector.get_recent_issues(days_back=30)
            data = []
            for issue in issues:
                data.append({
                    "id": issue["key"],
                    "title": issue["summary"],
                    "content": f"Description: {issue['description']}\nComments:\n" + "\n".join(issue["comments"]),
                    "url": issue["source_url"],
                    "date": issue["updated"],
                    "source": f"Jira {issue['key']}",
                })
            return {"jira_data": data, "status": "jira_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Jira: {e}"]
            return {"jira_data": [], "errors": errs}

    @staticmethod
    def _inv_row(item: dict, default_source: str, kind: str) -> dict:
        """Normalize a connector-data item into an inventory row. Handles both the
        {id,title,content,url} shape (drive/meeting/jira) and the {text,source_url}
        shape (slack/email)."""
        item_id = str(item.get("id") or item.get("source_url") or item.get("url") or "")
        title = item.get("title") or (item.get("text", "") or "")[:80] or default_source
        url = item.get("url") or item.get("source_url") or ""
        snippet = (item.get("content") or item.get("text") or "")[:300]
        return {
            "source": item.get("source", default_source),
            "item_id": item_id,
            "title": title,
            "url": url,
            "date": item.get("date", ""),
            "kind": kind,
            "snippet": snippet,
        }

    async def _synthesize(self, state: KairosState) -> dict:
        # Interleave sources (round-robin) so a capped cycle samples across
        # Slack/email/drive/meeting/jira instead of burning the whole budget on
        # the first source (e.g. casual Slack messages) and never reaching the
        # decision-rich ones (Jira tickets, email approvals).
        sources = [
            state.get("jira_data", []),     # tickets/epics — richest in decisions
            state.get("email_data", []),    # approvals/threads
            state.get("drive_data", []),    # docs/specs
            state.get("meeting_data", []),  # transcripts
            state.get("slack_data", []),    # chat — often casual
        ]
        all_batches = []
        from itertools import zip_longest
        for group in zip_longest(*sources):
            for item in group:
                if item is not None:
                    all_batches.append(item)

        # Cap items per cycle to respect the LLM provider's token-per-minute
        # limit (Groq free tier is 6000 TPM). Successive cycles filter out
        # previously processed items, progressively working through the backlog.
        import asyncio
        max_per_cycle = config.MAX_EXTRACT_PER_CYCLE
        user_id = state.get("user_id")

        processed_ids = self.memory.get_processed_item_ids(user_id) if user_id else set()
        unprocessed_batches = []
        for item in all_batches:
            item_id = self._get_item_id(item)
            if item_id and item_id not in processed_ids:
                unprocessed_batches.append(item)
            elif not item_id:
                unprocessed_batches.append(item)

        batches = unprocessed_batches[:max_per_cycle]

        count = 0
        errors = list(state.get("errors", []))

        # Snapshot ALL fetched items (not just the capped extraction batch) into the
        # per-user inventory cache. No LLM — just metadata — so the LiveDataAgent can
        # answer "what do I have" instantly/offline. Never blocks ingestion.
        try:
            inv: list[dict] = []
            for items, src, kind in (
                (state.get("jira_data", []), "Jira", "issue"),
                (state.get("email_data", []), "Email", "email"),
                (state.get("drive_data", []), "Google Drive", "file"),
                (state.get("meeting_data", []), "Zoom", "recording"),
                (state.get("slack_data", []), "Slack", "message"),
            ):
                inv.extend(self._inv_row(it, src, kind) for it in items)
            if user_id and inv:
                self.memory.store_inventory(user_id, inv)
        except Exception as e:
            print(f"[Ingestion] inventory snapshot error: {e}")

        processed_item_ids = []
        for i, batch in enumerate(batches):
            try:
                extracted = await self.synthesis_agent.extract_decisions(batch, user_id=user_id)
                count += len(extracted)
                batch_id = self._get_item_id(batch)
                if batch_id:
                    processed_item_ids.append(batch_id)
            except Exception as e:
                errors.append(f"Synthesis: {e}")
            # Small spacing between calls to smooth out token-per-minute bursts.
            if i < len(batches) - 1:
                await asyncio.sleep(config.EXTRACT_DELAY_SECONDS)

        if user_id and processed_item_ids:
            self.memory.mark_items_as_processed(user_id, processed_item_ids)

        print(f"[Ingestion] Synthesize complete — {count} decisions from {len(batches)}/{len(unprocessed_batches)} unprocessed items (out of {len(all_batches)} total)")
        return {"decisions_extracted": count, "errors": errors, "status": "complete"}

    @staticmethod
    def _get_item_id(item: dict) -> str:
        """Helper to extract unique item ID from raw connector data."""
        return str(item.get("id") or item.get("source_url") or item.get("url") or "")

    # ── Ingestion API ──────────────────────────────────────────────────────────

    async def run_ingestion(
        self,
        user_id: str,
        progress_callback: Callable[[str], Awaitable[None]] | None = None
    ) -> dict:
        """Full ingestion run. Serialized via Lock to prevent race conditions."""
        lock = self.ingestion_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            if progress_callback:
                await progress_callback("🚀 KAIROS ingestion started...")

            initial: KairosState = {
                "user_id": user_id,
                "slack_data": [],
                "email_data": [],
                "drive_data": [],
                "meeting_data": [],
                "jira_data": [],
                "decisions_extracted": 0,
                "errors": [],
                "status": "starting",
            }

            # Offload graph execution to event loop
            result = await self._graph.ainvoke(initial)

            if progress_callback:
                n = result.get("decisions_extracted", 0)
                errs = result.get("errors", [])
                await progress_callback(
                    f"✅ Done. {n} decisions extracted."
                    + (f" Errors: {errs}" if errs else "")
                )

            return result

    # ── User-Aware Query Pipeline ──────────────────────────────────────────────

    async def query_with_memory(
        self,
        question: str,
        user_id: str,
        session_id: str | None = None,
        stream_callback: Callable[[dict], Awaitable[None]] | None = None
    ) -> dict:
        """
        Runs the full multi-agent query answering pipeline:
          1. Retrieve/create conversation session (bypasses idle resumption on New Chat)
          2. Classify intent (IntentAgent)
          3. Enrich query and resolve references (ContextAgent)
          4. Execute answering agent (ResearchAgent for deep dive, SynthesisAgent for standard summary)
          5. Save conversation turn to UserMemory
        """
        # If session_id is missing, generate a brand new session ID (fixes New Chat bug)
        if not session_id:
            session_id = f"session-{uuid.uuid4().hex[:12]}"
        
        # Verify/ensure the session exists in SQLite
        session_id = await asyncio.to_thread(self.user_memory.get_or_create_session, user_id, session_id)

        # Per-request agent instances. The query agents hold per-user mutable state
        # (_current_user_id, _connectors, _collected_sources, _trace), so a single
        # shared instance would interleave/leak state across concurrent users.
        # Constructors only build an AsyncOpenAI client + config, so this is cheap.
        from agents.intent_agent import IntentAgent
        from agents.context_agent import ContextAgent
        from agents.research_agent import ResearchAgent
        from agents.synthesis_agent import SynthesisAgent
        from agents.live_data_agent import LiveDataAgent
        intent_agent = IntentAgent()
        context_agent = ContextAgent(user_memory=self.user_memory)
        research_agent = ResearchAgent(memory=self.memory)
        synthesis_agent = SynthesisAgent(memory=self.memory)
        live_data_agent = LiveDataAgent(memory=self.memory)

        # 1. Intent Classification
        if stream_callback:
            await stream_callback({"type": "thinking", "agent": "intent_agent", "step": "think", "content": "Analyzing query intent..."})

        history = await asyncio.to_thread(self.user_memory.get_current_session_context, user_id, max_turns=6, session_id=session_id)
        intent = await intent_agent.classify(question, conversation_history=history)

        if stream_callback:
            await stream_callback({
                "type": "agent_trace",
                "agent": "intent_agent",
                "trace": [step.to_dict() for step in intent_agent.get_trace()]
            })

        # 2. Context Resolution
        if stream_callback:
            await stream_callback({"type": "thinking", "agent": "context_agent", "step": "think", "content": "Resolving pronouns and personal profile context..."})

        resolved_context = await context_agent.resolve(question, user_id=user_id, intent=intent, session_id=session_id)

        if stream_callback:
            await stream_callback({
                "type": "agent_trace",
                "agent": "context_agent",
                "trace": [step.to_dict() for step in context_agent.get_trace()]
            })

        # 3. Choose agent & Execute Answering
        merged_traces = []
        merged_traces.extend(intent_agent.get_trace())
        merged_traces.extend(context_agent.get_trace())

        # 3a. Greeting / small-talk → reply conversationally, skip memory search
        if intent.intent == "greeting":
            answer = await self._conversational_reply(question, history, stream_callback)
            await asyncio.to_thread(
                self.user_memory.store_message,
                user_id=user_id, session_id=session_id,
                role="user", content=question, query_intent=intent.intent,
            )
            await asyncio.to_thread(
                self.user_memory.store_message,
                user_id=user_id, session_id=session_id,
                role="assistant", content=answer, query_intent=intent.intent,
                metadata={"sources": [], "confidence": 1.0},
            )
            return {
                "answer": answer, "sources": [], "intent": intent.to_dict(),
                "confidence": 1.0, "traces": [s.to_dict() for s in merged_traces],
                "session_id": session_id, "user_context": resolved_context.to_dict(),
            }

        # 3b. Live data → query the user's connected sources on-demand (Drive/Gmail/Slack/Jira/Zoom)
        if intent.intent == "live_data":
            if stream_callback:
                await stream_callback({"type": "thinking", "agent": "live_data_agent", "step": "think", "content": "Checking your connected sources live..."})

            result = await live_data_agent.run(
                resolved_context.resolved_query, user_id=user_id, stream_callback=stream_callback
            )
            merged_traces.extend(live_data_agent.get_trace())

            if stream_callback:
                await stream_callback({
                    "type": "agent_trace",
                    "agent": "live_data_agent",
                    "trace": [step.to_dict() for step in live_data_agent.get_trace()]
                })

            if not result.success:
                log.error("Live Data Agent failed: %s", result.error)
                raise ValueError("Live data lookup could not be completed. Please check your connected sources.")

            answer = result.output.get("answer", "")
            sources = result.output.get("sources", [])
            confidence = result.confidence

        # If it is comparison, timeline, person lookup or user asks for a deep dive, run ResearchAgent
        elif intent.intent in ("comparison", "timeline", "person_lookup", "what_if"):
            if stream_callback:
                await stream_callback({"type": "thinking", "agent": "research_agent", "step": "think", "content": "Running deep multi-step research on KAIROS graph..."})
            
            result = await research_agent.run(resolved_context.resolved_query, user_id=user_id, stream_callback=stream_callback)
            merged_traces.extend(research_agent.get_trace())

            if stream_callback:
                await stream_callback({
                    "type": "agent_trace",
                    "agent": "research_agent",
                    "trace": [step.to_dict() for step in research_agent.get_trace()]
                })
            
            if not result.success:
                log.error("Research Agent failed: %s", result.error)
                raise ValueError("Deep research could not be completed. Please try rephrasing your question.")
            
            answer = result.output.get("answer", "")
            sources = result.output.get("sources", [])
            confidence = result.confidence
        else:
            if stream_callback:
                await stream_callback({"type": "thinking", "agent": "synthesis_agent", "step": "think", "content": "Synthesizing response from relevant company memories..."})
            
            result = await synthesis_agent.run(question, resolved_context=resolved_context, user_id=user_id, stream_callback=stream_callback)
            merged_traces.extend(synthesis_agent.get_trace())

            if stream_callback:
                await stream_callback({
                    "type": "agent_trace",
                    "agent": "synthesis_agent",
                    "trace": [step.to_dict() for step in synthesis_agent.get_trace()]
                })
                
            if not result.success:
                log.error("Synthesis Agent failed: %s", result.error)
                raise ValueError("Could not generate an answer right now. Please try again in a moment.")
                
            answer = result.output.get("answer", "")
            sources = result.output.get("sources", [])
            confidence = result.confidence

        # 4. Save to User Memory
        # Store user question
        await asyncio.to_thread(
            self.user_memory.store_message,
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=question,
            query_intent=intent.intent
        )
        
        # Store assistant response
        await asyncio.to_thread(
            self.user_memory.store_message,
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=answer,
            query_intent=intent.intent,
            metadata={
                "sources": sources,
                "confidence": confidence,
                "requires_history": intent.requires_history
            }
        )

        # Triggers profile preference summary update asynchronously every 5 queries
        profile = await asyncio.to_thread(self.user_memory.get_profile, user_id)
        if profile.total_queries > 0 and profile.total_queries % 5 == 0:
            asyncio.create_task(self._trigger_profile_update(user_id))

        # Also store the Q&A exchange as a DecisionNode so it is searchable via
        # MCP get_context (which queries the decision graph, not UserMemory sessions).
        # This ensures Claude/ChatGPT can find past KAIROS conversations.
        if answer and intent.intent not in ("greeting",):
            try:
                from core.graph import DecisionNode
                from datetime import datetime as _dt
                qa_node = DecisionNode(
                    id=self.memory.make_id(
                        title=question[:100],
                        source_url=f"kairos://session/{session_id}",
                        user_id=user_id,
                    ),
                    title=question[:200],
                    summary=f"Q: {question[:300]}\nA: {answer[:300]}",
                    date=_dt.utcnow().strftime("%Y-%m-%d"),
                    source="KAIROS Chat",
                    source_url=f"kairos://session/{session_id}",
                    participants=[],
                    topics=["KAIROS Conversation", intent.intent],
                    outcome=answer[:500],
                    raw_text=f"Question: {question}\n\nAnswer: {answer}",
                    metadata={"session_id": session_id, "intent": intent.intent, "confidence": confidence},
                    user_id=user_id,
                )
                await asyncio.to_thread(self.memory.store, qa_node, user_id)
            except Exception as _e:
                log.warning("Failed to index Q&A to decision graph: %s", _e)

        return {
            "answer": answer,
            "sources": sources,
            "intent": intent.to_dict(),
            "confidence": confidence,
            "traces": [step.to_dict() for step in merged_traces],
            "session_id": session_id,
            "user_context": resolved_context.to_dict()
        }

    async def _conversational_reply(
        self,
        question: str,
        history: list,
        stream_callback=None,
    ) -> str:
        """Generate a natural, on-brand reply for greetings / small talk and
        stream it token-by-token. No memory search — avoids the robotic
        'no recorded decision' message for casual chat."""
        system = (
            "You are KAIROS, a Company Organizational Memory AI. You connect to a "
            "company's Slack, Gmail, Drive, Jira and Zoom, extract every decision and "
            "its context, and let people ask why past decisions were made. "
            "Right now the user is making small talk or greeting you — reply warmly, "
            "briefly (1-3 sentences), in a confident, friendly tone. Do NOT say you "
            "have no records. Invite them to ask about a past decision, and give one "
            "concrete example they could ask (e.g. 'Why did we choose this vendor?')."
        )
        msgs = [{"role": "system", "content": system}]
        for m in (history or [])[-4:]:
            role = m.get("role", "user")
            if role in ("user", "assistant"):
                msgs.append({"role": role, "content": str(m.get("content", ""))[:500]})
        msgs.append({"role": "user", "content": question})

        # Try each configured provider in order (Fireworks → Groq → Gemini) so a
        # greeting doesn't fail just because the primary provider is down — matching
        # the multi-provider fallback the agents use.
        from openai import AsyncOpenAI
        for name, api_key, base_url, model in config.text_providers():
            answer = ""
            emitted = False
            try:
                client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                stream = await client.chat.completions.create(
                    model=model, messages=msgs,
                    temperature=0.6, max_tokens=200, stream=True,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    token = chunk.choices[0].delta.content
                    if token:
                        answer += token
                        emitted = True
                        if stream_callback:
                            await stream_callback({"type": "token", "content": token})
                if answer.strip():
                    return answer.strip()
            except Exception as e:
                print(f"[Orchestrator] greeting provider {name} failed: {e}")
                # If we already streamed partial tokens, don't retry (would duplicate
                # output to the client) — return what we have.
                if emitted and answer.strip():
                    return answer.strip()
                continue

        # All providers failed → graceful canned reply.
        fallback = (
            "Hi! I'm KAIROS — your company's organizational memory. Ask me why a "
            "past decision was made, e.g. \"Why did we choose this vendor?\""
        )
        if stream_callback:
            await stream_callback({"type": "token", "content": fallback})
        return fallback

    async def _trigger_profile_update(self, user_id: str):
        """Asynchronously triggers LLM summary update on user profile context."""
        try:
            history = await asyncio.to_thread(self.user_memory.get_recent_history, user_id, limit=15)
            if not history:
                return

            history_text = "\n".join([
                f"{h.role.upper()}: {h.content}" for h in history if h.role == "user"
            ])

            prompt = f"""You are KAIROS personalization engine. Analyze this user's query history.
Determine:
1. What department they likely work in (Engineering, Product, Operations, HR, Sales, Legal)
2. What topics they care about most (e.g. databases, hiring, contracts, React, deployments)
3. Write a 1-sentence role context summary (e.g., "Engineering lead focused on infrastructure decisions")

Return JSON only:
{{
  "department": "Engineering",
  "frequent_topics": ["databases", "CI/CD"],
  "role_context": "Engineering lead focused on infrastructure decisions"
}}

User History:
{history_text}"""

            # Fireworks (AMD) primary; Groq + Gemini auto-fallback. See config.text_providers.
            api_key, base_url, model = config.primary_text(fast=True)

            # We create a client locally to avoid circular dependencies
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            data = json.loads(raw)
            
            department = data.get("department", "")
            frequent_topics = data.get("frequent_topics", [])
            role_context = data.get("role_context", "")
            
            # Use surgical target update instead of save_profile to prevent overwriting stats
            await asyncio.to_thread(
                self.user_memory.update_learned_profile,
                user_id=user_id,
                department=department,
                frequent_topics=frequent_topics,
                role_context=role_context
            )
            print(f"[Orchestrator] Updated learned profile context for user {user_id}")
        except Exception as e:
            print(f"[Orchestrator] Profile learn error: {e}")

    # ── Backward compatibility ────────────────────────────────────────────────

    async def query(self, question: str, user_id: str = "anonymous", **kwargs) -> dict:
        """Fallback to user context querying."""
        session_id = kwargs.get("session_id")
        return await self.query_with_memory(question, user_id=user_id, session_id=session_id)

    async def query_stream(self, question: str, user_id: str = "anonymous", **kwargs):
        """Streams using synthesis agent with default user context."""
        session_id = kwargs.get("session_id") or "anonymous-session"
        await asyncio.to_thread(self.user_memory.get_or_create_session, user_id, session_id)
        resolved_context = ResolvedContext(
            original_query=question,
            resolved_query=question,
            intent=await self.intent_agent.classify(question)
        )
        async for token in self.synthesis_agent.answer_query_stream(question, resolved_context):
            yield token

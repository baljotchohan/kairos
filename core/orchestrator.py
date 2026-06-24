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
import uuid
from typing import Callable, TypedDict, Awaitable

from langgraph.graph import StateGraph, END

from config import config

from agents.context_agent import ResolvedContext
from core.memory import KairosMemory
from core.user_memory import UserMemory


# ── Pipeline State ────────────────────────────────────────────────────────────

class KairosState(TypedDict):
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
        self.ingestion_lock = asyncio.Lock()

        # Lazy imports to avoid circular dependencies
        from agents.slack_agent import SlackAgent
        from agents.email_agent import EmailAgent
        from agents.drive_agent import DriveAgent
        from agents.meeting_agent import MeetingAgent
        from agents.synthesis_agent import SynthesisAgent
        from agents.intent_agent import IntentAgent
        from agents.context_agent import ContextAgent
        from agents.research_agent import ResearchAgent
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
            data = await self.slack_agent.fetch()
            return {"slack_data": data, "status": "slack_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Slack: {e}"]
            return {"slack_data": [], "errors": errs}

    async def _gather_email(self, state: KairosState) -> dict:
        try:
            data = await self.email_agent.fetch()
            return {"email_data": data, "status": "email_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Gmail: {e}"]
            return {"email_data": [], "errors": errs}

    async def _gather_drive(self, state: KairosState) -> dict:
        try:
            data = await self.drive_agent.fetch()
            return {"drive_data": data, "status": "drive_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Drive: {e}"]
            return {"drive_data": [], "errors": errs}

    async def _gather_meetings(self, state: KairosState) -> dict:
        try:
            data = await self.meeting_agent.fetch()
            return {"meeting_data": data, "status": "meetings_done"}
        except Exception as e:
            errs = state.get("errors", []) + [f"Meetings: {e}"]
            return {"meeting_data": [], "errors": errs}

    async def _gather_jira(self, state: KairosState) -> dict:
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

    async def _synthesize(self, state: KairosState) -> dict:
        all_batches = (
            state.get("slack_data", [])
            + state.get("email_data", [])
            + state.get("drive_data", [])
            + state.get("meeting_data", [])
            + state.get("jira_data", [])
        )

        count = 0
        errors = list(state.get("errors", []))

        for batch in all_batches:
            try:
                extracted = await self.synthesis_agent.extract_decisions(batch)
                count += len(extracted)
            except Exception as e:
                errors.append(f"Synthesis: {e}")

        return {"decisions_extracted": count, "errors": errors, "status": "complete"}

    # ── Ingestion API ──────────────────────────────────────────────────────────

    async def run_ingestion(
        self,
        progress_callback: Callable[[str], Awaitable[None]] | None = None
    ) -> dict:
        """Full ingestion run. Serialized via Lock to prevent race conditions."""
        async with self.ingestion_lock:
            if progress_callback:
                await progress_callback("🚀 KAIROS ingestion started...")

            initial: KairosState = {
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
        
        # 1. Intent Classification
        if stream_callback:
            await stream_callback({"type": "thinking", "agent": "intent_agent", "step": "think", "content": "Analyzing query intent..."})
            
        history = await asyncio.to_thread(self.user_memory.get_current_session_context, user_id, max_turns=6, session_id=session_id)
        intent = await self.intent_agent.classify(question, conversation_history=history)
        
        if stream_callback:
            await stream_callback({
                "type": "agent_trace",
                "agent": "intent_agent",
                "trace": [step.to_dict() for step in self.intent_agent.get_trace()]
            })

        # 2. Context Resolution
        if stream_callback:
            await stream_callback({"type": "thinking", "agent": "context_agent", "step": "think", "content": "Resolving pronouns and personal profile context..."})
            
        resolved_context = await self.context_agent.resolve(question, user_id=user_id, intent=intent)
        
        if stream_callback:
            await stream_callback({
                "type": "agent_trace",
                "agent": "context_agent",
                "trace": [step.to_dict() for step in self.context_agent.get_trace()]
            })

        # 3. Choose agent & Execute Answering
        merged_traces = []
        merged_traces.extend(self.intent_agent.get_trace())
        merged_traces.extend(self.context_agent.get_trace())

        # If it is comparison, timeline, person lookup or user asks for a deep dive, run ResearchAgent
        is_research = intent.intent in ("comparison", "timeline", "person_lookup", "what_if")
        
        if is_research:
            if stream_callback:
                await stream_callback({"type": "thinking", "agent": "research_agent", "step": "think", "content": "Running deep multi-step research on KAIROS graph..."})
            
            result = await self.research_agent.run(resolved_context.resolved_query)
            merged_traces.extend(self.research_agent.get_trace())
            
            if stream_callback:
                await stream_callback({
                    "type": "agent_trace",
                    "agent": "research_agent",
                    "trace": [step.to_dict() for step in self.research_agent.get_trace()]
                })
            
            if not result.success:
                raise ValueError(f"Research Agent failed: {result.error}")
            
            answer = result.output.get("answer", "")
            sources = result.output.get("sources", [])
            confidence = result.confidence
        else:
            if stream_callback:
                await stream_callback({"type": "thinking", "agent": "synthesis_agent", "step": "think", "content": "Synthesizing response from relevant company memories..."})
            
            result = await self.synthesis_agent.run(question, resolved_context=resolved_context)
            merged_traces.extend(self.synthesis_agent.get_trace())
            
            if stream_callback:
                await stream_callback({
                    "type": "agent_trace",
                    "agent": "synthesis_agent",
                    "trace": [step.to_dict() for step in self.synthesis_agent.get_trace()]
                })
                
            if not result.success:
                raise ValueError(f"Synthesis Agent failed: {result.error}")
                
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

        return {
            "answer": answer,
            "sources": sources,
            "intent": intent.to_dict(),
            "confidence": confidence,
            "traces": [step.to_dict() for step in merged_traces],
            "session_id": session_id,
            "user_context": resolved_context.to_dict()
        }

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

            api_key = config.GROQ_API_KEY or config.FIREWORKS_API_KEY
            base_url = config.GROQ_BASE_URL if config.GROQ_API_KEY else config.FIREWORKS_BASE_URL
            model = config.GROQ_MODEL if config.GROQ_API_KEY else config.FIREWORKS_MODEL

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

    async def query(self, question: str) -> dict:
        """Fallback to anonymous user context querying."""
        return await self.query_with_memory(question, user_id="anonymous")

    async def query_stream(self, question: str):
        """Streams using synthesis agent with default anonymous context."""
        await asyncio.to_thread(self.user_memory.get_or_create_session, "anonymous")
        resolved_context = ResolvedContext(
            original_query=question,
            resolved_query=question,
            intent=await self.intent_agent.classify(question)
        )
        async for token in self.synthesis_agent.answer_query_stream(question, resolved_context):
            yield token

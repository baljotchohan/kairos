"""
KAIROS Research Agent — Deep-dive multi-step search and fact verification.

Inherits from BaseAgent and uses a ReAct reasoning loop to search across:
  - Vector similarity (ChromaDB)
  - Structured queries (SQLite)
  - Relationships (Decision Graph)

Can run multiple search steps to resolve complex/multi-hop queries
(e.g., "Find the database decision, then see who approved the follow-up migration").
"""

from __future__ import annotations

import json
import re
import asyncio
from typing import Any, Optional

from openai import AsyncOpenAI

from config import config
from agents.base_agent import BaseAgent, AgentTool, AgentResult
from core.memory import KairosMemory
from core.graph import DecisionNode


class ResearchAgent(BaseAgent):
    """
    Advanced agent that performs multi-hop research, semantic searches,
    structured filter searches, and graph navigation to resolve complex questions.
    """

    def __init__(self, memory: KairosMemory):
        super().__init__(
            name="research_agent",
            description="Performs multi-step research and graph navigation across KAIROS memories",
            max_iterations=5,
        )
        self.memory = memory
        # Set per-run so the fixed-signature tool handlers can scope to the user.
        self._current_user_id: Optional[str] = None

        # LLM client setup
        api_key = config.GROQ_API_KEY or config.FIREWORKS_API_KEY
        base_url = config.GROQ_BASE_URL if config.GROQ_API_KEY else config.FIREWORKS_BASE_URL
        self.model = config.GROQ_MODEL if config.GROQ_API_KEY else config.FIREWORKS_MODEL

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _register_tools(self):
        """Register memory search tools."""
        self.register_tool(AgentTool(
            name="semantic_search",
            description="Find decisions using natural language similarity. Input: 'query' (str), optional 'limit' (int).",
            handler=self._tool_semantic_search,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "limit": {"type": "integer", "description": "Max results to return (default 5)"}
                },
                "required": ["query"]
            }
        ))

        self.register_tool(AgentTool(
            name="structured_search",
            description="Find decisions with SQL filters. Input: 'topic' (str), 'person' (str), 'date_from' (str YYYY-MM-DD), 'date_to' (str YYYY-MM-DD).",
            handler=self._tool_structured_search,
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "person": {"type": "string"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"}
                }
            }
        ))

        self.register_tool(AgentTool(
            name="get_connected_decisions",
            description="Get decisions related/linked to a given decision ID. Input: 'decision_id' (str), 'depth' (int, default 1).",
            handler=self._tool_get_connected_decisions,
            parameters={
                "type": "object",
                "properties": {
                    "decision_id": {"type": "string"},
                    "depth": {"type": "integer"}
                },
                "required": ["decision_id"]
            }
        ))

        self.register_tool(AgentTool(
            name="get_decision_details",
            description="Retrieve full details for a decision by its ID. Input: 'decision_id' (str).",
            handler=self._tool_get_decision_details,
            parameters={
                "type": "object",
                "properties": {
                    "decision_id": {"type": "string"}
                },
                "required": ["decision_id"]
            }
        ))

    # ── Tool Handlers ─────────────────────────────────────────────────────────

    async def _tool_semantic_search(self, query: str, limit: int = 5) -> list[dict]:
        nodes = self.memory.semantic_search(query, n_results=limit, user_id=self._current_user_id)
        return [self._node_to_dict(n) for n in nodes]

    async def _tool_structured_search(
        self,
        topic: str = None,
        person: str = None,
        date_from: str = None,
        date_to: str = None,
    ) -> list[dict]:
        if not any([topic, person, date_from, date_to]):
            return []
        nodes = self.memory.structured_search(
            topic=topic, person=person, date_from=date_from, date_to=date_to,
            user_id=self._current_user_id,
        )
        return [self._node_to_dict(n) for n in nodes]

    async def _tool_get_connected_decisions(self, decision_id: str, depth: int = 1) -> list[dict]:
        nodes = self.memory.graph.get_connected(decision_id, depth=depth, user_id=self._current_user_id)
        return [self._node_to_dict(n) for n in nodes]

    async def _tool_get_decision_details(self, decision_id: str) -> dict:
        node = self.memory.graph.get_decision(decision_id, user_id=self._current_user_id)
        if not node:
            return {"error": f"Decision {decision_id} not found."}
        res = self._node_to_dict(node)
        # Add extra details
        res["raw_text"] = node.raw_text
        res["context"] = node.metadata.get("context", "")
        res["alternatives_considered"] = node.metadata.get("alternatives_considered", []) or node.metadata.get("alternatives", [])
        res["decision_maker"] = node.metadata.get("decision_maker", "Unknown")
        return res

    @staticmethod
    def _node_to_dict(node: DecisionNode) -> dict:
        return {
            "id": node.id,
            "title": node.title,
            "summary": node.summary,
            "date": node.date,
            "source": node.source,
            "participants": node.participants,
            "outcome": node.outcome,
            "topics": node.topics,
        }

    # ── ReAct Loop Execution ──────────────────────────────────────────────────

    async def execute(self, input_data: Any, **kwargs) -> dict:
        """Execute multi-step ReAct reasoning loop to answer a query."""
        question = input_data if isinstance(input_data, str) else str(input_data)
        # Scope every tool call in this run to the asking user.
        self._current_user_id = kwargs.get("user_id")

        self.think(f"Starting deep research for query: '{question}'")

        system_prompt = f"""You are the KAIROS Research Agent, an expert in deep-dive retrieval and fact-finding.
Your goal is to answer the user's query by executing a series of search actions to gather complete, high-quality information.

You have access to these tools:
{self.get_tools_description()}

To use a tool, output a Thought followed by an Action block, exactly in this format:

Thought: Write your reasoning about what information is missing and why you are calling this tool.

Action: {{"name": "tool_name", "arguments": {{"arg1": "val1"}}}}

The system will execute the tool and return the Observation. Repeat this process as needed.
When you have collected all necessary facts to answer the question, output your final answer as:

Action: {{"name": "Final Answer", "arguments": {{"answer": "Your comprehensive answer with specific details and citations here."}}}}

Do not output any text after the Action block. Always verify facts and relations between decisions.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Query: {question}"}
        ]

        final_answer = ""
        
        for iteration in range(self.max_iterations):
            try:
                response = await self._chat_completion_with_fallback(
                    client=self._client,
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=800,
                )

                raw_response = response.choices[0].message.content.strip()
                
                # Parse Thought & Action
                thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", raw_response, re.DOTALL | re.IGNORECASE)
                action_match = re.search(r"Action:\s*(\{.*\})", raw_response, re.DOTALL | re.IGNORECASE)

                if thought_match:
                    thought = thought_match.group(1).strip()
                    self.think(thought)
                    # Keep track in conversation history
                    messages.append({"role": "assistant", "content": f"Thought: {thought}"})
                
                if not action_match:
                    # If LLM didn't format properly, try parsing the whole thing as action if it looks like JSON
                    json_match = re.search(r"(\{.*\})", raw_response, re.DOTALL)
                    if json_match:
                        action_json_str = json_match.group(1).strip()
                    else:
                        raise ValueError(f"Could not parse action from agent response: {raw_response}")
                else:
                    action_json_str = action_match.group(1).strip()

                try:
                    action_data = json.loads(action_json_str)
                except json.JSONDecodeError:
                    # Try cleaning up curly braces
                    raise ValueError(f"Action block was not valid JSON: {action_json_str}")

                tool_name = action_data.get("name")
                tool_args = action_data.get("arguments", {})

                if tool_name == "Final Answer":
                    final_answer = tool_args.get("answer", "")
                    self.reflect(f"Research finished. Generated final answer.")
                    break

                self.think(f"Executing tool '{tool_name}' with args {json.dumps(tool_args)}")
                
                # Call tool
                observation = await self.use_tool(tool_name, **tool_args)
                observation_str = json.dumps(observation, indent=2)
                
                # Shorten observation log in the console trace
                obs_summary = str(observation)[:150] + "..." if len(str(observation)) > 150 else str(observation)
                self.observe(f"Tool {tool_name} returned: {obs_summary}")

                # Append tool result to messages
                messages.append({
                    "role": "user",
                    "content": f"Observation from {tool_name}:\n{observation_str}"
                })

            except Exception as e:
                self.observe(f"Error in ReAct step: {e}")
                messages.append({
                    "role": "user",
                    "content": f"Error executing previous action: {e}. Please correct your format or choose a different action."
                })

        if not final_answer:
            final_answer = "Research agent timed out or failed to find a final answer."

        stream_callback = kwargs.get("stream_callback")
        if stream_callback:
            for token in re.split(r'(\s+)', final_answer):
                if token:
                    await stream_callback({"type": "token", "content": token})
                    await asyncio.sleep(0.01)

        # Let's perform a semantic search to attach source nodes to the returned output
        relevant = self.memory.semantic_search(question, n_results=5, user_id=self._current_user_id)

        return {
            "answer": final_answer,
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
        }

    async def evaluate_confidence(self, input_data: Any, output: Any) -> float:
        """Evaluate how complete our research answer is."""
        if isinstance(output, dict) and "answer" in output:
            ans = output["answer"]
            # If default failure/timeout message
            if "failed to find" in ans or "timed out" in ans:
                return 0.2
            # High confidence if we cited specific details
            if len(ans) > 200:
                return 0.9
            return 0.7
        return 0.5

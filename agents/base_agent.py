"""
KAIROS Base Agent — Abstract foundation for all KAIROS agents.

Implements:
  - ReAct (Reasoning + Acting) loop: Think → Act → Observe
  - Tool registry: Each agent declares its available tools
  - Execution traces: Every action logged for full transparency
  - Self-reflection: Agents evaluate their own output quality
  - Retry with backoff: Automatic retry on transient failures

All KAIROS agents inherit from this class.
"""

from __future__ import annotations

import time
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from enum import Enum


# ── Trace Models ─────────────────────────────────────────────────────────────

class TraceStepType(str, Enum):
    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"
    REFLECT = "reflect"
    ERROR = "error"
    RESULT = "result"


@dataclass
class TraceStep:
    """A single step in an agent's execution trace."""
    step_type: TraceStepType
    content: str
    timestamp: float = 0.0
    duration_ms: float = 0.0
    tool_name: str = ""
    tool_input: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "type": self.step_type.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "metadata": self.metadata,
        }


@dataclass
class AgentResult:
    """Result returned by an agent after execution."""
    success: bool
    output: Any
    trace: list[TraceStep] = field(default_factory=list)
    confidence: float = 0.0   # 0.0 - 1.0
    error: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output if isinstance(self.output, (str, dict, list)) else str(self.output),
            "trace": [s.to_dict() for s in self.trace],
            "confidence": self.confidence,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


# ── Tool Definition ──────────────────────────────────────────────────────────

@dataclass
class AgentTool:
    """A tool available to an agent."""
    name: str
    description: str
    handler: Callable[..., Awaitable[Any]]
    parameters: dict = field(default_factory=dict)  # JSON Schema style

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ── Base Agent ───────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base class for all KAIROS agents.
    Provides ReAct loop, tool management, tracing, and retry logic.
    """

    def __init__(self, name: str, description: str, max_iterations: int = 5):
        self.name = name
        self.description = description
        self.max_iterations = max_iterations
        self._tools: dict[str, AgentTool] = {}
        self._trace: list[TraceStep] = []
        self._start_time: float = 0

        # Register agent-specific tools
        self._register_tools()

    # ── Tool Registry ─────────────────────────────────────────────────────────

    def register_tool(self, tool: AgentTool):
        """Register a tool for this agent."""
        self._tools[tool.name] = tool

    def _register_tools(self):
        """Override in subclasses to register agent-specific tools."""
        pass

    def get_tools_description(self) -> str:
        """Get a formatted description of all available tools for LLM prompts."""
        if not self._tools:
            return "No tools available."
        lines = []
        for tool in self._tools.values():
            lines.append(f"- **{tool.name}**: {tool.description}")
        return "\n".join(lines)

    async def use_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a registered tool by name."""
        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self._tools[tool_name]
        start = time.time()

        try:
            result = await tool.handler(**kwargs)
            duration = (time.time() - start) * 1000

            self._add_trace(TraceStep(
                step_type=TraceStepType.ACT,
                content=f"Called tool: {tool_name}",
                tool_name=tool_name,
                tool_input=str(kwargs)[:200],
                duration_ms=duration,
            ))

            return result
        except Exception as e:
            self._add_trace(TraceStep(
                step_type=TraceStepType.ERROR,
                content=f"Tool {tool_name} failed: {str(e)}",
                tool_name=tool_name,
            ))
            raise

    # ── Trace Management ──────────────────────────────────────────────────────

    def _add_trace(self, step: TraceStep):
        """Add a step to the execution trace."""
        self._trace.append(step)

    def think(self, thought: str):
        """Record a reasoning step."""
        self._add_trace(TraceStep(
            step_type=TraceStepType.THINK,
            content=thought,
        ))

    def observe(self, observation: str):
        """Record an observation after acting."""
        self._add_trace(TraceStep(
            step_type=TraceStepType.OBSERVE,
            content=observation,
        ))

    def reflect(self, reflection: str):
        """Record a self-reflection step."""
        self._add_trace(TraceStep(
            step_type=TraceStepType.REFLECT,
            content=reflection,
        ))

    def get_trace(self) -> list[TraceStep]:
        """Get the current execution trace."""
        return list(self._trace)

    def clear_trace(self):
        """Clear the execution trace for a new run."""
        self._trace = []
        self._start_time = time.time()

    # ── ReAct Loop ────────────────────────────────────────────────────────────

    async def run(self, input_data: Any, **kwargs) -> AgentResult:
        """
        Execute the agent's ReAct loop:
          1. Think: Analyze the input and determine what to do
          2. Act: Execute the planned action (tool call, search, etc.)
          3. Observe: Evaluate the result
          4. Repeat or finalize
        """
        self.clear_trace()
        start = time.time()

        try:
            output = await self.execute(input_data, **kwargs)
            duration = (time.time() - start) * 1000

            # Self-reflection on output quality
            confidence = await self.evaluate_confidence(input_data, output)

            self._add_trace(TraceStep(
                step_type=TraceStepType.RESULT,
                content=f"Completed with confidence {confidence:.0%}",
                duration_ms=duration,
            ))

            return AgentResult(
                success=True,
                output=output,
                trace=self.get_trace(),
                confidence=confidence,
                duration_ms=duration,
            )

        except Exception as e:
            duration = (time.time() - start) * 1000
            self._add_trace(TraceStep(
                step_type=TraceStepType.ERROR,
                content=str(e),
                duration_ms=duration,
            ))
            return AgentResult(
                success=False,
                output=None,
                trace=self.get_trace(),
                confidence=0.0,
                error=str(e),
                duration_ms=duration,
            )

    @abstractmethod
    async def execute(self, input_data: Any, **kwargs) -> Any:
        """
        Core execution logic. Subclasses implement their specific behavior here.
        Use self.think(), self.observe(), self.reflect(), and self.use_tool()
        within this method to build the ReAct trace.
        """
        ...

    async def evaluate_confidence(self, input_data: Any, output: Any) -> float:
        """
        Evaluate confidence in the output. Override for custom logic.
        Default returns 0.7 (medium confidence).
        """
        return 0.7

    # ── Retry with Backoff ────────────────────────────────────────────────────

    async def run_with_retry(
        self, input_data: Any, max_retries: int = 3, base_delay: float = 1.0, **kwargs
    ) -> AgentResult:
        """Execute with exponential backoff retry on failure."""
        last_result = None

        for attempt in range(max_retries):
            result = await self.run(input_data, **kwargs)
            if result.success:
                return result

            last_result = result
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                self.think(f"Attempt {attempt + 1} failed. Retrying in {delay}s...")
                await asyncio.sleep(delay)

        return last_result

    # ── Persona overlay ───────────────────────────────────────────────────────

    @staticmethod
    def apply_persona(system_prompt: str, persona_overlay: dict | None) -> str:
        """Prepend a short tone/voice instruction to a system prompt. Additive
        only — never touches the extraction/classification instructions below it,
        only the framing of the agent's user-facing output text. `persona_overlay`
        is a dict shaped like core.personas.AgentPersonaStore.get()'s return value;
        pass None (or a default persona) to leave the prompt unchanged."""
        if not persona_overlay or persona_overlay.get("is_default"):
            return system_prompt
        display_name = persona_overlay.get("display_name")
        tone = persona_overlay.get("tone_preset", "professional")
        if not display_name:
            return system_prompt
        # Defense-in-depth: display_name is sanitized at write time (see
        # core.personas.sanitize_display_name), but strip control/newline chars
        # here too so this stays safe even if a caller ever bypasses that path —
        # an embedded newline would let display_name break out of this single-line
        # instruction and inject arbitrary text into the system prompt.
        import re
        safe_name = re.sub(r"[\x00-\x1f\x7f]+", " ", str(display_name)).strip()[:80]
        if not safe_name:
            return system_prompt
        overlay = f"Respond as '{safe_name}', a {tone} analyst. Keep this persona in your tone and phrasing only — never change what facts you report.\n\n"
        return overlay + system_prompt

    # ── Info ──────────────────────────────────────────────────────────────────

    def info(self) -> dict:
        """Get agent metadata."""
        return {
            "name": self.name,
            "description": self.description,
            "tools": [t.to_dict() for t in self._tools.values()],
            "max_iterations": self.max_iterations,
        }

    async def _chat_completion_with_fallback(
        self,
        client: Any = None,
        model: str = None,
        *,
        messages: list[dict],
        stream: bool = False,
        fast: bool = False,
        **kwargs,
    ) -> Any:
        """
        Run a chat completion against the configured provider chain, in priority
        order (Fireworks → Groq → Gemini; see ``config.text_providers``).

        Fireworks (AMD) is primary. If it rate-limits or errors, we fall straight
        through to the next provider so a single hiccup never breaks a query. The
        legacy ``client``/``model`` args are accepted for backward-compatibility
        but ignored — provider selection is owned by config, the single source of
        truth. Pass ``fast=True`` for high-volume ingestion to use cheaper models.
        """
        import asyncio
        import re
        from openai import AsyncOpenAI
        from config import config

        providers = config.text_providers(fast=fast)
        if not providers:
            raise RuntimeError(
                "No AI provider configured. Set FIREWORKS_API_KEY (preferred), "
                "or GROQ_API_KEY / GEMINI_API_KEY."
            )

        last_err = None
        for name, api_key, base_url, pmodel in providers:
            cli = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=90)
            # One in-place retry only when this is the *sole* provider — otherwise
            # rolling to the next provider is faster than waiting out a 429.
            attempts = 2 if len(providers) == 1 else 1
            for attempt in range(attempts):
                try:
                    return await cli.chat.completions.create(
                        model=pmodel, messages=messages, stream=stream, **kwargs
                    )
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    # Bad/expired key → disable this provider for the rest of the
                    # process so we don't pay its latency on every future call.
                    if "401" in msg or "403" in msg or "invalid" in msg.lower() or "unauthorized" in msg.lower():
                        config.mark_provider_dead(base_url)
                        print(f"[{self.name}] {name} auth failed — disabling for this session")
                        break
                    is_rate_limit = "429" in msg or "rate" in msg.lower()
                    if is_rate_limit and attempt < attempts - 1:
                        m = re.search(r"try again in ([\d.]+)s", msg)
                        wait = min(float(m.group(1)) + 0.5, 20.0) if m else 6.0
                        print(f"[{self.name}] {name} rate-limited — retrying in {wait:.1f}s")
                        await asyncio.sleep(wait)
                        continue
                    print(f"[{self.name}] {name} failed ({msg[:140]}) — trying next provider")
                    break  # move on to the next provider in the chain

        raise last_err or RuntimeError("All AI providers failed")

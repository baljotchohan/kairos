"""
KAIROS MCP Server — exposes 3 tools over Streamable HTTP.
Uses FastMCP from the mcp package.

Tools:
  get_context(query, limit)                    → semantic search, returns top decisions
  store_context(decision, context, ...)        → manually store a decision
  search_decisions(topic, date_from, ...)      → structured search by filters

Run: python mcp_server.py
  → Serves at http://localhost:8001/mcp (streamable-http transport)

Add to Claude Desktop / Cursor MCP config:
  {
    "mcpServers": {
      "kairos": {
        "url": "http://localhost:8000/mcp"
      }
    }
  }
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from mcp.server.fastmcp import FastMCP

from core.memory import KairosMemory
from core.graph import DecisionNode

# ── Init ──────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="KAIROS",
    instructions=(
        "KAIROS is a Company Organizational Memory OS. "
        "It stores and retrieves every important decision a company has ever made — "
        "from Slack threads, emails, meeting transcripts, and documents. "
        "Call get_context() before answering ANY question about company history, "
        "decisions, architecture, vendors, or strategy. "
        "Call store_context() whenever the user shares important decisions or "
        "organizational knowledge that should be permanently remembered."
    ),
)

memory = KairosMemory()

# MCP_TENANT_ID scopes all reads/writes to a single tenant (user_id).
# Set this env var to the Firebase UID of the workspace you want this MCP
# server to access. If unset, falls back to "mcp-system" (isolated namespace).
MCP_TENANT_ID: str = os.environ.get("MCP_TENANT_ID", "mcp-system")


# ── Tool 1: get_context ───────────────────────────────────────────────────────

@mcp.tool()
def get_context(query: str, limit: int = 5) -> str:
    """Get organizational context and decisions relevant to a query.

    Call this before answering ANY question about company decisions, history,
    architecture, vendors, or strategy. Returns the most relevant past decisions
    with full context, source citations, participants, and outcomes.

    Args:
        query: Natural language question, e.g. "Why do we use AWS?" or
               "Who decided to hire remote engineers?" or "mobile app history".
        limit: Max number of decisions to return (default 5).

    Returns:
        Formatted string of relevant decisions with context, sources, and
        participant information for the AI to use in its answer.
    """
    results = memory.get_context(query, n_results=limit, user_id=MCP_TENANT_ID)

    if not results:
        return (
            f"KAIROS: No decisions found in organizational memory for: '{query}'\n"
            "This topic has no recorded history. The company may not have made a "
            "formal decision on this, or it predates KAIROS adoption."
        )

    lines = [
        f"KAIROS ORGANIZATIONAL MEMORY — {len(results)} decision(s) found for: '{query}'\n",
        "=" * 60,
    ]

    for i, d in enumerate(results, 1):
        participants_str = ", ".join(d["participants"]) if d["participants"] else "Unknown"
        related_count = len(d.get("related", []))

        lines.append(f"""
DECISION {i}: {d['title']}
  Date:         {d['date']}
  Source:       {d['source']}
  Participants: {participants_str}
  Summary:      {d['summary']}
  Outcome:      {d['outcome']}
  Related:      {related_count} connected decision(s) in graph
{"—" * 50}""")

    lines.append(
        "\nUse this context to answer the user's question with full organizational history."
    )
    return "\n".join(lines)


# ── Tool 2: store_context ─────────────────────────────────────────────────────

@mcp.tool()
def store_context(
    decision: str,
    context: str,
    participants: list[str],
    date: str,
    source: str,
    project: str = "General",
) -> str:
    """Store an important decision or organizational context permanently in KAIROS memory.

    Call this whenever the user shares important decisions or organizational
    knowledge that should be remembered. KAIROS will auto-link this decision
    to existing related decisions in the graph and export it to the Obsidian vault.

    Args:
        decision: Short title for the decision (max ~10 words), e.g.
                  "Chose Node.js over Python for backend".
        context:  Full context — why was this decision made? What alternatives
                  were considered? What were the trade-offs?
        participants: People involved in making the decision, e.g.
                      ["Priya Sharma (CTO)", "Dev Anand"].
        date:     Date of decision in ISO format YYYY-MM-DD, e.g. "2024-03-15".
        source:   Where this came from, e.g. "Slack #engineering", "Email thread",
                  "Board meeting", "Google Drive doc", "Manual entry".
        project:  Project or department this belongs to (default "General"),
                  e.g. "Infrastructure", "Product", "Sales".

    Returns:
        Confirmation string with the stored decision ID and auto-link summary.
    """
    node_id = str(uuid.uuid4())

    # Derive a clean outcome from the decision title + context
    outcome = context[:500] if len(context) > 500 else context

    node = DecisionNode(
        id=node_id,
        title=decision,
        summary=context[:300] if len(context) > 300 else context,
        date=date,
        participants=participants,
        source=source,
        source_url="",
        topics=[project] if project != "General" else [],
        outcome=outcome,
        raw_text=context,
        metadata={
            "project": project,
            "stored_via": "mcp_store_context",
        },
    )

    memory.store(node, user_id=MCP_TENANT_ID)

    participants_str = ", ".join(participants) if participants else "Not specified"
    return (
        f"KAIROS: Decision stored successfully.\n"
        f"  ID:           {node_id}\n"
        f"  Title:        {decision}\n"
        f"  Date:         {date}\n"
        f"  Source:       {source}\n"
        f"  Participants: {participants_str}\n"
        f"  Project:      {project}\n"
        f"\nAuto-linked to related decisions in the graph. "
        f"Obsidian vault updated."
    )


# ── Tool 3: search_decisions ──────────────────────────────────────────────────

@mcp.tool()
def search_decisions(
    topic: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    person: Optional[str] = None,
    project: Optional[str] = None,
) -> str:
    """Search for specific decisions by topic, date range, person, or project.

    Use this for precise filtered queries, such as:
    - "all decisions about AWS" → topic="AWS"
    - "decisions by John in 2021" → person="John", date_from="2021-01-01", date_to="2021-12-31"
    - "vendor decisions in Q4 2022" → topic="vendor", date_from="2022-10-01", date_to="2022-12-31"
    - "mobile project decisions" → project="Mobile"

    For open-ended semantic questions ("why do we use X?"), prefer get_context() instead.

    Args:
        topic:      Topic keyword to search for, e.g. "AWS", "vendor", "hiring", "backend".
        date_from:  Start of date range (YYYY-MM-DD), e.g. "2021-01-01".
        date_to:    End of date range (YYYY-MM-DD), e.g. "2021-12-31".
        person:     Person name to filter by, e.g. "John Smith" or just "John".
        project:    Project/department filter, e.g. "Mobile", "Infrastructure".

    Returns:
        Formatted list of matching decisions with dates, sources, and summaries.
    """
    # Use project as an additional topic filter if provided
    search_topic = topic
    if project and not topic:
        search_topic = project
    elif project and topic:
        search_topic = topic  # topic takes priority; project is secondary

    results = memory.structured_search(
        topic=search_topic,
        person=person,
        date_from=date_from,
        date_to=date_to,
        user_id=MCP_TENANT_ID,
    )

    # Secondary filter by project if topic was already set
    if project and topic:
        project_results = memory.structured_search(topic=project, person=person,
                                                   date_from=date_from, date_to=date_to,
                                                   user_id=MCP_TENANT_ID)
        # Merge and deduplicate by ID
        seen = {n.id for n in results}
        for n in project_results:
            if n.id not in seen:
                results.append(n)
                seen.add(n.id)

    if not results:
        filters = []
        if topic:
            filters.append(f"topic='{topic}'")
        if person:
            filters.append(f"person='{person}'")
        if date_from:
            filters.append(f"from {date_from}")
        if date_to:
            filters.append(f"to {date_to}")
        if project:
            filters.append(f"project='{project}'")
        filter_str = ", ".join(filters) if filters else "no filters"
        return f"KAIROS: No decisions found matching filters: {filter_str}"

    lines = [
        f"KAIROS: {len(results)} decision(s) found\n",
        "=" * 60,
    ]

    for i, n in enumerate(results, 1):
        participants_str = ", ".join(n.participants) if n.participants else "Unknown"
        topics_str = ", ".join(n.topics) if n.topics else "Untagged"
        lines.append(
            f"\n{i}. [{n.date}] {n.title}\n"
            f"   Source:       {n.source}\n"
            f"   Participants: {participants_str}\n"
            f"   Topics:       {topics_str}\n"
            f"   Summary:      {n.summary}\n"
            f"   Outcome:      {n.outcome[:200]}{'...' if len(n.outcome) > 200 else ''}\n"
        )

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp._mcp_server.run(streams[0], streams[1], mcp._mcp_server.create_initialization_options())

    starlette_app = Starlette(routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ])

    uvicorn.run(starlette_app, host="0.0.0.0", port=8002)

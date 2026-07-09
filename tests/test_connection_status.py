"""
Regression tests for tool/app request routing in the orchestrator.

Any question about the user's connected tools — their status ("which apps am I
connected to") OR their live data ("list all data from my connected apps", "use
slack, see my messages") — must be routed to the LiveDataAgent, which answers
with a real LLM call over real connector output. It must NOT fall into the
memory-search path, where such requests died with "I wasn't able to generate a
response". Decision/history questions that merely mention a tool ("why did we
pick Slack") must stay in search.

These tests lock in the two detectors that correct classifier drift.
"""

import core.orchestrator as orch


def _routes_to_live_data(q: str) -> bool:
    """Mirror of the orchestrator's reroute condition."""
    return orch._is_connection_status_question(q) or orch._looks_like_live_source_request(q)


# ── Should reach the LiveDataAgent ────────────────────────────────────────────

def test_named_tool_and_all_tools_requests_route_to_live_data():
    for q in [
        # every real query that failed in production before this fix
        "ok kairos use slack see any message store that",
        "use all tools list all data from all apps are which are connected",
        "ok so use notion list all data in kairos",
        # plus natural phrasings that must also work
        "list all my notion pages",
        "show my github repos",
        "any recent emails",
        "extract messages from slack",
        "list all data from all connected apps",
        "what's in my drive",
    ]:
        assert _routes_to_live_data(q) is True, q


def test_mailbox_phrasings_route_to_live_data():
    # "mail"/"inbox"/"unread" were holes in the keyword list — "ok so what is my
    # last mail" got labeled search and died. These must reach the LiveDataAgent.
    for q in [
        "ok so what is my last mail",
        "what is my last mail",
        "how many unread emails do I have",
        "show my latest email from finance",
        "check my inbox",
        "ok so list all files in my drive",
    ]:
        assert _routes_to_live_data(q) is True, q


def test_connection_status_questions_route_to_live_data():
    for q in [
        "which apps are connected",
        "what tools am I connected to",
        "am I connected to anything",
        "what's connected",
        "list my connected integrations",
    ]:
        assert _routes_to_live_data(q) is True, q


# ── Should stay in memory search ──────────────────────────────────────────────

def test_decision_and_history_questions_stay_in_search():
    # These mention a tool but are genuine decision history — the LiveDataAgent
    # would be the wrong place; they must stay in the memory-search path.
    for q in [
        "why did we decide to use slack",
        "why do we use notion over confluence",
        "what was the reason we chose github",
        "why did we decide to connect our CRM to Salesforce in 2019",
        "why do we use React",
        "who approved the vendor contract",
        "summarize our q3 vendor decisions",
    ]:
        assert _routes_to_live_data(q) is False, q


# ── store_decision backstop ───────────────────────────────────────────────────
# The user hands KAIROS a fact to SAVE. If the LLM router mislabels it as search,
# the request dies in memory-search AND nothing is written. This backstop catches
# that drift — but must never fire on an ordinary question.

def test_record_a_fact_requests_route_to_store_decision():
    for q in [
        "ok add decision we are hiring interns in next week with date add by yourself",
        "remember that we decided to use Postgres",
        "note that the vendor contract was renewed",
        "log a decision: launching in March",
        "store this: Raj approved the AWS migration",
        "for the record, we picked AWS",
        "add a decision that we will launch mobile in March",
    ]:
        assert orch._looks_like_store_decision(q) is True, q


def test_questions_and_fetches_are_not_store_decisions():
    for q in [
        "add up my unread emails",            # data fetch reusing "add"
        "why did we add the vendor decision",  # history question
        "what decisions did we make in Q3",    # question about stored decisions
        "list my files",                       # live_data fetch
        "show my last email",                  # live_data fetch
        "why do we use React",                 # search
    ]:
        assert orch._looks_like_store_decision(q) is False, q

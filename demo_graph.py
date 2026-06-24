"""
Seeds KAIROS with demo decisions and auto-syncs the Obsidian vault.
Every memory.store() call writes to ChromaDB + SQLite + graph AND updates
the affected Obsidian notes immediately — no separate export step needed.

    python demo_graph.py

Then open obsidian_vault/ in Obsidian → Graph View.
"""

from core.memory import KairosMemory
from core.graph import DecisionNode

memory = KairosMemory(
    chroma_path="./chroma_db",
    db_path="./kairos.db",
    obsidian_vault="./obsidian_vault",
)

decisions = [
    DecisionNode(
        id="d1",
        title="Why we chose AWS over GCP",
        summary="Team evaluated AWS and GCP for primary cloud provider in Q3 2021.",
        date="2021-08-15",
        participants=["Raj Singh", "John Smith", "Priya Kapoor"],
        source="Slack #engineering",
        source_url="https://slack.com/archives/C123/p1629",
        topics=["Infrastructure", "Cloud"],
        outcome="Chose AWS. Reason: existing team expertise + larger hiring pool. Risk noted: vendor lock-in.",
    ),
    DecisionNode(
        id="d2",
        title="Why we chose React over Vue",
        summary="Frontend team voted on React vs Vue for the main product UI.",
        date="2022-03-10",
        participants=["Priya Kapoor", "Arjun Mehta", "Sara Lee", "Tom B", "Alex K"],
        source="Slack #frontend",
        source_url="https://slack.com/archives/C456/p1646",
        topics=["Frontend", "Engineering"],
        outcome="React won 4-2. Reason: larger hiring pool. Vue advocate: Priya Kapoor (still at company).",
    ),
    DecisionNode(
        id="d3",
        title="2021 Mobile App attempt — Failed",
        summary="Decision to build a native mobile app in 2021.",
        date="2021-03-01",
        participants=["John Smith", "Board"],
        source="Board Meeting March 2021",
        source_url="https://drive.google.com/doc/board-march-2021",
        topics=["Mobile", "Product"],
        outcome="Attempted and failed. Reason: no mobile expertise. Cost: ₹40L. Project killed at board meeting.",
    ),
    DecisionNode(
        id="d4",
        title="Vendor contract auto-renewal — $2.3M",
        summary="Infrastructure vendor contract signed Nov 2019, auto-renewed 3 times.",
        date="2019-11-01",
        participants=["John Smith"],
        source="Email thread",
        source_url="https://mail.google.com/thread/abc123",
        topics=["Finance", "Infrastructure", "Vendor"],
        outcome="Paying $191K/month since 2019. Decision maker left in 2022. No one noticed 3 auto-renewals.",
    ),
    DecisionNode(
        id="d5",
        title="Switch from Jenkins to GitHub Actions",
        summary="CI/CD pipeline migration decision after Jenkins maintenance overhead grew.",
        date="2022-09-20",
        participants=["Raj Singh", "Arjun Mehta"],
        source="Jira INFRA-441",
        source_url="https://jira.company.com/browse/INFRA-441",
        topics=["Infrastructure", "Engineering", "DevOps"],
        outcome="Migrated all pipelines to GitHub Actions. Saved ~12 hours/month of maintenance.",
    ),
]

# Each store() call → ChromaDB + SQLite + graph + Obsidian notes updated live
for d in decisions:
    memory.store(d)
    print(f"  ✓ stored + synced: {d.title}")

print(f"\nGraph: {memory.graph.stats()}")
print(f"Obsidian vault: ./obsidian_vault/  ← open in Obsidian → Graph View")

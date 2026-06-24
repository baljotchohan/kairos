"""
Seed KAIROS with Helios Tech demo data.

    python scripts/seed_demo_data.py

Stores 12 decisions covering all 3 hackathon demo scenarios.
After running: open obsidian_vault/ in Obsidian → Graph View.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory import KairosMemory
from data.demo.helios_tech import get_demo_decisions


def main():
    print("🧠 KAIROS Demo Seeder — Helios Tech Dataset")
    print("=" * 50)

    memory = KairosMemory()
    decisions = get_demo_decisions()

    print(f"Seeding {len(decisions)} decisions...\n")

    for i, node in enumerate(decisions, 1):
        memory.store(node)
        print(f"  [{i:02d}/{len(decisions)}] ✓ {node.title[:60]}")

    stats = memory.graph.stats()
    print(f"\n{'=' * 50}")
    print(f"✅ Done!")
    print(f"   Decisions stored : {stats['total_decisions']}")
    print(f"   Relations linked : {stats['total_relations']}")
    print(f"   Graph components : {stats['connected_components']}")
    print(f"\n📂 Obsidian vault updated → {memory.obsidian_vault}/")
    print("   Open in Obsidian → Graph View to see the decision web")
    print("\n🎯 Demo scenarios ready:")
    print("   1. Ask: 'Why are we paying the Salesforce vendor?' → zombie contract")
    print("   2. Ask: 'Why do we use Node.js?' → new hire answer in seconds")
    print("   3. Ask: 'Should we build a mobile app?' → surfaces 2021 failure")


if __name__ == "__main__":
    main()

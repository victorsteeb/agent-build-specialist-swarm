"""
Stretch: add a Critic sub-agent to the coordinator's roster.

The critic's job is to review the coordinator's draft before it goes out.
It must produce one of three verdicts:
- "ship it" (with a brief why)
- "revise" (with specific revisions)
- "stop" (with reason — e.g., we shouldn't pursue this deal)

This script creates the critic agent and updates the coordinator's roster
to include it. Then update the coordinator's system prompt to "always
consult the Critic on the draft before finalising."

Usage:
    python stretch_critic_subagent.py
"""

import json
from pathlib import Path

import anthropic

from _common import get_client, read_id


CRITIC_SYSTEM = """\
You are the Deal Desk Critic. You don't write proposals. You review them.

When the coordinator asks for your review, you'll receive:
- The draft proposal
- The RFP (for context)

Your job: deliver one of three verdicts.

1. **SHIP IT** — the proposal is solid, with at most cosmetic suggestions.
2. **REVISE** — specific issues that need fixing. List them tersely. No more
   than 5 issues; if there are more, the proposal isn't ready.
3. **STOP** — we shouldn't pursue this deal. Reasons might include: terms
   we can't deliver, mismatched scale, regulatory issues, strategic conflict.

Be sceptical. Your value to the coordinator is that you push back. A senior
partner who never gets pushback gets sloppy.

Lead your reply with: VERDICT: SHIP IT / REVISE / STOP.
"""


CRITIC_GUIDANCE = (
    "\n\n# Critic\n\n"
    "Before producing the final document, send your draft to the Deal "
    "Desk Critic. The Critic will reply with one of: SHIP IT, REVISE, "
    "or STOP.\n"
    "- If SHIP IT: produce the final docx.\n"
    "- If REVISE: address the issues and re-submit to the Critic. "
    "Repeat at most twice.\n"
    "- If STOP: report to the user with the Critic's reasoning. Do "
    "NOT produce the final docx.\n"
)


def _roster_entry(entry) -> dict:
    """Normalise roster entries (SDK objects or dicts) to plain dicts."""
    if isinstance(entry, dict):
        return entry
    return entry.model_dump(exclude_none=True)


def main() -> None:
    client = get_client()

    coordinator_id = read_id(".coordinator_id", "Run create_coordinator.py first.")
    ids_path = Path(".specialist_ids.json")
    if not ids_path.exists():
        raise SystemExit("Missing .specialist_ids.json. Run create_specialists.py first.")
    specialist_ids = json.loads(ids_path.read_text())

    # Reuse an existing critic — never mint duplicates on re-run
    critic_id = specialist_ids.get("critic")
    if critic_id:
        try:
            client.beta.agents.retrieve(critic_id)
            print(f"Reusing critic: {critic_id}")
        except anthropic.APIStatusError:
            critic_id = None
    if not critic_id:
        critic = client.beta.agents.create(
            name="Deal Desk Critic",
            model="claude-opus-4-8",  # The critic needs to be sharp
            system=CRITIC_SYSTEM,
            tools=[{"type": "agent_toolset_20260401"}],
            metadata={
                "hackathon": "partner-basecamp-2026",
                "track": "specialist-swarm",
                "role": "critic",
            },
        )
        critic_id = critic.id
        print(f"Critic created: {critic_id}")
        specialist_ids["critic"] = critic_id
        ids_path.write_text(json.dumps(specialist_ids, indent=2))

    # Update the coordinator: add the critic to the roster and the guidance to
    # the prompt — each exactly once, no matter how often this script runs.
    coordinator = client.beta.agents.retrieve(coordinator_id)
    roster = [_roster_entry(e) for e in coordinator.multiagent.agents]
    changed = False

    if not any(e.get("id") == critic_id for e in roster):
        roster.append({"type": "agent", "id": critic_id})
        changed = True

    new_system = coordinator.system or ""
    if "# Critic" not in new_system:
        new_system = new_system + CRITIC_GUIDANCE
        changed = True

    if changed:
        client.beta.agents.update(
            coordinator_id,
            version=coordinator.version,
            system=new_system,
            multiagent={"type": "coordinator", "agents": roster},
        )
        print("Coordinator updated: critic is in the roster and the prompt.")
    else:
        print("Coordinator already has the critic — nothing to change.")

    print("Re-run run_deal_desk.py to see the critic in action.")


if __name__ == "__main__":
    main()

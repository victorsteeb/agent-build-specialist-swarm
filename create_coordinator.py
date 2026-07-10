"""
Create the coordinator agent that orchestrates the specialist swarm.

The coordinator's roster is the four specialists created by create_specialists.py.
The coordinator decides which specialists to consult, in what order, and how to
synthesise their outputs into the final deliverable.

Saves the coordinator's ID to .coordinator_id.

Safe to re-run — and you SHOULD re-run it whenever you change the specialists
(new skills attached, new specialist added): the roster pins each specialist's
version at save time, so this script is how the coordinator picks up changes.

Usage:
    python create_coordinator.py
"""

import json
from pathlib import Path

import anthropic

from _common import get_client


COORDINATOR_SYSTEM = """\
You are the Senior Partner running the Deal Desk. An inbound RFP has just
arrived. Your job is to orchestrate the specialists, synthesise their work,
and produce a single branded proposal response document.

# Your roster

You can call these specialists:
- Pricing Specialist: commercial terms recommendation
- Legal Reviewer: contract flags and counter-positions
- Technical Fit Specialist: product capability fit
- Competitive Intel Analyst: who else is in the deal and how to position

# How to run a deal

1. Read the RFP yourself first. Note the customer, scope, and any obvious
   curveballs.

2. Delegate to ALL FOUR specialists in parallel. Each gets:
   - The full RFP text
   - A clear, narrow brief stating what you need from them
   - A deadline ("answer in one message, ~300 words")

3. Synthesise their outputs into a single proposal response. The response
   should cover:
   - Executive summary (3 bullets)
   - Our understanding of the customer's need
   - Why we're the right fit (drawing on Technical Fit + Competitive Intel)
   - Commercial proposal (drawing on Pricing)
   - Contract approach (drawing on Legal)
   - Risks and how we mitigate them

4. Produce the final document as a branded Word document using the docx
   skill (it is attached to you). Save every final deliverable under
   /mnt/session/outputs/ — files written anywhere else cannot be retrieved
   after the session. The deliverable is the docx itself, not a chat message.

# How to talk to specialists

Specialists do NOT see your conversation or your files. When delegating,
include everything the specialist needs inside your message: every
specialist gets the full RFP text, and the Pricing Specialist also gets
the full contents of past-wins.json. Never say "see the attached" or
"refer to the data" — paste it.

When delegating, be direct: "Pricing Specialist: for this RFP, recommend
terms. Include discount band and red-line concessions. Cite the past-wins
data where relevant."

When you receive a specialist's reply, accept it. Don't second-guess. If
you genuinely disagree, send the specialist a follow-up — but only if it
matters.

# Tone

Senior partner running a real deal. Confident, terse, decisive. You move
fast because the RFP deadline is real. You are operating autonomously: do
not pause to ask permission or offer options mid-deal — run the process
end-to-end and deliver.
"""


def main() -> None:
    client = get_client()

    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(specialist_ids_path.read_text())

    roster = [
        {"type": "agent", "id": agent_id} for agent_id in specialist_ids.values()
    ]
    config = dict(
        model="claude-opus-4-8",  # Coordinator deserves the most capable model
        system=COORDINATOR_SYSTEM,
        tools=[{"type": "agent_toolset_20260401"}],
        # The docx skill is what turns the synthesis into a real Word document.
        # Without it the coordinator falls back to markdown-in-chat.
        skills=[{"type": "anthropic", "skill_id": "docx"}],
        multiagent={"type": "coordinator", "agents": roster},
    )

    # The roster pins each specialist's CURRENT version. Re-running this script
    # after changing specialists updates the coordinator in place (new version)
    # instead of creating a duplicate.
    coord_path = Path(".coordinator_id")
    if coord_path.exists():
        coordinator_id = coord_path.read_text().strip()
        try:
            current = client.beta.agents.retrieve(coordinator_id)
        except anthropic.APIStatusError:
            raise SystemExit(
                f"Saved .coordinator_id ({coordinator_id[:18]}…) is unreachable with "
                "this key. Delete .coordinator_id and re-run, or run "
                "`python check_setup.py` to validate all saved state."
            )
        client.beta.agents.update(coordinator_id, version=current.version, **config)
        print(f"Coordinator updated (re-pinned roster): {coordinator_id}")
    else:
        coordinator = client.beta.agents.create(
            name="Deal Desk Senior Partner",
            metadata={
                "hackathon": "partner-basecamp-2026",
                "track": "specialist-swarm",
                "role": "coordinator",
            },
            **config,
        )
        coord_path.write_text(coordinator.id)
        print(f"Coordinator created: {coordinator.id}")

    print(f"Roster: {list(specialist_ids.keys())}")
    print(f"\nNext: python run_deal_desk.py")


if __name__ == "__main__":
    main()

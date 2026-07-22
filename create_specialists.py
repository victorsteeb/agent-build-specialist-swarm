"""
Create four specialist sub-agents for the Deal Desk swarm.

Each specialist gets:
- A narrow system prompt
- The agent toolset (file ops, web search, web fetch, bash)
- A skill that matches its domain (uploaded separately by upload_skills.py)

Saves the resulting agent IDs to .specialist_ids.json so create_coordinator.py
can reference them. Safe to re-run: existing specialists are validated and
reused, never duplicated.

Usage:
    python create_specialists.py
"""

import json
from pathlib import Path

import anthropic

from _common import get_client


SPECIALISTS = [
    {
        "key": "pricing",
        "name": "Pricing Specialist",
        "model": "claude-sonnet-5",
        "system": (
            "You are the Pricing Specialist in a Deal Desk. Your job is to "
            "recommend commercial terms for inbound RFPs.\n\n"
            "Inputs you'll receive:\n"
            "- The RFP text\n"
            "- The pricing-playbook skill (your authoritative pricing rules)\n"
            "- past-wins.json (recent comparable deals)\n\n"
            "Your output: a one-page commercial recommendation covering:\n"
            "1. List price + recommended discount band\n"
            "2. Term and payment structure\n"
            "3. Any commercial concessions you'd accept and which you'd refuse\n"
            "4. Risks to the margin\n\n"
            "Be specific about numbers. Cite the past-wins data when you use it."
        ),
    },
    {
        "key": "legal",
        "name": "Legal Reviewer",
        "model": "claude-sonnet-5",
        "system": (
            "You are the Legal Reviewer in a Deal Desk. Your job is to read "
            "an RFP and flag every clause that conflicts with our standard "
            "negotiation positions.\n\n"
            "Inputs you'll receive:\n"
            "- The RFP text\n"
            "- The legal-checklist skill (your authoritative position library)\n\n"
            "Your output: a structured list of flags, each with:\n"
            "1. The RFP requirement\n"
            "2. Why it conflicts with our standard\n"
            "3. Our recommended counter-position\n"
            "4. Severity: blocker / negotiable / acceptable\n\n"
            "Be precise. Don't flag boilerplate just because it's there — "
            "only call out things that genuinely deviate from our checklist."
        ),
    },
    {
        "key": "technical_fit",
        "name": "Technical Fit Specialist",
        "model": "claude-sonnet-5",
        "system": (
            "You are the Technical Fit Specialist. You decide whether our "
            "product actually does what the RFP asks for.\n\n"
            "Inputs:\n"
            "- The RFP text\n"
            "- The technical-fit skill (the canonical capability map)\n\n"
            "Output: a structured fit assessment:\n"
            "1. Requirements we meet fully\n"
            "2. Requirements we meet partially (and what's missing)\n"
            "3. Requirements we don't meet at all\n"
            "4. Overall fit score: high / medium / low\n"
            "5. The single most important risk to flag to the coordinator"
        ),
    },
    {
        "key": "competitive",
        "name": "Competitive Intel Analyst",
        "model": "claude-haiku-4-5",  # Cheaper for a quick analyst lookup; alias, never date-pinned
        "system": (
            "You are the Competitive Intel Analyst. You identify who else "
            "is likely competing for this RFP and how we should position.\n\n"
            "Inputs:\n"
            "- The RFP text\n"
            "- The competitive-intel skill (your battlecard library)\n\n"
            "Output:\n"
            "1. The 2-3 most likely competitors based on the RFP shape\n"
            "2. For each: their probable strengths and weaknesses on THIS deal\n"
            "3. Our two best positioning angles\n"
            "4. One trap to avoid"
        ),
    },
]


def main() -> None:
    client = get_client()

    # Reuse specialists from an earlier run when their IDs still resolve —
    # agents are persistent resources; re-creating them on every run litters
    # the workspace with duplicates and breaks the coordinator's version pins.
    saved: dict = {}
    ids_path = Path(".specialist_ids.json")
    if ids_path.exists():
        saved = json.loads(ids_path.read_text())

    specialist_ids: dict = {}
    for spec in SPECIALISTS:
        existing = saved.get(spec["key"])
        if existing:
            try:
                current = client.beta.agents.retrieve(existing)
                # Update in place so an edited prompt/model actually applies on
                # re-run. `skills` is omitted -> preserved (PATCH semantics), so
                # the skill attached by upload_skills.py stays put. Re-run
                # create_coordinator.py afterwards to re-pin the roster.
                client.beta.agents.update(
                    existing,
                    version=current.version,
                    model=spec["model"],
                    system=spec["system"],
                    tools=[{"type": "agent_toolset_20260401"}],
                )
                specialist_ids[spec["key"]] = existing
                print(f"  Updated {spec['name']:32s} -> {existing}")
                continue
            except anthropic.APIStatusError:
                print(f"  Saved ID for {spec['key']} is unreachable — creating a fresh one.")

        agent = client.beta.agents.create(
            name=spec["name"],
            model=spec["model"],
            system=spec["system"],
            tools=[{"type": "agent_toolset_20260401"}],
            metadata={
                "hackathon": "partner-basecamp-2026",
                "track": "specialist-swarm",
                "role": spec["key"],
            },
        )
        specialist_ids[spec["key"]] = agent.id
        print(f"  Created {spec['name']:32s} -> {agent.id}")

    # Preserve extra keys an earlier run may have added (e.g. the stretch critic)
    for k, v in saved.items():
        specialist_ids.setdefault(k, v)

    ids_path.write_text(json.dumps(specialist_ids, indent=2))
    print(f"\nSaved {len(specialist_ids)} specialist IDs to .specialist_ids.json")
    print("Next: python upload_skills.py")
    print("(changed a specialist after the coordinator exists? re-run "
          "create_coordinator.py afterwards — it re-pins the roster)")


if __name__ == "__main__":
    main()

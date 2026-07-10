"""
Upload each skill in skills/ via the Skills API and attach to the right
specialist agent.

Uses `files_from_dir` (from anthropic.lib) to package the skill directory.
Each skill bundle must contain a SKILL.md at its root with proper YAML
frontmatter (`name` and `description`).

Usage:
    python upload_skills.py
"""

import json
import secrets
from pathlib import Path

from anthropic import BadRequestError
from anthropic.lib import files_from_dir

from _common import get_client


# Map skill directory name → specialist key that should get it.
# One skill per specialist — that symmetry is the architecture story.
SKILL_TO_SPECIALIST = {
    "pricing-playbook":  "pricing",
    "legal-checklist":   "legal",
    "technical-fit":     "technical_fit",
    "competitive-intel": "competitive",
}


def main() -> None:
    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(specialist_ids_path.read_text())

    client = get_client()

    # Skill display_titles must be globally unique — including titles you can't
    # see in your own workspace's list (other teams, deleted skills). So bare
    # titles like "Pricing Playbook" collide in shared orgs. Each checkout gets
    # a stable random suffix: unique across teams, reusable across re-runs.
    suffix_path = Path(".skill_title_suffix")
    if suffix_path.exists():
        suffix = suffix_path.read_text().strip()
    else:
        suffix = secrets.token_hex(3)
        suffix_path.write_text(suffix)

    print(f"Checking for existing skills (title suffix: {suffix})...")
    existing_by_title: dict[str, str] = {}
    for item in client.beta.skills.list(source="custom"):
        existing_by_title[item.display_title] = item.id

    uploaded: dict[str, str] = {}

    for skill_name, specialist_key in SKILL_TO_SPECIALIST.items():
        skill_dir = Path("skills") / skill_name
        if not (skill_dir / "SKILL.md").exists():
            print(f"  Skipping {skill_name} — no SKILL.md found")
            continue

        display_title = f"{skill_name.replace('-', ' ').title()} {suffix}"

        # 1. Upload the skill (or reuse if one already exists with this title)
        if display_title in existing_by_title:
            skill_id = existing_by_title[display_title]
            print(f"Reusing existing skill: {skill_name} ({skill_id})")
            uploaded[skill_name] = skill_id
        else:
            print(f"Uploading skill: {skill_name}...")
            try:
                skill = client.beta.skills.create(
                    display_title=display_title,
                    files=files_from_dir(str(skill_dir)),
                )
            except BadRequestError as e:
                if "display_title" not in str(e):
                    raise
                # Title collides with a skill we can't see. New suffix, one retry.
                suffix = secrets.token_hex(3)
                suffix_path.write_text(suffix)
                display_title = f"{skill_name.replace('-', ' ').title()} {suffix}"
                print(f"  title collision — retrying with suffix {suffix}")
                skill = client.beta.skills.create(
                    display_title=display_title,
                    files=files_from_dir(str(skill_dir)),
                )
            uploaded[skill_name] = skill.id
            print(f"  -> {skill.id}")

        # 2. Attach to the matching specialist by updating its skills array
        specialist_id = specialist_ids[specialist_key]
        skill_id = uploaded[skill_name]
        print(f"  attaching to specialist `{specialist_key}` ({specialist_id})...")

        current = client.beta.agents.retrieve(specialist_id)

        # Avoid duplicate attachment on re-run. The SDK returns skill entries
        # as typed objects (dicts only on some versions) — handle both.
        def _skill_id_of(entry):
            if isinstance(entry, dict):
                return entry.get("skill_id")
            return getattr(entry, "skill_id", None)

        already_attached = any(
            _skill_id_of(s) == skill_id for s in (current.skills or [])
        )
        if already_attached:
            print(f"  already attached ✓ (skipping)")
            continue

        def _as_param(entry) -> dict:
            return entry if isinstance(entry, dict) else entry.model_dump(exclude_none=True)

        new_skills = [_as_param(s) for s in (current.skills or [])] + [
            {"type": "custom", "skill_id": skill_id, "version": "latest"}
        ]
        client.beta.agents.update(
            specialist_id,
            version=current.version,
            skills=new_skills,
        )
        print(f"  attached ✓")

    Path(".skill_ids.json").write_text(json.dumps(uploaded, indent=2))
    print(f"\nUploaded {len(uploaded)} skills and attached them to specialists.")
    print("Next: python create_coordinator.py")
    print("(order matters: the coordinator pins specialist versions at create time,")
    print(" so skills must be attached BEFORE the coordinator exists)")


if __name__ == "__main__":
    main()

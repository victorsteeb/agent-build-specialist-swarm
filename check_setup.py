"""
Run this FIRST — before anything else in this repo.

It verifies, in order:
  1. Dependencies (installs the anthropic SDK if missing — survives locked-down Pythons)
  2. Your API key (.env or shell variable), with a live 1-token ping
  3. The SDK is new enough for Managed Agents
  4. Your workspace has multi-agent access — the research-preview gate this track needs
  5. Any saved resource IDs from earlier runs still point at real resources

Usage:
    python check_setup.py            # run all checks
    python check_setup.py --reset    # delete LOCAL state files (never remote resources)
"""

# ── 1. Dependencies — safe to re-run; survives PEP 668 / no-admin Pythons ──
import importlib.util, subprocess, sys


def _ensure_packages(requirements):
    """requirements: list of (import_name, pip_spec). Install only what is missing,
    into the running interpreter. Tries a normal install, then user-space, then a
    PEP 668 override. Pip output is captured, not streamed; only if every strategy
    fails does it surface the reason, with the venv fix instead of a traceback."""
    missing = [pip for mod, pip in requirements if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    print("Installing " + ", ".join(missing) + " — first run only, please wait…", flush=True)
    base = [sys.executable, "-m", "pip", "install", "-q"]
    last = None
    for extra in ([], ["--user"], ["--user", "--break-system-packages"], ["--break-system-packages"]):
        last = subprocess.run(base + extra + missing, capture_output=True, text=True)
        if last.returncode == 0:
            return
    pip_said = (last.stderr or last.stdout or "").strip().splitlines() if last else []
    tail = "\n      ".join(pip_said[-3:]) if pip_said else "(no output from pip)"
    raise SystemExit(
        "\n  Couldn't install: " + ", ".join(missing) + "\n"
        "  This Python is locked down (PEP 668) or offline. Quickest fix is a venv:\n"
        f"      {sys.executable} -m venv .venv\n"
        "      source .venv/bin/activate          # Windows: see SETUP.md\n"
        f"      pip install {' '.join(missing)}\n"
        "  Corporate proxy or PyPI blocked? See SETUP.md in the repo root.\n"
        f"  (pip said: {tail})\n"
    )


_ensure_packages([("anthropic", "anthropic")])
print("✓ Dependencies ready")

import json
from pathlib import Path

STATE_FILES = [
    ".environment_id",
    ".specialist_ids.json",
    ".skill_ids.json",
    ".coordinator_id",
    ".last_session_id",
    ".skill_title_suffix",
]

PROBE_NAME = "preflight-multiagent-probe"


def do_reset():
    removed = []
    for f in STATE_FILES:
        p = Path(f)
        if p.exists():
            p.unlink()
            removed.append(f)
    if removed:
        print("Removed local state files: " + ", ".join(removed))
        print("(Remote agents/environments/skills are untouched — new runs will "
              "reuse or recreate what they need.)")
    else:
        print("No local state files to remove.")


def main():
    if "--reset" in sys.argv:
        do_reset()
        return

    import anthropic
    from _common import get_client, load_env

    failures = 0

    # ── 2. API key + live ping ──
    key = load_env()
    ping = anthropic.Anthropic(api_key=key, timeout=30.0, max_retries=1)
    try:
        ping.messages.create(
            model="claude-haiku-4-5", max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
    except anthropic.AuthenticationError:
        raise SystemExit(
            "✗ That key was rejected. Open .env and paste the whole key "
            "(it starts with sk-ant-), then re-run."
        )
    except Exception as exc:
        raise SystemExit(
            f"✗ Could not reach the Claude API ({type(exc).__name__}). "
            "Check your connection / proxy (SETUP.md), then re-run."
        )
    print("✓ API key verified — any error after this is not the API key")

    client = get_client()

    # ── 3. SDK surfaces ──
    needed = ("agents", "sessions", "environments", "skills")
    missing = [s for s in needed if not hasattr(client.beta, s)]
    if missing:
        raise SystemExit(
            f"✗ Your anthropic SDK ({anthropic.__version__}) is too old — "
            f"missing client.beta.{missing[0]}.\n"
            "  Fix: pip install -U 'anthropic>=0.116.0'"
        )
    print(f"✓ SDK has the Managed Agents surfaces (anthropic {anthropic.__version__})")

    # ── 4. Multi-agent access (the gate this track lives behind) ──
    # One tiny probe agent per workspace, ever: agents can't be deleted, so we
    # get-or-create by name instead of creating per run.
    try:
        probe = next((a for a in client.beta.agents.list() if a.name == PROBE_NAME), None)
        if probe is None:
            client.beta.agents.create(
                name=PROBE_NAME,
                model="claude-haiku-4-5",
                system="Workspace preflight probe. Never used in sessions.",
                multiagent={"type": "coordinator", "agents": [{"type": "self"}]},
                metadata={"purpose": "preflight"},
            )
        print("✓ Multi-agent access confirmed for this workspace")
    except (anthropic.BadRequestError, anthropic.PermissionDeniedError) as e:
        failures += 1
        print("✗ This workspace does NOT appear to have multi-agent (research preview) access.")
        print(f"    API said: {e}")
        print("    Ask whoever owns your workspace to request the preview, or see")
        print("    TROUBLESHOOTING.md → 'No multi-agent access' for the manual fallback.")

    # ── 5. Saved state from earlier runs ──
    def check_id(label, retrieve, res_id, fix):
        nonlocal failures
        try:
            retrieve(res_id)
            print(f"✓ {label} is reachable ({res_id[:18]}…)")
        except Exception:
            failures += 1
            print(f"✗ {label} points at a resource this key can't see ({res_id[:18]}…).")
            print(f"    Fix: {fix}  (or `python check_setup.py --reset` to clear all local state)")

    if Path(".environment_id").exists():
        check_id("Saved environment", lambda i: client.beta.environments.retrieve(i),
                 Path(".environment_id").read_text().strip(),
                 "delete .environment_id and re-run setup_environment.py")
    if Path(".coordinator_id").exists():
        check_id("Saved coordinator", lambda i: client.beta.agents.retrieve(i),
                 Path(".coordinator_id").read_text().strip(),
                 "delete .coordinator_id and re-run create_coordinator.py")
    if Path(".specialist_ids.json").exists():
        for k, v in json.loads(Path(".specialist_ids.json").read_text()).items():
            check_id(f"Saved specialist '{k}'", lambda i: client.beta.agents.retrieve(i), v,
                     "delete .specialist_ids.json and re-run create_specialists.py")
    if Path(".skill_ids.json").exists():
        for k, v in json.loads(Path(".skill_ids.json").read_text()).items():
            check_id(f"Saved skill '{k}'", lambda i: client.beta.skills.retrieve(i), v,
                     "delete .skill_ids.json and re-run upload_skills.py")

    print()
    if failures:
        raise SystemExit(f"{failures} check(s) failed — fix the ✗ items above, then re-run.")
    print("All checks passed. Build order: setup_environment.py → create_specialists.py "
          "→ upload_skills.py → create_coordinator.py → run_deal_desk.py")


if __name__ == "__main__":
    main()

"""
Shared helpers for this exercise: API-key loading, client construction, and a
hardened session driver. The same file ships in every agent-build repo.

Nothing here is exercise content — it exists so that when something goes
wrong, you get a next step instead of a traceback.
"""

import os
import pathlib
import sys
import time

import anthropic
from anthropic import Anthropic

# Windows consoles default to cp1252; streamed agent output routinely contains
# characters outside it (→, ✓, box-drawing), which crashes the run mid-stream on
# a plain print(). Force UTF-8 for every script that imports this module. (File
# writes pass encoding="utf-8" explicitly — this only covers stdout/stderr.)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


_ENV_TEMPLATE = (
    "# Paste your Anthropic API key after the = (no quotes, no spaces), then save\n"
    "# and re-run. Get a key at https://console.anthropic.com/\n"
    "# This file is gitignored — your key is never committed.\n"
    "ANTHROPIC_API_KEY=paste-your-key-here\n"
)


def _resolve_env_file():
    """Find a .env walking up from the working directory, so one repo-root
    .env serves every script. If none exists, target the repo root."""
    here = pathlib.Path.cwd().resolve()
    for d in [here, *here.parents]:
        if (d / ".env").is_file():
            return d / ".env"
    root = next(
        (d for d in [here, *here.parents] if (d / ".git").exists() or (d / "SETUP.md").exists()),
        here,
    )
    return root / ".env"


def load_env():
    """Resolve the API key. A real shell variable wins; otherwise read .env
    (created from a template on first run). Exits with the exact next step
    when no key is available. Exports the key so the SDK picks it up."""
    shell = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if shell.startswith("sk-ant-"):
        return shell

    env_file = _resolve_env_file()
    if not env_file.exists():
        env_file.write_text(_ENV_TEMPLATE)
        raise SystemExit(
            f"\nCreated {env_file}\n"
            "Open it, paste your key after ANTHROPIC_API_KEY=, save, then re-run this script."
        )

    file_vals = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            file_vals[k.strip()] = v.strip().strip('"').strip("'")

    key = file_vals.get("ANTHROPIC_API_KEY", "").strip()
    if not key.startswith("sk-ant-"):
        raise SystemExit(
            f"\nNo API key yet. Open {env_file}, paste your key after "
            "ANTHROPIC_API_KEY= (it starts with sk-ant-), save, then re-run."
        )
    os.environ["ANTHROPIC_API_KEY"] = key
    return key


def get_client():
    """Client with the key loaded. No extra headers needed — the SDK sets the
    managed-agents beta header on every client.beta.* call by itself."""
    load_env()
    return Anthropic()


def read_id(path, hint):
    """Read a saved resource ID, or exit telling the participant what to run."""
    p = pathlib.Path(path)
    if not p.exists():
        raise SystemExit(f"Missing {path}. {hint}")
    return p.read_text().strip()


def console_url(session_id):
    return (
        f"https://platform.claude.com/workspaces/default/sessions/{session_id}"
        "\n  (swap 'default' for your workspace ID if your key lives elsewhere)"
    )


def create_session_or_explain(client, dotfiles, **kwargs):
    """sessions.create with a guided error when saved IDs have gone stale —
    the classic case: dot-files from an earlier run, a deleted resource, or a
    key from a different workspace."""
    try:
        return client.beta.sessions.create(**kwargs)
    except (anthropic.NotFoundError, anthropic.PermissionDeniedError, anthropic.BadRequestError) as e:
        raise SystemExit(
            "\nCould not start the session. Most likely a saved ID points at a "
            "resource this API key can't see (deleted, or created in another "
            "workspace).\n"
            f"  API said: {e}\n"
            f"  Fix: delete {', '.join(dotfiles)} and re-run the create script(s),\n"
            "  or run `python check_setup.py` to validate every saved ID.\n"
            "  (TROUBLESHOOTING.md → 'Stale state files')"
        )


def _error_text(event):
    err = getattr(event, "error", None)
    if err is None:
        return str(event)
    return getattr(err, "message", None) or str(err)


def _print_run_stats(client, session, elapsed_s):
    """Wall-clock + token readout so a team can see the number their lens moves
    (cost = tokens, speed = seconds). Best-effort: a stats hiccup never breaks
    the run. Shows the score; it does not compute a verdict (that is the
    participant's call to argue)."""
    parts = [f"{elapsed_s:.0f}s ({elapsed_s / 60:.1f} min)"]
    try:
        u = client.beta.sessions.retrieve(session.id).usage
        inp, out = u.input_tokens or 0, u.output_tokens or 0
        cache = u.cache_read_input_tokens or 0
        parts.append(f"{inp + out:,} tokens (in {inp:,} / out {out:,}; {cache:,} cache-read)")
    except Exception:
        parts.append("token usage unavailable - see the Console trace")
    print(f"\n[run stats] {' | '.join(parts)}", flush=True)


def drive_session(client, session, kickoff_events, on_event, timeout_s=600):
    """Run one turn of a session, correctly.

    - Opens the event stream BEFORE sending (send-then-stream misses events).
    - Prints the session ID and Console URL up front, so a hung or failed
      session is always diagnosable.
    - Ends on: idle with a terminal stop_reason (normal), terminated (error
      exit), or session.error (error exit with the message).
    - After timeout_s without finishing, prints a reminder that the session is
      still running and where to watch it. Ctrl-C here is safe — the session
      keeps running server-side; re-fetch results from the Console.
    """
    url = console_url(session.id)
    print(f"Session: {session.id}")
    print(f"Watch it live: {url}\n")

    t0 = time.monotonic()
    reminder_at = t0 + timeout_s
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(session.id, events=kickoff_events)
        for event in stream:
            on_event(event)
            et = event.type
            if et == "session.error":
                print(f"\n[session error] {_error_text(event)}")
                print(f"Full trace: {url}")
                raise SystemExit(1)
            if et == "session.status_terminated":
                print("\n[session terminated before finishing]")
                print(f"Full trace: {url}")
                raise SystemExit(1)
            if et == "session.status_idle":
                stop = getattr(event, "stop_reason", None)
                if getattr(stop, "type", None) == "requires_action":
                    continue  # transient idle — the agent is waiting, keep listening
                _print_run_stats(client, session, time.monotonic() - t0)
                return  # normal completion
            if time.monotonic() > reminder_at:
                print(
                    f"\n[still running after {timeout_s}s — that can be normal for a big build."
                    f"\n Watch it live: {url}"
                    "\n Ctrl-C here is safe; the session keeps running server-side.]\n"
                )
                reminder_at = time.monotonic() + timeout_s

"""
Verify the deliverable the swarm produced — run this AFTER run_deal_desk.py.

The habit this enforces (straight out of Anthropic's "Building Effective Agents"):
a pipeline that RAN is not a deliverable that's RIGHT. Before you present, you
check the output against acceptance criteria. This script is that check — and it
is deliberately dumb: no API call, no second model, no network. Just a fast local
read of outputs/proposal-response.docx.

It is built NOT to box you in. Three layers, loosest to tightest:

  • THE FLOOR (always gates, scenario-agnostic): the deliverable exists, has real
    content, and actually assembled a structured document. This is "did the swarm
    produce a deliverable at all" — true for the wired Deal Desk or any build you
    invent. A custom build can NEVER hard-fail just for being custom.

  • YOUR CRITERIA (gates, only if you write them): drop an `acceptance.txt` next to
    this script — one criterion per line — and the check grades YOUR build against
    YOUR bar. This is the point: adapt the scenario, define what "good" means for
    it, and the harness comes with you. Format at the bottom of this file.

  • THE WIRED GRADE (advisory, only for the shipped Acme scenario): if you're still
    running the wired RFP, you also get the Deal Desk "Great when" bar graded for
    free (past wins cited, 99.99% SLA handled honestly, no overpromise). These are
    keyword heuristics on prose — a ✗ means "go read that section," not "you failed."
    They never gate, and they go quiet the moment you adapt the scenario.

Want a real critique instead of a keyword scan? That's the Critic sub-agent stretch
(stretch_critic_subagent.py) — a second LLM pass. This is the floor; that's the ceiling.

Usage:
    python check_deliverable.py
    python check_deliverable.py path/to/other.docx
"""

import re
import sys
import zipfile
from pathlib import Path

DELIVERABLE = Path("outputs/proposal-response.docx")
ACCEPTANCE = Path("acceptance.txt")
WIRED_RFP = Path("synthetic-data/rfp-acme-corp.md")

# --- wired-scenario reference (only used when the shipped Acme RFP is in play) ---
PAST_WINS = ["Globex", "Initech Sensors", "Stark Industries", "Wayne", "Pied Piper"]
CLOSEST_LOOKALIKE = "Initech Sensors"
SECTIONS = {
    "Executive summary": ["executive summary", "exec summary"],
    "Understanding of need": ["understanding", "your need", "customer need", "what you", "requirements overview"],
    "Why we're the fit": ["why we", "our fit", "the right fit", "why northwind", "our strengths"],
    "Commercial proposal": ["commercial", "pricing", "discount", "payment terms"],
    "Contract approach": ["contract", "legal", "liability", "terms and conditions", "red-line", "redline"],
    "Risks": ["risk", "mitigat"],
}


def extract_text(path: Path) -> str:
    """Plain text from a .docx (a zip of XML) with no third-party deps. Falls back
    to reading the raw file if it isn't a valid docx, so a coordinator that saved
    markdown-in-a-.docx still gets graded rather than crashing the check."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml)
    except (zipfile.BadZipFile, KeyError):
        return path.read_text(errors="ignore")


def _has(text_lc, *needles):
    return any(n.lower() in text_lc for n in needles)


def load_criteria():
    """Parse acceptance.txt into criteria, or None if the team hasn't written one.

    One criterion per line. Blank lines and #-comments ignored.
      plain text     -> the deliverable MUST contain it (case-insensitive substring)
      /regex/        -> the deliverable MUST match this regex (case-insensitive)
      leading "!"    -> negate: e.g. "!perfect fit" or "!/re/" means MUST NOT contain / match
    """
    if not ACCEPTANCE.exists():
        return None
    crits = []
    for raw in ACCEPTANCE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        if negate:
            line = line[1:].strip()
        is_regex = len(line) >= 2 and line.startswith("/") and line.endswith("/")
        pattern = line[1:-1] if is_regex else line
        crits.append({"raw": raw.strip(), "negate": negate, "regex": is_regex, "pattern": pattern})
    return crits


def check_criterion(text, text_lc, c):
    if c["regex"]:
        try:
            found = re.search(c["pattern"], text, re.IGNORECASE) is not None
        except re.error as e:
            return None, f"bad regex: {e}"
    else:
        found = c["pattern"].lower() in text_lc
    ok = (not found) if c["negate"] else found
    return ok, None


def _staleness_warning(output_path):
    """If .last_session_id (stamped when run_deal_desk starts a session) is newer
    than the deliverable, the most recent run didn't produce this docx — it likely
    errored before the download. Grading a leftover from an earlier run reports a
    misleading PASS, so flag it."""
    marker = Path(".last_session_id")
    try:
        if marker.exists() and output_path.exists():
            if marker.stat().st_mtime > output_path.stat().st_mtime + 2:
                return (f"⚠ STALE: {output_path} is older than your last session — "
                        "the latest run may have errored before downloading it. "
                        "Re-run run_deal_desk.py to grade THIS session.")
    except OSError:
        pass
    return None


def is_wired_scenario() -> bool:
    """True only if the shipped Acme RFP is still the input — i.e. you haven't
    swapped synthetic-data/ for your own scenario."""
    try:
        return WIRED_RFP.exists() and "acme corp" in WIRED_RFP.read_text().lower()
    except OSError:
        return False


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DELIVERABLE

    # ── THE FLOOR (scenario-agnostic, gates) ─────────────────────────────────
    if not path.exists():
        raise SystemExit(
            f"✗ No deliverable at {path}\n"
            "  Run `python run_deal_desk.py` first — the swarm has to produce the\n"
            "  document before there's anything to check. (Already ran it? It may\n"
            "  still be indexing — retry `python download_deliverable.py`.)"
        )
    text = extract_text(path)
    text_lc = text.lower()
    nonblank = [ln for ln in text.splitlines() if ln.strip()]
    if len(text.strip()) < 200 or len(nonblank) < 4:
        raise SystemExit(
            f"✗ {path} exists but isn't a real deliverable "
            f"({len(text.strip())} chars, {len(nonblank)} lines).\n"
            "  Looks like a stub, or the content was saved somewhere other than\n"
            "  /mnt/session/outputs/. Open the Console trace from the run and check."
        )

    stale = _staleness_warning(path)
    print(f"Checking {path}  ({len(text.strip())} chars, {len(nonblank)} lines)\n")
    print("FLOOR — is there a real, assembled deliverable?")
    print("  ✓ Exists, has content, and assembled a structured document")
    if stale:
        print(f"  {stale}")
    print()

    gate_failures = 0

    # ── YOUR CRITERIA (gates, only if acceptance.txt exists) ─────────────────
    criteria = load_criteria()
    if criteria is not None:
        print(f"YOUR CRITERIA — from acceptance.txt ({len(criteria)} defined):")
        if not criteria:
            print("  (acceptance.txt is present but empty — add one criterion per line)")
        for c in criteria:
            ok, err = check_criterion(text, text_lc, c)
            if err:
                print(f"  ⚠ {c['raw']}   ({err})")
                continue
            kind = "must NOT contain" if c["negate"] else "must contain"
            print(f"  {'✓' if ok else '✗'} [{kind}] {c['raw']}")
            if not ok:
                gate_failures += 1
        print()

    # ── THE WIRED GRADE (advisory, only for the shipped Acme scenario) ────────
    if is_wired_scenario():
        present = [n for n, kws in SECTIONS.items() if _has(text_lc, *kws)]
        print("WIRED GRADE — the Deal Desk 'Great when' bar (advisory, no gate):")
        print(f"  · Sections assembled: {len(present)}/6 "
              f"({', '.join(present) if present else 'none detected'})")

        cited = [w for w in PAST_WINS if w.lower() in text_lc]
        if cited:
            extra = "  ← closest Acme look-alike" if CLOSEST_LOOKALIKE in cited else ""
            print(f"  ✓ Cites past wins by name: {', '.join(cited)}{extra}")
            if CLOSEST_LOOKALIKE not in cited:
                print(f"    ⚠ ...but not {CLOSEST_LOOKALIKE}, the closest look-alike — a stronger swarm reaches for it.")
        else:
            print("  ✗ No past win cited by name (Initech Sensors is the closest comparable).")

        sla_mentioned = _has(text_lc, "99.99")
        sla_honest = sla_mentioned and _has(
            text_lc, "add-on", "add on", "premium", "custom", "bespoke", "additional",
            "not standard", "not our standard", "upgrade", "priced", "active-active",
        )
        if sla_honest:
            print("  ✓ Handles the 99.99% SLA honestly (a priced add-on, not the standard tier)")
        elif sla_mentioned:
            print("  ✗ Mentions 99.99% SLA but doesn't flag it as an add-on — standard is 99.95%.")
        else:
            print("  ✗ Doesn't address the 99.99% SLA — a headline Acme requirement and a known gap.")

        overpromises = [p for p in (
            "meets all requirements", "fully meets all", "perfect fit", "100% fit",
            "exceeds all", "guarantees 99.99", "guarantee 99.99", "no gaps",
            "fully compliant with all",
        ) if p in text_lc]
        if overpromises:
            print(f"  ⚠ Possible overpromise language: {', '.join(overpromises)}")
        else:
            print("  ✓ No blanket overpromise phrases detected")
        print("  (Advisory only — the lever is a prompt or a skill, never the data. "
              "Changed a specialist? re-run create_coordinator.py.)")
        print()
    elif criteria is None:
        # Adapted scenario AND no acceptance.txt — don't invent a bar, teach them to.
        print("ADAPTED SCENARIO — the wired Acme checks don't apply to your build.")
        print("  Define what 'good' means for YOUR deliverable: create acceptance.txt")
        print("  next to this script, one criterion per line, e.g.:")
        print("      # a risk memo for the M&A variant")
        print("      Executive summary")
        print("      /change[- ]of[- ]control/")
        print("      !perfect fit          # must NOT overpromise")
        print("  Then re-run — the check grades your build against your bar.")
        print()

    # ── VERDICT ──────────────────────────────────────────────────────────────
    if gate_failures:
        raise SystemExit(
            f"✗ {gate_failures} of your acceptance criteria failed. Reopen the "
            "section each one points at — the lever is a prompt or a skill, then "
            "re-run create_coordinator.py → run_deal_desk.py → check_deliverable.py."
        )
    print("✓ PASSED — a real deliverable, and it meets the bar in play.")
    if stale:
        print("  ⚠ ...but you graded a STALE file — re-run run_deal_desk.py to grade THIS session.")
    if criteria is None and is_wired_scenario():
        print("  (Read the advisory WIRED GRADE above for what to tighten before Drive Value.)")


if __name__ == "__main__":
    main()

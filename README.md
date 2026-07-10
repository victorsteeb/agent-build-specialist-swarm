# Track 3 — Specialist Swarm

You build a **coordinator agent** that fans an inbound RFP out to four **specialist sub-agents** — each carrying its own **skill** — and synthesises their work into a real branded Word document. It's the coordinator-plus-specialists shape every services firm runs on, made concrete: drop an RFP in, watch four specialists answer in parallel on the events stream, get `proposal-response.docx` out.

**Start with [`BRIEF.md`](./BRIEF.md)** — the scenario, the numbered build, the 40-minute plan, and the demo.

## Step 0 — run this first

```bash
python check_setup.py
```

It verifies your dependencies, API key, SDK version, **whether your workspace has multi-agent access** (a research preview this track needs), and any saved state from earlier runs. Green across the board means you're clear to build. If it flags something, it prints the fix — and [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) has the details, including a manual fallback if multi-agent access isn't granted.

Key setup, venvs, and corporate proxies → [`SETUP.md`](./SETUP.md).

## How to run

Work the exercise in the repo — run the scripts, don't paste code out of a chat window. The build is five scripts in a fixed order (`BRIEF.md` has the details); each one is safe to re-run.

### VS Code / Cursor (recommended)
1. **File → Open Folder** and select this folder.
2. Install the **Python** extension if prompted, and set up a virtual environment (see `SETUP.md`).
3. In the integrated terminal: `python check_setup.py`, then run the five build scripts in order.

### Claude Code (CLI)
`cd` into this folder and either run the scripts yourself or pair with Claude Code to drive and debug them — it reads [`CLAUDE.md`](./CLAUDE.md) for how to help.

```bash
cd agent-build-specialist-swarm
python check_setup.py
claude                      # …or work the exercise with Claude Code as your pair
```

### Claude Desktop
Keep it open alongside as your AI pair — ask it to explain an event, debug an error, or suggest the next prompt change while you edit.

## What's in this folder

```
agent-build-specialist-swarm/
├── README.md                       (you are here)
├── BRIEF.md                        (the exercise — read this first)
├── TROUBLESHOOTING.md              (failure catalog + fixes)
├── CLAUDE.md                       (coaching notes for Claude Code)
├── SETUP.md                        (key, venv, proxy, no-admin)
├── stretch-goals.md                (push-further menu)
├── requirements.txt
├── check_setup.py                  (step 0 — verify key, SDK, multi-agent access, saved state)
├── _common.py                      (shared helpers: key loading, client, session driver)
├── setup_environment.py            (step 1 — cloud environment, get-or-create)
├── create_specialists.py           (step 2 — the four sub-agents, idempotent)
├── upload_skills.py                (step 3 — Skills API upload + attach, idempotent)
├── create_coordinator.py           (step 4 — Senior Partner + roster + docx skill; re-run to re-pin)
├── run_deal_desk.py                (step 5 — run the swarm, stream events, download outputs)
├── download_deliverable.py         (re-fetch outputs from any past session)
├── stretch_critic_subagent.py      (stretch: a critic agent that reviews the draft)
├── skills/                         (custom skills — one per specialist)
│   ├── pricing-playbook/SKILL.md
│   ├── legal-checklist/SKILL.md
│   ├── technical-fit/SKILL.md
│   └── competitive-intel/SKILL.md
└── synthetic-data/
    ├── rfp-acme-corp.md            (the RFP that triggers the swarm)
    ├── past-wins.json              (inlined into the kickoff; the Pricing specialist cites it)
    └── product-overview.md         (the source the technical-fit skill was built from)
```

## Rules of the data

All fictional. Acme Corp, the past wins, the competitor battlecards, the product capabilities — none of it maps to anything real. Don't add real customer or firm data to your checkout.

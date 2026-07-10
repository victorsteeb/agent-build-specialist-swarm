# Track 3 — Specialist Swarm (build brief)

**Concept landed:** Skills, sub-agents & orchestration
**Tech:** [Claude Managed Agents multi-agent](https://platform.claude.com/docs/en/managed-agents/multi-agent) + [custom Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) + the pre-built [docx skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/quickstart)
**Build window:** ~40 minutes on the clock
**Output:** A coordinator agent that fans work out to specialist sub-agents, each with its own skill, assembling a real branded Word document.

## The shape you're building

This is the architecture that wins the next $50M transformation deal: **coordinator + specialists + skills**. It maps directly to how every services firm structures real work. A senior partner orchestrates; specialists (legal, pricing, technical) own their lanes; the senior partner synthesises and delivers.

You're going to build exactly that around a Deal Desk scenario. Drop an RFP in, get a branded response doc out, and watch the parallelism happen live on the events stream. **The visible fan-out is the demo** — four specialist threads spawning at once, then their answers flowing back into one document.

Two working agents beat five broken ones. Get the coordinator and one specialist handing off cleanly before you scale the roster.

## Step 0 — before you build anything

```bash
python check_setup.py
```

This is the gate. It verifies your dependencies, your API key (with a live ping), your SDK version, and — the one that matters for this track — **whether your workspace has multi-agent access** (it's a research preview). It also validates any saved state from an earlier run.

No more "confirm with your facilitator that your team has access." The probe answers that question in about 30 seconds. If it comes back green, you're clear to build. If multi-agent access fails, `check_setup.py` tells you exactly what to do, and [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) → **No multi-agent access** has a 5-line manual fallback so you can still finish the exercise.

Key setup, venvs, corporate proxies → [`SETUP.md`](./SETUP.md).

## The scenario — Deal Desk

An inbound RFP has landed. Your swarm turns it into a branded proposal response.

**Coordinator — "Senior Partner, Deal Desk Lead"** (runs on Opus)
Reads the RFP, delegates to the specialists in parallel, synthesises their outputs, and produces the final Word document using the pre-built **docx skill**.

**Four specialists — one skill each** (Sonnet, except the analyst on Haiku for a cheap lookup):

| Specialist | Skill | Owns |
| --- | --- | --- |
| Pricing Specialist | `pricing-playbook` | Commercial terms from the RFP scope and past wins |
| Legal Reviewer | `legal-checklist` | Flags risky RFP requirements, recommends contract positions |
| Technical Fit Specialist | `technical-fit` | Whether the product actually covers the RFP's requirements |
| Competitive Intel Analyst | `competitive-intel` | Who else is likely in the deal and how to position |

That one-skill-per-specialist symmetry **is** the architecture story: each lane has its own codified playbook, and the coordinator never has to hold all four in its head at once.

**The trigger:** [`synthetic-data/rfp-acme-corp.md`](./synthetic-data/rfp-acme-corp.md) — Acme Corp wants an enterprise data platform. The RFP is deliberately spicy: it demands an MFN clause, uncapped breach liability, a 35% discount, Net 90 terms, and a 99.99% SLA. Those are exactly the things your specialists' skills have opinions about — so the swarm has something real to say.

**The deliverable:** a branded Word document at `outputs/proposal-response.docx`.

> **The one rule that bites:** agents can only hand files back to you from `/mnt/session/outputs/` inside the container. A deliverable written anywhere else is unreachable after the session ends. The kickoff prompt already tells the coordinator this — keep it if you rewrite the prompt.

## Core build — run in THIS order

The order is not optional. **The coordinator pins each specialist's version when it is created**, so skills must be attached to the specialists *before* the coordinator exists. Coordinator-before-skills means your specialists silently run without their skills.

1. **Create the environment.** `python setup_environment.py` — the cloud container the sessions run in. Safe to re-run; reuses an existing environment by name.

2. **Create the specialists.** `python create_specialists.py` — the four sub-agents. IDs saved to `.specialist_ids.json`. Idempotent: re-running reuses them, never duplicates.

3. **Upload and attach the skills.** `python upload_skills.py` — packages each folder in `skills/` via the Skills API and attaches it to the matching specialist. Idempotent on re-run. (Skill titles get an automatic per-checkout suffix so they don't collide with other teams on a shared workspace — see [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) if you're curious.)

4. **Create the coordinator.** `python create_coordinator.py` — the Senior Partner, with the four specialists in its `multiagent` roster and the **docx skill** attached (that's what turns the synthesis into a real Word document, not markdown in chat).

5. **Run the deal.** `python run_deal_desk.py` — inlines the RFP and `past-wins.json` into the kickoff message, streams the events so you can watch the parallel thread fan-out, and downloads everything the swarm saved to `/mnt/session/outputs/` into `outputs/`.

By the end you have `outputs/proposal-response.docx`, generated by a coordinator plus specialists who each used their own skill.

> **The #1 recovery move — memorise it.** Changed a specialist after the coordinator already exists (new prompt, new model, a skill just attached)? **Re-run `python create_coordinator.py`.** It updates the coordinator in place and re-pins the roster to the specialists' current versions. If your specialists seem to be ignoring their skills, this is almost always why — the coordinator is pointing at a stale version from before the skills were attached.

## The 40 minutes

- **0–10 — wiring.** `check_setup.py`, then the five scripts in order. Get the docx out *once*, exactly as shipped, before you change a thing. A working baseline is worth more than a clever half-build.
- **10–30 — build.** Iterate on what the run actually produces. Your knobs are the **prompts** (the specialist system prompts in `create_specialists.py`, the coordinator prompt in `create_coordinator.py`) and the **skills** (the SKILL.md files). Change a specialist → re-run `create_coordinator.py` → re-run the deal. Cut scope before you cut the demo: two specialists handing off cleanly beats four wired badly.
- **30–40 — lock the demo.** One clean end-to-end run. Events stream scrolling in one window, `proposal-response.docx` open in another.

## Done when / Great when

**Done when:** `outputs/proposal-response.docx` exists, and the events stream showed **four specialist threads spawn and run in parallel** before the coordinator synthesised them.

**Great when:**
- Every section of the document traces back to a specialist's contribution — you can point at the commercial section and say "that's Pricing," at the risk section and say "that's Legal."
- The commercial section **cites specific past wins** from `past-wins.json` by name (Initech Sensors is the closest Acme look-alike in there — a strong swarm finds it).
- Technical Fit **flags the honest gaps** from its skill rather than claiming a perfect fit — the 99.99% SLA Acme demands is a priced add-on, not the standard tier, and sub-100ms real-time isn't our best ground. A proposal that quietly promises everything is a proposal that loses on the reference call.

## Two-minute demo

Two-monitor setup:
- **Monitor 1 — the events stream.** You'll see `session.thread_created` × 4, the threads running in parallel, then `agent.thread_message_received` flowing back as each specialist reports in. Narrate it live: "four specialists, parallel, one synthesis." The visible parallelism IS the demo.
- **Monitor 2 — `outputs/proposal-response.docx`, open.** A real branded document, ready to send.

Every session prints its ID and a Console trace URL when it starts — drop that on screen too if you want to show the full sub-agent threads.

## Take-home — what you show your practice lead

Two artifacts:
1. **`outputs/proposal-response.docx`** — the document the swarm wrote from an RFP it had never seen, with each section owned by a different specialist and its own playbook.
2. **A screenshot of the parallel fan-out** on the events stream — the four threads spawning at once.

The line that lands: *"I dropped in an RFP and four specialists answered in parallel, each with its own codified playbook, and the senior-partner agent assembled the proposal. This is the shape of every deal desk, diligence team, and onboarding function we sell into."*

## Make it your own

The Deal Desk is the wired scenario, but the pattern — a coordinator plus 3–5 specialists, each carrying one skill — is the reusable part. To adapt it, you author your own `synthetic-data/` inputs and your own `skills/`, then re-point the specialist prompts. Two starters that map cleanly to services work:

- **M&A Diligence Lite.** Coordinator = M&A Lead reading a deal memo and data room. Specialists: Financial Analyst (flags financial concerns), Legal Diligence (change-of-control, IP, litigation), Tech Stack Assessor (technical debt, integration complexity), People & Culture (leadership and retention risk). Deliverable: a structured risk-and-recommendation memo. *Best for a senior-partner audience — it has gravitas.*
- **Hire-to-Onboard Orchestrator.** Coordinator = Onboarding Lead taking a new-hire profile and start date. Specialists: Recruiter (offer terms, references), IT Provisioning (laptop + accounts checklist), Onboarding Buddy Match (picks a buddy by team and seniority), Welcome Packet (personalised content). Deliverable: a day-1 readiness pack. *Best if your clients live in HR / people-ops.*

Neither ships with data — that authoring *is* the adaptation exercise, and it's the fastest way to prove the pattern transfers to your own book of work. Best of all: swap in a real deal shape from an account you know.

## Stretch goals

Want to push further? [`stretch-goals.md`](./stretch-goals.md) has the menu — codify *your* firm's voice as a skill, add a Critic sub-agent that reviews the draft before it ships, give the coordinator memory across deals, or have the swarm grade its own deliverable against a rubric (Outcomes).

## Rules of the data

All fictional. Acme Corp, the past wins, the competitor battlecards, the product capabilities — none of it maps to a real company or a real product. Don't add real customer or firm data to your checkout.

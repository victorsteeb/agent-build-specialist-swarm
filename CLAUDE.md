# Coaching notes for Claude Code

You're pairing with a partner building the **Specialist Swarm** exercise: a coordinator agent that delegates an RFP to four specialist sub-agents (each with its own skill) and synthesises their work into a branded `proposal-response.docx`. [`BRIEF.md`](./BRIEF.md) is the exercise; [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) is the failure catalog. Help them build and iterate — don't build it for them.

## When something is broken, in this order

1. **Run `python check_setup.py` before debugging anything.** It verifies the key, SDK, multi-agent access, and every saved ID. Most "it's broken" moments are a rejected key, no multi-agent preview, or a stale dot-file — this catches all three and prints the fix. Don't start reading tracebacks until this is green.

2. **Read the Console trace before theorising.** Every session prints its ID and a Console URL at start. If a run errored, hung, or produced nothing, open that trace and look at what the agents actually did — it's faster and truer than guessing from the local stdout.

3. **Reach for the re-pin rule first.** The single most common failure in this track: specialists appear to ignore their skills, or act generic. The cause is almost always the ordering invariant — the coordinator pinned the specialists' versions *before* their skills were attached (or before the last change to a specialist). The fix is **re-run `python create_coordinator.py`** — it updates the coordinator in place and re-pins the roster to the specialists' current versions. Any time the partner changes a specialist (prompt, model, attached skill), the next step is re-running `create_coordinator.py`.

## Where fixes live

Fixes live in **prompts and skills** — never in the data or the scripts' plumbing.

- Output too generic, misses a nuance, wrong tone? Tune a **specialist system prompt** (`create_specialists.py`) or the **coordinator prompt** (`create_coordinator.py`), or sharpen the relevant **`skills/*/SKILL.md`**. Then re-run `create_coordinator.py` and the deal.
- Don't reach for the synthetic data to "fix" a weak answer. If Pricing isn't citing past wins or Technical Fit isn't flagging gaps, that's a prompt/skill problem, not a data problem.
- The idempotency and error-handling in `_common.py`, `check_setup.py`, and the create scripts is load-bearing. Don't rewrite it to route around an error — surface the error and fix the cause.

## Hands off

- **Never edit `synthetic-data/`** — `rfp-acme-corp.md` is the fixed input the whole exercise is graded against, and `past-wins.json` is what makes the "cites past wins" outcome real. Changing the RFP to make the swarm's job easier defeats the exercise.
- Don't hand-edit the dot-files (`.specialist_ids.json`, `.coordinator_id`, etc.). If state is stale, use `python check_setup.py --reset` and re-run the create scripts.
- The build order is real: `setup_environment.py` → `create_specialists.py` → `upload_skills.py` → `create_coordinator.py` → `run_deal_desk.py`. Skills before coordinator, always.

## What good looks like

Encourage the partner toward the **Great when** bar in `BRIEF.md`: every section of the doc traceable to a specialist, Pricing citing named past wins, and Technical Fit honestly flagging the gaps its skill lists (the 99.99% SLA is a priced add-on; sub-100ms real-time isn't our best ground) instead of promising a perfect fit. A proposal that quietly promises everything is the one that loses on the reference call — steer them away from it.

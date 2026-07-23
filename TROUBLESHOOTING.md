# Troubleshooting

**First move, always:** `python check_setup.py`. It verifies your key, SDK, multi-agent access, and every saved ID from earlier runs — most of what's below, it catches before you hit it. Every session script also prints its **session ID and a Console trace URL** the moment it starts; when something goes wrong mid-run, open that URL first.

---

## "My key was rejected" / can't reach the API

`check_setup.py` pings the API with your key before anything else and tells you which of the two it is:
- **Rejected key** → open `.env`, paste the whole key (it starts with `sk-ant-`), save, re-run. See [`SETUP.md`](./SETUP.md) for the `.env` flow.
- **Can't reach the API at all** → connection or corporate proxy. [`SETUP.md`](./SETUP.md) has the proxy setup.

Once you see `✓ API key verified — any error after this is not the API key`, stop suspecting the key and read the actual error.

---

## No multi-agent access

`check_setup.py` ends with a probe: it get-or-creates one tiny agent whose only config is a multi-agent roster. If your workspace has the research preview, it succeeds silently. If not, you'll see:

```
✗ This workspace does NOT appear to have multi-agent (research preview) access.
```

**What it means:** multi-agent (a coordinator with a sub-agent roster) is gated behind a research preview. `create_coordinator.py` is the one script that needs it — creating specialists, uploading skills, and running single-agent sessions all work without it.

**How to get access:** ask whoever owns your workspace to request the **multi-agent research preview** for that workspace, through the Console or your Anthropic contact. It's a workspace-level grant, not something you can flip from the SDK.

**Manual fallback (finish the exercise without the preview).** You lose the parallel fan-out, but you still get the deliverable and the architecture story:

1. Run `setup_environment.py`, `create_specialists.py`, `upload_skills.py` as normal — none of them need the preview.
2. **Skip** `create_coordinator.py`.
3. For each of the four specialists, create a single-agent session (`agent=<that specialist's id>` from `.specialist_ids.json`), send it the RFP text, and save its reply. Each specialist already has its skill attached, so it answers in-lane.
4. Create one **new synthesis agent with the docx skill attached** — `client.beta.agents.create(name="Deal Desk Synthesis", model="claude-opus-4-8", tools=[{"type": "agent_toolset_20260401"}], skills=[{"type": "anthropic", "skill_id": "docx"}])` — then start a single-agent session against it, paste in the RFP plus the four saved replies, and ask it to synthesise them and write `proposal-response.docx` to `/mnt/session/outputs/`. **The four specialists only carry their own domain skill, not docx** (only `create_coordinator.py` attaches docx, and this fallback skips it) — so docx must be attached to whichever agent writes the document, or you'll get markdown in chat instead of a file.
5. `python download_deliverable.py <that session id>` to pull the docx.

Same coordinator-plus-specialists shape — just sequential instead of parallel.

---

## Specialists seem generic / didn't use their skill

Almost always the **ordering invariant**: the coordinator pins each specialist's version at the moment it's created, so if the coordinator was created *before* the skills were attached (or before you last changed a specialist), it's pointing at a stale version with no skill on it.

**Fix:** `python create_coordinator.py`. It updates the coordinator in place and re-pins the roster to the specialists' current versions. Re-run the deal. This is the single most common recovery move in this track — any time you change a specialist (prompt, model, attached skill), re-run `create_coordinator.py` afterwards.

If a *specific* specialist still ignores its skill, confirm the skill actually attached: `.skill_ids.json` should list it, and `upload_skills.py` prints `attached ✓` for each one.

---

## Session appears hung

A big build can legitimately take minutes. The session driver prints a reminder if a turn runs past its timeout:

```
[still running after 600s — that can be normal for a big build.
 Watch it live: https://platform.claude.com/workspaces/...
 Ctrl-C here is safe; the session keeps running server-side.]
```

**Open that Console URL** to watch the live event trace and see which thread is working. **Ctrl-C is safe** — it only detaches your local script; the session keeps running in the cloud. Once it finishes, pull the results with `python download_deliverable.py` (it reads `.last_session_id`, or pass the session ID shown at start).

If instead you get `[session error]` or `[session terminated before finishing]`, the script exits non-zero and prints the trace URL — read the trace to see what the agent hit.

---

## "No files found" after the run

The swarm's deliverable is only retrievable if it was saved to **`/mnt/session/outputs/`** inside the container. Files written anywhere else vanish when the session ends.

There's also a **1–3 second indexing lag** after a session goes idle before its files are listable. `run_deal_desk.py` already retries four times over ~9 seconds, so a transient lag resolves itself. If you still see `(no files found …)`:

- **Re-fetch a bit later:** `python download_deliverable.py` (uses `.last_session_id`), or `python download_deliverable.py <session_id>` for an older run.
- **Check what the coordinator actually did** in the transcript (`outputs/coordinator-transcript.txt`) or the Console trace. If it wrote the proposal as markdown *in chat* instead of a docx file, the **docx skill wasn't attached** — re-run `create_coordinator.py` (it attaches the docx skill) and run the deal again.
- **Wrong path** — if the coordinator saved to `outputs/` or `/tmp` inside the container instead of `/mnt/session/outputs/`, tighten that instruction in the kickoff prompt or coordinator system prompt.

---

## Stale or foreign saved IDs

Symptom: a script exits with "a saved ID points at a resource this key can't see," or a session fails to start with a not-found / permission error, or `check_setup.py` marks a saved ID with `✗ … points at a resource this key can't see`.

**Cause:** dot-files left over from an earlier run, a resource that was deleted, or a key that belongs to a different workspace than the one that created those IDs.

**Fix:** delete the offending dot-file and re-run its create script, or clear everything local at once:

```bash
python check_setup.py --reset
```

`--reset` only removes **local** state files. It never deletes remote agents, environments, or skills — the next run reuses or recreates whatever it needs.

---

## The state files (dot-files)

Every script writes small hidden files at the repo root so later steps can find what earlier steps made. All are gitignored. When one goes stale, delete it and re-run its owner script (or use `--reset` to clear them all).

| File | Written by | What it holds | If it's stale |
| --- | --- | --- | --- |
| `.environment_id` | `setup_environment.py` | The cloud environment ID | Delete it, re-run `setup_environment.py` |
| `.specialist_ids.json` | `create_specialists.py` | The four specialist agent IDs (plus the critic, if you added it) | Delete it, re-run `create_specialists.py` → then `upload_skills.py` → then `create_coordinator.py` (the IDs changed, so the roster must be re-pinned) |
| `.skill_ids.json` | `upload_skills.py` | The uploaded custom-skill IDs | Delete it, re-run `upload_skills.py` |
| `.coordinator_id` | `create_coordinator.py` | The coordinator agent ID | Delete it, re-run `create_coordinator.py` |
| `.last_session_id` | `run_deal_desk.py` | The most recent deal session (the default for `download_deliverable.py`) | Safe to delete; you just lose the download default — pass the session ID explicitly |
| `.skill_title_suffix` | `upload_skills.py` | Your per-checkout skill-title suffix (see below) | Delete it and the next `upload_skills.py` mints a new suffix and uploads fresh skill copies |

---

## Skill title collision (auto-handled)

Custom skill `display_title`s must be **globally unique across the whole org** — including titles you can't see (other teams' skills, deleted skills). So a bare title like `Pricing Playbook` collides the moment two teams run this exercise in the same org.

`upload_skills.py` handles this for you: on first run it generates a short random suffix, stores it in `.skill_title_suffix`, and appends it to every skill title (`Pricing Playbook 3f9a1c`). The suffix is stable across re-runs (so you reuse your skills instead of duplicating them) and unique across teams. If a title still collides with something invisible, the script mints a new suffix and retries once. **You don't need to do anything** — this is just what the suffix in that dot-file is.

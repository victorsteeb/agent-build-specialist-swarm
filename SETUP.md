# Setup & Troubleshooting

One page to get any laptop — including a locked-down corporate one — running this exercise. **The fastest reliable path is a virtual environment.**

---

## The 4-command setup (do this once)

```bash
python3 -m venv .venv                 # create an isolated environment
source .venv/bin/activate             # macOS/Linux  (Windows: .venv\Scripts\activate)
pip install -r requirements.txt       # install the anthropic SDK
python check_setup.py                 # verify key, SDK, multi-agent access, saved state
```

You should see `✓ Dependencies ready`, then `✓ API key verified`, then the rest of the checks. Green across the board means you're ready to build (start with [`BRIEF.md`](./BRIEF.md)).

> You don't strictly need the venv — `check_setup.py` installs what's missing on its own — but a venv is the one setup that sidesteps *every* problem below at once.

---

## API key

`check_setup.py` (like every script here) creates a gitignored **`.env` file** the first time you run it — you never paste your key into a script or the terminal history. Open the `.env`, paste your key after `ANTHROPIC_API_KEY=`, save, and re-run. The key never touches the code, it survives across runs so you paste it once, and a single `.env` at the repo root serves every script (the loader walks up the folders to find it). You can also set `ANTHROPIC_API_KEY` in your shell — it wins over the file:

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
```

A key starts with `sk-ant-`. If `check_setup.py` says the key was rejected, paste the *whole* key again — a truncated copy is the usual culprit.

---

## Common problems

### `error: externally-managed-environment` (PEP 668)
**Why:** you're installing into a system Python (Homebrew on macOS, or the OS Python on Debian/Ubuntu) that's marked off-limits for `pip`. **Fix:** usually nothing — `check_setup.py` detects a locked-down Python and installs into your user space automatically on the **first** run, printing just `✓ Dependencies ready` (no PEP 668 wall of text). Prefer not to touch the system Python at all? Use the venv above; it's the cleanest path. You'll only get an error if **every** install strategy fails — an offline machine or a blocked PyPI (see the proxy section below).

### No admin rights / `permission denied` on install
A venv is owned by you, so it needs no admin rights — use it. If you can't make one, the automatic `--user` fallback installs into your home directory instead.

### Corporate proxy / PyPI blocked by the firewall
Point pip at your proxy, then install:
```bash
export HTTPS_PROXY=http://user:pass@proxy.company.com:8080
export HTTP_PROXY=$HTTPS_PROXY
pip install -r requirements.txt
```
If PyPI itself is blocked, ask IT for your internal package mirror and use it:
`pip install -r requirements.txt --index-url https://<your-mirror>/simple`.

### "I don't have Python" / wrong version
You need **Python 3.9 or newer** (the CI pins 3.9). Install from [python.org](https://www.python.org/downloads/) or your company's software portal, then re-open your terminal so it's detected. Check with `python3 --version`.

### SDK too old for Managed Agents
This track uses `client.beta.agents` / `.sessions` / `.environments` / `.skills`, which need a current SDK. `check_setup.py` catches an old install and prints the exact upgrade command (`pip install -U 'anthropic>=0.116.0'`). Inside a venv, `pip install -r requirements.txt` already satisfies this.

---

## Still stuck?
Run `python check_setup.py` and read the message — every script prints a specific next step rather than a raw traceback. Runtime issues once you're building (hung sessions, stale IDs, no multi-agent access, missing output files) live in [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md). The venv path at the top of this page resolves the setup issues in the large majority of cases.

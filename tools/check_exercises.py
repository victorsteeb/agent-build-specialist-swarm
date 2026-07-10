#!/usr/bin/env python3
"""Guardrail checks for the Basecamp exercises. Run from the repo root:

    python tools/check_exercises.py

Checks every .py / .ipynb / .md / .txt file for the failure modes that have
actually bitten this repo:

  1. Model IDs outside the allowlist (aliases only — date-pinned snapshot IDs
     invite 404s when a snapshot retires, and one phantom ID shipped that way).
  2. Unicode dashes inside model IDs (word processors silently turn the hyphen
     in `claude-sonnet-4-6` into an en-dash; notebooks store it as \\u2013, so
     this scans *decoded* cell sources, not raw JSON).
  3. Deprecated/removed API params in code: temperature / top_p / top_k are
     removed on Opus 4.7+ and Fable 5; budget_tokens is replaced by adaptive
     thinking; top-level output_format is replaced by output_config.format.
  4. Anything that looks like a real API key (sk-ant-… literals).
  5. Bare IPython magics (!/%) in .py files — they break `python file.py`.
  6. Every .py compiles; every .ipynb is valid nbformat.

Exit code 0 = clean, 1 = findings (printed as file:line: message).
"""
import glob
import json
import py_compile
import re
import sys

ALLOWED_MODELS = {
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-fable-5",
    "claude-sonnet-5",
}

# Any dash-like character that is not the ASCII hyphen.
DASHES = "‐‑‒–—―−"
MODEL_RE = re.compile(r"claude-(?:fable|opus|sonnet|haiku)[\w.\-" + DASHES + r"]*")

DEPRECATED_CODE = [
    (re.compile(r"\btemperature\s*="), "temperature= (removed on Opus 4.7+/Fable 5)"),
    (re.compile(r"\btop_p\s*="), "top_p= (removed on Opus 4.7+/Fable 5)"),
    (re.compile(r"\btop_k\s*="), "top_k= (removed on Opus 4.7+/Fable 5)"),
    (re.compile(r"\bbudget_tokens\b"), "budget_tokens (use thinking={'type': 'adaptive'} + output_config.effort)"),
    (re.compile(r"\boutput_format\s*="), "top-level output_format (use output_config={'format': ...})"),
]

KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")
MAGIC_RE = re.compile(r"^\s*[!%]\w")

# Magic pip installs in notebook cells: %pip, !pip, !{sys.executable} -m pip, or the
# nbconvert form get_ipython().run_line_magic('pip', ...). These break on PEP 668 /
# locked-down Pythons — notebooks must use the _ensure_packages() helper instead.
NB_PIP_RE = re.compile(
    r"""(^\s*[!%]\s*\S*\s*pip\s+install      # %pip install / !pip install / !{sys.executable} -m pip install
        |get_ipython\(\)\.run_line_magic\(\s*['"]pip['"])""",
    re.VERBOSE,
)

# No files are exempt from the doc checks in this repo.
SKIP_FILES = set()

findings = []


def flag(path, line, msg):
    findings.append(f"{path}:{line}: {msg}")


def lineno(text, pos):
    return text[:pos].count("\n") + 1


def check_models_and_keys(path, text):
    for m in MODEL_RE.finditer(text):
        token = m.group().rstrip(".,;:")
        if any(ord(ch) > 127 for ch in token):
            flag(path, lineno(text, m.start()),
                 f"unicode dash inside model ID {token!r} — replace with ASCII hyphens")
        elif re.search(r"-\d{8}$", token):
            flag(path, lineno(text, m.start()),
                 f"date-pinned model ID {token!r} — use the alias")
        elif token not in ALLOWED_MODELS:
            flag(path, lineno(text, m.start()),
                 f"model ID {token!r} not in allowlist {sorted(ALLOWED_MODELS)}")
    for m in KEY_RE.finditer(text):
        flag(path, lineno(text, m.start()), "possible API key literal (sk-ant-…) — use env vars")


def check_code(path, text):
    for pattern, msg in DEPRECATED_CODE:
        for m in pattern.finditer(text):
            flag(path, lineno(text, m.start()), msg)


def main():
    py_files = [p for p in glob.glob("**/*.py", recursive=True)
                if not p.startswith((".git/", "tools/"))]
    nb_files = [p for p in glob.glob("**/*.ipynb", recursive=True) if not p.startswith(".git/")]
    doc_files = [p for p in glob.glob("**/*.md", recursive=True) + glob.glob("**/*.txt", recursive=True)
                 if not p.startswith(".git/") and p not in SKIP_FILES]

    for path in py_files:
        text = open(path, encoding="utf-8").read()
        check_models_and_keys(path, text)
        check_code(path, text)
        for i, line in enumerate(text.split("\n"), 1):
            if MAGIC_RE.match(line):
                flag(path, i, f"bare IPython magic {line.strip()[:40]!r} — comment it; .py must run as a script")
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as e:
            flag(path, 0, f"does not compile: {e.msg.splitlines()[-1] if e.msg else e}")

    for path in nb_files:
        raw = open(path, encoding="utf-8").read()
        try:
            nb = json.loads(raw)
        except json.JSONDecodeError as e:
            flag(path, 0, f"invalid JSON: {e}")
            continue
        try:
            import nbformat
            nbformat.validate(nbformat.reads(raw, as_version=4))
        except ImportError:
            pass
        except Exception as e:
            flag(path, 0, f"nbformat validation failed: {e}")
        for cell in nb.get("cells", []):
            src = "".join(cell.get("source", []))  # decoded — catches – escapes
            check_models_and_keys(path, src)
            if cell.get("cell_type") == "code":
                check_code(path, src)
                for m in NB_PIP_RE.finditer(src):
                    flag(path, 0, "magic pip install in a notebook cell — use the "
                                  "_ensure_packages() helper (survives PEP 668); see SETUP.md")

    for path in doc_files:
        check_models_and_keys(path, open(path, encoding="utf-8").read())

    if findings:
        print(f"FAIL — {len(findings)} finding(s):")
        for f in findings:
            print(f"  {f}")
        sys.exit(1)
    print(f"OK — {len(py_files)} .py, {len(nb_files)} .ipynb, {len(doc_files)} docs checked; no findings")


if __name__ == "__main__":
    main()

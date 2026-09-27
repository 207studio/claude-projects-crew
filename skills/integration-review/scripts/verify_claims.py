#!/usr/bin/env python3
"""Check a worker's (subagent's or thread's) claims against the actual files.

A report that says "done, under 280 characters, tests pass" is a claim, not evidence.
This script re-measures each claim and prints PASS / FAIL / SKIP with the measured value.

Input: a JSON file with a list of claims, OR a Markdown report containing a fenced
```claims block with that JSON. If no claims block is found the exit code is 2:
treat the work as UNVERIFIED (this also covers a worker that ended without reporting).

Claim types (all paths are relative to --root):
  {"type": "file_exists", "path": "out/post.txt"}
  {"type": "file_absent", "path": "tmp/debug.log"}
  {"type": "max_chars", "path": "out/post.txt", "max": 280, "mode": "codepoints" | "x_weighted"}
  {"type": "min_chars", "path": "...", "min": 10}
  {"type": "max_lines", "path": "...", "max": 40}
  {"type": "contains", "path": "...", "text": "..."}          / "not_contains"
  {"type": "regex", "path": "...", "pattern": "..."}
  {"type": "json_valid", "path": "..."}
  {"type": "changed_within", "base": "main", "allowed": ["src/feature/*", "tests/*"]}
  {"type": "command", "run": "make test", "expect_exit": 0}   (only with --allow-commands)
Any claim may use "text" instead of "path" to measure an inline string.
Any claim may carry "claimed": <what the worker said>, shown next to the measurement.

Exit: 0 all pass, 1 any FAIL, 2 no claims found / unreadable input.
Standard library only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

# ---- X (Twitter) weighted length: APPROXIMATION of twitter-text v3 config ----
# Code points in these ranges weigh 1, everything else 2; each URL counts as 23.
# Emoji sequences are approximated (joiners/modifiers weigh 0). Confirm limits
# that matter with the platform's own counter before publishing.
_X_LIGHT = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
_X_ZERO = {0x200D, 0xFE0E, 0xFE0F, 0x20E3} | set(range(0x1F3FB, 0x1F400))
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


def x_weighted_len(text: str) -> int:
    text = unicodedata.normalize("NFC", text)
    total = 0
    urls = _URL.findall(text)
    total += 23 * len(urls)
    text = _URL.sub("", text)
    for ch in text:
        cp = ord(ch)
        if cp in _X_ZERO:
            continue
        total += 1 if any(lo <= cp <= hi for lo, hi in _X_LIGHT) else 2
    return total


def read_target(c: dict, root: Path) -> str:
    if "text" in c and c.get("type") not in ("contains", "not_contains"):
        return str(c["text"])
    if "inline" in c:
        return str(c["inline"])
    return (root / c["path"]).read_text(encoding="utf-8")


def measure(c: dict, root: Path, allow_cmd: bool) -> tuple[str, str]:
    t = c.get("type")
    try:
        if t == "file_exists":
            return ("PASS" if (root / c["path"]).exists() else "FAIL"), "exists" if (root / c["path"]).exists() else "missing"
        if t == "file_absent":
            return ("PASS" if not (root / c["path"]).exists() else "FAIL"), "absent" if not (root / c["path"]).exists() else "present"
        if t in ("max_chars", "min_chars"):
            s = read_target(c, root)
            if c.get("strip", True):
                s = s.strip()
            mode = c.get("mode", "codepoints")
            n = x_weighted_len(s) if mode == "x_weighted" else len(unicodedata.normalize("NFC", s))
            limit = c["max"] if t == "max_chars" else c["min"]
            ok = n <= limit if t == "max_chars" else n >= limit
            return ("PASS" if ok else "FAIL"), f"{n} ({mode}) vs {'≤' if t == 'max_chars' else '≥'} {limit}"
        if t == "max_lines":
            n = len(read_target(c, root).splitlines())
            return ("PASS" if n <= c["max"] else "FAIL"), f"{n} lines vs ≤ {c['max']}"
        if t in ("contains", "not_contains"):
            body = (root / c["path"]).read_text(encoding="utf-8") if "path" in c else str(c.get("inline", ""))
            found = c["text"] in body
            ok = found if t == "contains" else not found
            return ("PASS" if ok else "FAIL"), "found" if found else "not found"
        if t == "regex":
            m = re.search(c["pattern"], read_target(c, root), re.MULTILINE)
            return ("PASS" if m else "FAIL"), f"match: {m.group(0)[:60]!r}" if m else "no match"
        if t == "json_valid":
            json.loads(read_target(c, root))
            return "PASS", "valid JSON"
        if t == "changed_within":
            base = c.get("base", "main")
            mb = subprocess.run(["git", "merge-base", base, "HEAD"], cwd=root, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True).stdout.strip()
            diff = subprocess.run(["git", "diff", "--name-only", mb], cwd=root, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True).stdout.split()
            untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root,
                                       stdout=subprocess.PIPE, text=True).stdout.split()
            files = sorted(set(diff) | set(untracked))
            outside = [f for f in files if not any(fnmatch.fnmatch(f, g) for g in c["allowed"])]
            return ("PASS" if not outside else "FAIL"), (f"{len(files)} files, outside scope: {', '.join(outside)}"
                                                        if outside else f"{len(files)} files, all in scope")
        if t == "command":
            if not allow_cmd:
                return "SKIP", "command claims need --allow-commands"
            p = subprocess.run(c["run"], shell=True, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
            want = c.get("expect_exit", 0)
            tail = p.stdout.strip().splitlines()[-1:] if p.stdout.strip() else []
            return ("PASS" if p.returncode == want else "FAIL"), f"exit {p.returncode} (want {want}) {tail[0][:80] if tail else ''}"
        return "SKIP", f"unknown claim type {t!r}"
    except FileNotFoundError as e:
        return "FAIL", f"file not found: {e.filename}"
    except (KeyError, ValueError, OSError, re.error) as e:
        return "FAIL", f"{type(e).__name__}: {e}"


def load_claims(path: Path) -> list[dict] | None:
    raw = path.read_text(encoding="utf-8")
    m = re.search(r"```claims\s*\n(.*?)```", raw, re.DOTALL)
    payload = m.group(1) if m else raw
    try:
        data = json.loads(payload)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = data.get("claims")
    return data if isinstance(data, list) and data else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("claims", help="claims JSON file or Markdown report with a ```claims block")
    ap.add_argument("--root", default=".", help="directory the claim paths are relative to")
    ap.add_argument("--allow-commands", action="store_true", help="run `command` claims (shell)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    root = Path(a.root).resolve()
    try:
        claims = load_claims(Path(a.claims))
    except OSError as e:
        print(f"UNVERIFIED: cannot read report: {e}")
        return 2
    if not claims:
        print("UNVERIFIED: no claims block found. The worker did not report checkable claims "
              "(or ended without reporting). Inspect the output yourself before accepting it.")
        return 2

    rows = []
    for i, c in enumerate(claims, 1):
        status, measured = measure(c, root, a.allow_commands)
        target = c.get("path") or c.get("run") or ("inline text" if "text" in c else "")
        rows.append({"n": i, "type": c.get("type"), "target": target, "claimed": c.get("claimed", ""),
                     "measured": measured, "status": status})

    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print("| # | Claim | Target | Worker said | Measured | Result |")
        print("|---|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['n']} | {r['type']} | {r['target']} | {r['claimed']} | {r['measured']} | {r['status']} |")
        fails = sum(r["status"] == "FAIL" for r in rows)
        skips = sum(r["status"] == "SKIP" for r in rows)
        print(f"\n{len(rows)} claims: {len(rows) - fails - skips} pass, {fails} fail, {skips} skipped")
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())

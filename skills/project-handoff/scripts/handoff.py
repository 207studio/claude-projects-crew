#!/usr/bin/env python3
"""Repository-backed handoff notes for Claude Code sessions.

Keeps project state in the repository (not only in a cloud conversation):
  HANDOFF.md                    shared state: goal, decisions, open work (edit on the base branch)
  handoff/sessions/<file>.md    append-only notes, one file per branch+session (no merge conflicts)

Subcommands:
  init                 create HANDOFF.md and handoff/sessions/ if missing
  read                 print state, recent session notes, git status
  write                append a note for this session (optionally commit / push)

Standard library only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from pathlib import Path

STATE_FILE = "HANDOFF.md"
SESSIONS_DIR = "handoff/sessions"

STATE_TEMPLATE = """# Project handoff

<!-- Shared state for every session and thread. Keep it short. Update it on the
     base branch (or in a small PR); per-session notes go in handoff/sessions/. -->

## Goal

- (what this project is for, in one or two lines)

## Decisions (do not re-litigate without a reason)

- YYYY-MM-DD: (decision) — (why)

## Open work

- [ ] (task) — owner/branch: (thread or branch name)

## Needs a local machine (computer use, local DB, VPN, device)

- (task) — why it cannot run in a cloud session

## Known pitfalls

- (pitfall) — (how to avoid)
"""


def run(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"error: {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def git(root: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], cwd=root, check=check)


def repo_root(start: str | None) -> Path:
    cwd = Path(start or os.getcwd()).resolve()
    out = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, check=False).strip()
    if not out:
        raise SystemExit(f"error: {cwd} is not inside a git repository")
    return Path(out)


def current_branch(root: Path) -> str:
    name = git(root, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip()
    return name or "unknown"


def slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-").lower()
    return (s or "x")[:limit]


def session_id(explicit: str | None) -> str:
    if explicit:
        return explicit
    for var in ("CLAUDE_CODE_REMOTE_SESSION_ID", "CLAUDE_SESSION_ID"):
        if os.environ.get(var):
            return os.environ[var]
    return "local"


def now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def uncommitted(root: Path) -> list[str]:
    out = git(root, "status", "--porcelain", check=False)
    return [line[3:] for line in out.splitlines() if line.strip()]


def find_session_file(root: Path, branch: str, sid: str) -> Path | None:
    d = root / SESSIONS_DIR
    if not d.is_dir():
        return None
    suffix = f"-{slug(branch)}-{slug(sid, 16)}.md"
    matches = sorted(p for p in d.glob("*.md") if p.name.endswith(suffix))
    return matches[-1] if matches else None


# ---------------------------------------------------------------- init
def cmd_init(a: argparse.Namespace) -> int:
    root = repo_root(a.repo)
    created = []
    state = root / STATE_FILE
    if not state.exists():
        state.write_text(STATE_TEMPLATE, encoding="utf-8")
        created.append(STATE_FILE)
    sess = root / SESSIONS_DIR
    if not sess.exists():
        sess.mkdir(parents=True)
        (sess / ".gitkeep").write_text("", encoding="utf-8")
        created.append(SESSIONS_DIR + "/")
    print("created: " + (", ".join(created) if created else "nothing (already initialized)"))
    return 0


# ---------------------------------------------------------------- read
def note_headline(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("- Summary:"):
            return line[len("- Summary:"):].strip()
    return ""


def cmd_read(a: argparse.Namespace) -> int:
    root = repo_root(a.repo)
    branch = current_branch(root)
    print(f"# Handoff read — {root.name} @ {branch}\n")

    state = root / STATE_FILE
    if state.exists():
        print(state.read_text(encoding="utf-8").rstrip() + "\n")
    else:
        print(f"(no {STATE_FILE}; run `handoff.py init`)\n")

    sess_dir = root / SESSIONS_DIR
    notes = sorted(sess_dir.glob("*.md")) if sess_dir.is_dir() else []
    print(f"## Session notes on this branch ({len(notes)} files, latest {a.limit})\n")
    for p in notes[-a.limit:]:
        text = p.read_text(encoding="utf-8")
        print(f"### {p.name}\n")
        # print only the last entry of each file to keep output small
        entries = text.split("\n## ")
        last = entries[-1] if len(entries) > 1 else text
        print(("## " + last if len(entries) > 1 else last).rstrip() + "\n")

    if a.all_branches:
        here = {p.name for p in notes}
        refs = git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes", check=False).split()
        seen: set[str] = set()
        rows = []
        for ref in refs:
            if ref.endswith("/HEAD") or ref in (branch, f"origin/{branch}"):
                continue
            listing = git(root, "ls-tree", "-r", "--name-only", ref, "--", SESSIONS_DIR, check=False).split()
            for path in listing:
                name = path.rsplit("/", 1)[-1]
                if not name.endswith(".md") or name in here or name in seen:
                    continue
                seen.add(name)
                body = git(root, "show", f"{ref}:{path}", check=False)
                rows.append((ref, name, note_headline(body.split("\n## ")[-1]) or note_headline(body)))
        print(f"## Notes that exist only on other branches ({len(rows)})\n")
        for ref, name, head in rows:
            print(f"- {ref}: {name} — {head or '(no summary)'}")
        print()

    print("## Git state\n")
    upstream = git(root, "rev-parse", "--abbrev-ref", "@{u}", check=False).strip()
    if upstream:
        counts = git(root, "rev-list", "--left-right", "--count", f"{upstream}...HEAD", check=False).split()
        if len(counts) == 2:
            print(f"- upstream {upstream}: behind {counts[0]}, ahead {counts[1]}")
    else:
        print("- no upstream (branch not pushed)")
    dirty = uncommitted(root)
    print(f"- uncommitted files: {len(dirty)}" + (" — " + ", ".join(dirty[:10]) if dirty else ""))
    return 0


# ---------------------------------------------------------------- write
def bullet_block(title: str, items: list[str]) -> str:
    if not items:
        return ""
    return f"- {title}:\n" + "".join(f"  - {i}\n" for i in items)


def cmd_write(a: argparse.Namespace) -> int:
    root = repo_root(a.repo)
    branch = current_branch(root)
    sid = session_id(a.session)
    ts = now_utc()
    sess_dir = root / SESSIONS_DIR
    sess_dir.mkdir(parents=True, exist_ok=True)

    path = find_session_file(root, branch, sid)
    if path is None:
        path = sess_dir / f"{ts:%Y%m%d-%H%M}-{slug(branch)}-{slug(sid, 16)}.md"
        header = f"# Session notes — branch `{branch}`\n\n- Session: `{sid}`\n"
        if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
            header += "- Environment: cloud session\n"
        path.write_text(header, encoding="utf-8")

    head = git(root, "rev-parse", "--short", "HEAD", check=False).strip() or "(no commits)"
    dirty = [f for f in uncommitted(root) if not f.startswith(SESSIONS_DIR)]
    entry = f"\n## {ts:%Y-%m-%d %H:%M} UTC — {a.reason}\n\n"
    entry += f"- Summary: {a.summary}\n- HEAD: `{head}`\n"
    entry += bullet_block("Done", a.done)
    entry += bullet_block("Next", a.next)
    entry += bullet_block("Decisions", a.decision)
    entry += bullet_block("Blockers", a.blocker)
    entry += bullet_block("Needs a local machine", a.needs_local)
    entry += bullet_block("Uncommitted at time of note", dirty[:30])
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    rel = path.relative_to(root).as_posix()
    print(f"wrote {rel}")

    if a.commit or a.push:
        git(root, "add", "--", rel)
        msg = f"handoff({a.reason}): {a.summary}"[:120]
        git(root, "commit", "-m", msg, "--", rel)
        print("committed " + git(root, "rev-parse", "--short", "HEAD").strip())
    if a.push:
        out = run(["git", "push", "-u", "origin", "HEAD"], cwd=root, check=False)
        print(out.strip() or "push attempted (see git output above)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", help="path inside the target git repository (default: cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create HANDOFF.md and handoff/sessions/")

    r = sub.add_parser("read", help="print handoff state")
    r.add_argument("--limit", type=int, default=5, help="latest N session files to show")
    r.add_argument("--all-branches", action="store_true", help="also list notes that exist only on other branches")

    w = sub.add_parser("write", help="append a session note")
    w.add_argument("--summary", required=True, help="one line: where the work stands")
    w.add_argument("--reason", default="checkpoint",
                   choices=["checkpoint", "end", "limit", "blocked", "handoff"],
                   help="why the note is written")
    for flag in ("done", "next", "decision", "blocker", "needs-local"):
        w.add_argument(f"--{flag}", action="append", default=[], metavar="TEXT")
    w.add_argument("--session", help="session id (default: $CLAUDE_CODE_REMOTE_SESSION_ID or 'local')")
    w.add_argument("--commit", action="store_true", help="commit only the note file")
    w.add_argument("--push", action="store_true", help="commit and push the current branch to origin")

    a = p.parse_args(argv)
    return {"init": cmd_init, "read": cmd_read, "write": cmd_write}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

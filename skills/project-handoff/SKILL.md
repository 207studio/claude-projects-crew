---
name: project-handoff
description: Keeps a Claude Code project's state in the git repository so it survives cloud-only conversations, usage-limit pauses, sandbox resets and moves between local and cloud sessions. Use at the start of any session or Projects thread (read HANDOFF.md and recent session notes before working), before stopping, when the user says "hand off", "wrap up", "save progress", "checkpoint", or when a usage limit, long task or context limit is near (write and commit a handoff note). Also use when asked what was decided earlier or what is left to do.
license: MIT
compatibility: Needs git and python3 (3.8+). Works in local sessions, cloud sessions and Projects threads.
---

# Project handoff

The coordinator conversation and cloud threads of a Projects project live on
claude.ai, not on disk. This skill writes the parts you need to continue —
state, decisions, next steps — into the repository, where every session,
thread and your local clone can read them with `git pull`.

Files (in the repository root):

- `HANDOFF.md` — shared state: goal, decisions, open work, local-only tasks, pitfalls.
  Change it on the base branch or in a small PR, because every thread reads it.
- `handoff/sessions/*.md` — append-only notes, one file per branch + session.
  Threads on different branches never edit the same file, so notes do not conflict.

Script: `python3 ${CLAUDE_SKILL_DIR}/scripts/handoff.py` (run from inside the repo).

## At session start

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/handoff.py read --all-branches`
2. If it says there is no `HANDOFF.md`, run `... handoff.py init`, fill in the
   Goal section from the task, and commit it only if the user or project
   instructions allow committing to this branch.
3. Before working, state in one or two lines: the goal, the decisions that
   constrain this task, and which open item you are taking. Do not redo work
   another branch's notes mark as done; do not reverse a recorded decision
   without saying why.

## While working

- After each meaningful milestone (tests green, a subtask done, before a risky
  change), write a checkpoint and commit it together with the work in progress:
  `... handoff.py write --reason checkpoint --summary "..." --done "..." --next "..." --commit`
- A cloud thread's sandbox can be replaced by a fresh clone, which loses
  uncommitted changes. Commit and push work in progress on long tasks when the
  branch rules allow pushing (`--push` pushes the current branch to `origin`).
- Record decisions as `--decision "YYYY-MM-DD: X, because Y"`. If the decision
  applies to the whole project, also add it to `HANDOFF.md` (or ask the
  coordinator to), and ask Claude to remember it in project memory.

## Before stopping, or when a limit is near

You cannot read the remaining usage from inside a session. Treat these as
"near": a long multi-step task past its midpoint, a warning from the user, or a
context-limit or usage-limit message. Then:

1. `... handoff.py write --reason end|limit|blocked --summary "<where it stands>" \
   --done "..." --next "<first concrete step for the next session>" \
   --blocker "..." --needs-local "<anything only the user's machine can do>" --commit`
2. Push if allowed. Tell the user the note path and the next step in one line.

A good `--next` is executable without this conversation: file, function,
command, expected result. "Continue the refactor" is not enough.

## Rules

- Notes contain no secrets, tokens or personal data; they are committed.
- The script commits only the note file. Stage and commit your code yourself.
- Never force-push, rewrite history, or merge to the base branch for a handoff.
- If `git commit` fails (hooks, no identity), report the failure; do not bypass hooks.

See `references/notes-format.md` for the note format and a filled example.

---
name: portable-env
description: Audits which parts of a local Claude Code setup (personal skills, subagents, commands, ~/.claude/CLAUDE.md, hooks, plugins, MCP servers) will not reach cloud sessions or Projects threads, and moves the portable ones into the repository's committed .claude/ directory. Use when setting up a repository for cloud sessions or a Projects project, when a cloud thread "doesn't know" a skill, rule or tool that works locally, when the user asks why cloud behaves differently from local, or to list tasks that need the user's own computer (computer use, local database, VPN, device).
license: MIT
compatibility: Needs git and python3 (3.8+). Run it on the user's machine; in a cloud session ~/.claude is not the user's.
---

# Portable environment

Cloud sessions and Projects threads start from a fresh clone. What is
committed in the repository travels; what lives only in `~/.claude`,
`~/.claude.json` or your user settings does not. Moving a session between
local and cloud moves a branch and a summary, not a live connection.

Script: `python3 ${CLAUDE_SKILL_DIR}/scripts/env_audit.py --repo <repo>`
(prints names only; never values of MCP env, headers or hook commands).

## 1. Audit (on the user's machine)

1. Run the audit. Read the "will NOT reach a cloud session" table.
2. For each row decide with the user, using `references/portability.md`:
   - personal skill / agent / command the project needs → copy into the repo
   - rule in `~/.claude/CLAUDE.md` the project needs → move the rule text into
     the repo `CLAUDE.md` (project-wide rules only; keep personal rules personal)
   - MCP server → a claude.ai connector, or `claude mcp add --scope project`
     (writes `.mcp.json`) when the project has one repository
   - plugin → **Project settings > Plugins** for Projects threads
   - hook → repo `.claude/settings.json` (applies only with one repository)
   - CLI tool or package → the cloud environment's setup script
   - secret or token → never commit; use the environment's variables or API credentials

## 2. Copy what is portable

- `env_audit.py --repo <repo> --copy-skill <name>` (or `--copy-agent <name>`)
  copies from `~/.claude` into `<repo>/.claude/`. It refuses to overwrite
  unless `--force`.
- Run the audit again and fix every "Portability problems" line: absolute
  home paths and `~/.claude/...` references break in the cloud clone. Use
  paths relative to the repo, `${CLAUDE_SKILL_DIR}` inside skills, or
  `$CLAUDE_PROJECT_DIR` in hooks.
- Show the user `git status` and the diff; commit only with their approval.

## 3. Write down what cannot move

Some work needs the user's computer: computer use (screen control), local
databases, devices, simulators, VPN-only APIs, the user's logged-in apps.
Add them to the "Needs a local machine" section of `HANDOFF.md` (skill
`project-handoff`) or to the project instructions, each with: task, why it
is local-only, and what the user must switch on first. Template:
`references/portability.md#local-only-tasks`.

In a Projects project, the coordinator can then send those tasks to a thread
on the user's computer ("Work locally", via Remote Control) instead of a cloud
thread. Computer use itself is enabled in the desktop app's settings and
approved per app per session; this skill cannot switch it on.

## Multi-repository projects

In a Projects thread with several repositories, `CLAUDE.md` and
`.claude/skills|agents|commands` load from every repository, but hooks,
permission rules and `env` from `.claude/settings.json` do not apply, and
`.mcp.json` is loaded only with one repository. Put standing rules in the
project instructions, not in hooks.

## Rules

- Do not print or copy secrets. Do not commit `.claude/settings.local.json`.
- Do not change the user's `~/.claude` files; this skill only reads them and
  copies into the repository.

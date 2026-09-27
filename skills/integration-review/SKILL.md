---
name: integration-review
description: Reviews a branch or pull request beyond its own diff before it is opened or merged — cross-checks it against the base branch and every other open branch/PR (overlapping files, predicted merge conflicts, base drift, shared config, dangling references) — and verifies workers' reports by re-measuring their claims against the actual files. Use before opening or merging a PR from a Projects thread or cloud session, when several threads or sessions work on one repository, when the coordinator or user asks "is it safe to merge", "check the other PRs", "integration review", and whenever a subagent or thread reports "done" (character limits, tests passing, files created, scope respected).
license: MIT
compatibility: Needs git 2.38+ (for conflict prediction) and python3 3.8+. gh CLI optional for PR titles.
---

# Integration review

Each Projects thread opens a PR for its own part, and per-PR review looks at
that diff. Nobody checks by default how the parts fit together, and a worker's
"done" message is not evidence. This skill does both checks.

Scripts (run inside the repository):

- `python3 ${CLAUDE_SKILL_DIR}/scripts/crosscheck.py --base origin/main --fetch [--gh]`
- `python3 ${CLAUDE_SKILL_DIR}/scripts/verify_claims.py <report-or-claims.json> --root .`

## A. Before opening or merging a PR

1. Commit your work, then run `crosscheck.py --fetch` (add `--gh` if `gh` is
   authenticated, for PR titles). Other threads' work is visible only once they
   pushed their branches.
2. Act on each section of the report:
   - **Conflicts with base** → rebase or merge the base, resolve, re-run tests.
   - **Base drift** → re-read those files on the base; your change may rely on
     code that moved.
   - **Other branches overlapping** → read their diff for the shared files
     (`git diff <base>...<branch> -- <file>`). Decide who changes what and note
     the merge order. If a predicted conflict exists, do not solve it silently
     in your branch; report it to the coordinator/user.
   - **High blast-radius files** (lockfiles, manifests, CI, migrations,
     shared config, `CLAUDE.md`, public exports) → name every consumer you
     checked, or say you did not.
   - **Dangling references** → fix or explain each one.
3. Walk through `references/checklist.md` for out-of-scope effects.
4. Put a short "Integration notes" section in the PR body: overlaps, merge
   order, consumers checked, and what you did not check.

## B. Verifying a worker's report (subagent or thread)

1. When delegating, require a claims block. Paste this into the worker prompt:
   `references/claims-template.md`.
2. When the worker returns, save its report to a file and run
   `verify_claims.py report.md --root <worktree>`
   (`--allow-commands` only for commands you would run yourself).
3. Exit 0 = every claim re-measured and passed. Exit 1 = at least one claim is
   false; send the worker the failing rows or fix it yourself. Exit 2 = no
   claims block, or no report at all: the work is **unverified**; inspect the
   output yourself before telling anyone it is done.
4. Report to the user with measured values, not the worker's words:
   "post.txt: 312 weighted chars (limit 280) — FAIL", not "under 280".

For X/Twitter limits use `"mode": "x_weighted"` (CJK characters count double,
URLs count 23). It approximates the platform counter; check the final text in
the platform itself before publishing.

## Rules

- This skill reads and reports. It does not merge, rebase other threads'
  branches, close PRs or post PR comments unless the user asks.
- A passing cross-check is not a test run. Run the project's tests too.
- Say what was not checked (branches not pushed, repos not cloned, gh unavailable).

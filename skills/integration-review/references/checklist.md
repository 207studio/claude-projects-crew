# Out-of-scope impact checklist

Answer each line with "checked: <how>", "n/a", or "not checked". Do not skip
lines silently.

## Interfaces
- [ ] Changed function/type/API signatures: every caller found with `git grep`, including other open branches
- [ ] Renamed or deleted files, exports, routes, env vars, CLI flags: no remaining references
- [ ] Serialized formats (JSON fields, DB columns, file formats): old data still readable

## Shared state
- [ ] Lockfiles / dependency manifests: versions compatible with other open branches
- [ ] Migrations: ordering and numbering against other branches' migrations
- [ ] CI / build config: other jobs and platforms still run
- [ ] `CLAUDE.md`, `.claude/`, project instructions: other threads read these; the change is intended for all of them

## Behavior
- [ ] Defaults, feature flags, timeouts, limits changed on purpose and documented
- [ ] Error handling and logging: nothing sensitive added to logs
- [ ] Tests: the project's test command ran on the merged result (base + this branch), not only this branch

## Coordination
- [ ] Overlapping branches listed in the PR body with a proposed merge order
- [ ] Decisions made here recorded in `HANDOFF.md` / project memory
- [ ] Anything not checked is written down as "not checked"

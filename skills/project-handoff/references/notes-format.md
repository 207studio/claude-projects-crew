# Handoff note format

`handoff.py write` appends one entry per call to
`handoff/sessions/<YYYYMMDD-HHMM>-<branch>-<session>.md`:

```markdown
# Session notes — branch `fix/login-timeout`

- Session: `cse_01ABC...`
- Environment: cloud session

## 2026-09-27 14:05 UTC — limit

- Summary: Timeout fix done; flaky retry test still failing on CI only
- HEAD: `3f2a9c1`
- Done:
  - Raised auth client timeout to 10s (src/auth/client.ts)
- Next:
  - Run `npm test -- retry.spec.ts` with CI=1; expect 1 failure in "backs off twice"
- Decisions:
  - 2026-09-27: keep retries at 2, because the gateway already retries once
- Needs a local machine:
  - Reproduce on the iOS simulator (computer use), cloud thread cannot
- Uncommitted at time of note:
  - src/auth/retry.ts
```

The session id comes from `CLAUDE_CODE_REMOTE_SESSION_ID` in cloud sessions
(documented in the cloud environments page), otherwise `local` or `--session`.

## Reasons

| `--reason` | When |
|---|---|
| checkpoint | milestone reached, work continues |
| end | session finished its task |
| limit | usage or context limit near or hit |
| blocked | cannot continue without the user or another thread |
| handoff | moving the work to another session or machine |

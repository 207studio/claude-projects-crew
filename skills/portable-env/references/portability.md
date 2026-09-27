# What travels to a cloud session

Source: https://code.claude.com/docs/en/cloud-environments ("What carries over
from your setup") and https://code.claude.com/docs/en/claude-projects ("What
threads pick up from your repositories"). Re-check these pages; the product is
in beta and changes.

| Item | Cloud session, one repo | Projects thread, several repos | How to make it travel |
|---|---|---|---|
| Repo `CLAUDE.md` | yes | yes (every repo) | commit it |
| Repo `.claude/rules/` | yes | not stated in the Projects docs | commit it; verify in a thread |
| Repo `.claude/skills/`, `agents/`, `commands/` | yes | yes (every repo) | commit it |
| Repo `.claude/settings.json` hooks, permissions | yes | **no** | project instructions instead |
| Repo `.mcp.json` | yes | **no** | claude.ai connectors |
| Plugins in repo `enabledPlugins` | no | no | Project settings > Plugins |
| `~/.claude/CLAUDE.md` | no | no | move project rules to repo `CLAUDE.md` |
| `~/.claude/skills/`, `agents/`, `commands/` | no | no | copy into repo `.claude/` |
| User-scope plugins | no | no | Project settings > Plugins |
| MCP added with `claude mcp add` (local/user scope) | no | no | `--scope project` or a connector |
| CLI tools installed on your machine | no | no | environment setup script |
| API keys | Pro/Max: environment API credentials | same | never commit |

A thread run on your own computer (Remote Control) uses that machine's files,
tools, MCP servers and settings instead.

## Local-only tasks

Paste into `HANDOFF.md` ("Needs a local machine") or project instructions:

```markdown
## Needs a local machine

| Task | Why not cloud | Before starting |
|---|---|---|
| Click through onboarding in the iOS Simulator | needs the simulator / computer use | desktop app: Computer use on; approve Simulator when asked |
| Run migrations against the local DB | DB only on my laptop | `docker compose up db` |
| Call the billing API | VPN-only | connect VPN |

Rule for threads: if a task in this table comes up, stop and report
"needs local: <task>" instead of mocking or guessing.
```

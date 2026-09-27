#!/usr/bin/env bash
# Self-test: builds throwaway git repositories under a temp dir and exercises every script.
# Usage: tests/run_tests.sh      (exit 0 = all passed)
set -uo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
S="$here/skills"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/crew-test.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
pass=0; fail=0

ok()   { pass=$((pass+1)); echo "  ok   - $1"; }
bad()  { fail=$((fail+1)); echo "  FAIL - $1"; [ -n "${2:-}" ] && echo "$2" | head -20 | sed 's/^/         /'; }
expect_contains() { case "$2" in *"$3"*) ok "$1";; *) bad "$1" "$2";; esac; }
expect_absent()   { case "$2" in *"$3"*) bad "$1" "$2";; *) ok "$1";; esac; }
expect_code()     { if [ "$2" -eq "$3" ]; then ok "$1"; else bad "$1 (exit $2, want $3)"; fi; }

export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
g() { git -c init.defaultBranch=main -c commit.gpgsign=false "$@"; }

# ---------- fixture: origin + two clones with three branches
g init -q --bare "$tmp/origin.git"
g clone -q "$tmp/origin.git" "$tmp/a" 2>/dev/null
cd "$tmp/a"
mkdir -p src
printf 'def helper():\n    return 1\n' > src/util.py
printf 'from util import helper\nprint(helper())\n' > src/app.py
printf 'import util\n' > src/other.py
printf '{"name":"demo"}\n' > package.json
g add -A && g commit -qm init && g push -q origin main 2>/dev/null

g checkout -qb feature-a
printf 'def helper():\n    return 2\n' > src/util.py
echo '{"name":"demo","version":"2"}' > package.json
g commit -qam "a: change util and package.json" && g push -q -u origin feature-a 2>/dev/null

g checkout -q main && g checkout -qb feature-b
printf 'def helper():\n    return 3\n' > src/util.py
g commit -qam "b: change util" && g push -q -u origin feature-b 2>/dev/null

g checkout -q main && g checkout -qb feature-c
echo "docs" > README.md && g add README.md && g commit -qm "c: docs only" && g push -q -u origin feature-c 2>/dev/null

g checkout -q main
echo "# main moved" >> src/util.py && g commit -qam "main: touch util" && g push -q origin main 2>/dev/null
g checkout -q feature-a

echo "# integration-review / crosscheck.py"
out="$(python3 "$S/integration-review/scripts/crosscheck.py" --base origin/main --fetch 2>&1)"; code=$?
expect_code "crosscheck runs" $code 0
expect_contains "predicts conflict with base on src/util.py" "$out" "Conflicts if merged into base now: 1 — src/util.py"
expect_contains "reports base drift on src/util.py" "$out" "Base changed these files since you branched (re-read them): 1 — src/util.py"
expect_contains "finds overlap with feature-b" "$out" "feature-b | - | 1 | src/util.py | src/util.py |"
expect_contains "feature-c has no overlap" "$out" "feature-c | - | 1 | - | none |"
expect_contains "flags package.json as blast radius" "$out" "- package.json"
python3 "$S/integration-review/scripts/crosscheck.py" --base origin/main --strict >/dev/null 2>&1
expect_code "--strict exits 1 on conflicts" $? 1
jout="$(python3 "$S/integration-review/scripts/crosscheck.py" --base origin/main --json)"
echo "$jout" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["base_conflicts"]==["src/util.py"]' \
  && ok "--json is valid and structured" || bad "--json output" "$jout"

# dangling reference after rename
g checkout -q main && g checkout -qb feature-rename
g mv src/util.py src/helpers.py && g commit -qm "rename util"
out="$(python3 "$S/integration-review/scripts/crosscheck.py" --base main 2>&1)"
expect_contains "detects references to renamed file" "$out" "src/util.py ← "
g checkout -q feature-a

echo "# integration-review / verify_claims.py"
mkdir -p "$tmp/w/drafts"
python3 - "$tmp/w/drafts/post.txt" <<'PY'
import sys
# 150 Korean syllables + 10 ASCII: 160 code points, but 310 X-weighted
open(sys.argv[1], "w", encoding="utf-8").write("가" * 150 + "abcdefghij")
PY
cat > "$tmp/w/report.md" <<'EOF'
Done. The post is under 280 characters.
```claims
[
  {"type": "file_exists", "path": "drafts/post.txt"},
  {"type": "max_chars", "path": "drafts/post.txt", "max": 280, "mode": "codepoints", "claimed": 160},
  {"type": "max_chars", "path": "drafts/post.txt", "max": 280, "mode": "x_weighted", "claimed": 160},
  {"type": "file_exists", "path": "drafts/image.png"},
  {"type": "command", "run": "true"}
]
```
EOF
out="$(python3 "$S/integration-review/scripts/verify_claims.py" "$tmp/w/report.md" --root "$tmp/w")"; code=$?
expect_code "verify_claims exits 1 when a claim is false" $code 1
expect_contains "codepoint count measured (160)" "$out" "160 (codepoints) vs ≤ 280 | PASS"
expect_contains "X-weighted count catches overflow (310)" "$out" "310 (x_weighted) vs ≤ 280 | FAIL"
expect_contains "missing file detected" "$out" "| drafts/image.png |  | missing | FAIL"
expect_contains "commands skipped without --allow-commands" "$out" "| SKIP |"
printf 'All done, looks good!\n' > "$tmp/w/noclaims.md"
out="$(python3 "$S/integration-review/scripts/verify_claims.py" "$tmp/w/noclaims.md" --root "$tmp/w")"; code=$?
expect_code "report without claims -> exit 2" $code 2
expect_contains "report without claims -> UNVERIFIED" "$out" "UNVERIFIED"
out="$(python3 "$S/integration-review/scripts/verify_claims.py" "$tmp/w/missing-report.md" --root "$tmp/w")"; code=$?
expect_code "no report at all -> exit 2" $code 2
cat > "$tmp/w/ok.json" <<'EOF'
[{"type":"contains","path":"drafts/post.txt","text":"abc"},
 {"type":"command","run":"exit 0","expect_exit":0},
 {"type":"max_chars","text":"https://example.com/a/very/long/path hi","max":26,"mode":"x_weighted"}]
EOF
python3 "$S/integration-review/scripts/verify_claims.py" "$tmp/w/ok.json" --root "$tmp/w" --allow-commands >/dev/null
expect_code "all-pass claims -> exit 0 (URL counted as 23)" $? 0
cd "$tmp/a"
cat > "$tmp/scope.json" <<'EOF'
[{"type":"changed_within","base":"origin/main","allowed":["src/*"]}]
EOF
out="$(python3 "$S/integration-review/scripts/verify_claims.py" "$tmp/scope.json" --root "$tmp/a")"
expect_contains "scope check flags package.json outside src/*" "$out" "outside scope: package.json"

echo "# project-handoff / handoff.py"
H="$S/project-handoff/scripts/handoff.py"
cd "$tmp/a" && g checkout -q feature-a
out="$(python3 "$H" init)"; expect_contains "init creates files" "$out" "HANDOFF.md"
out="$(python3 "$H" init)"; expect_contains "init is idempotent" "$out" "already initialized"
g add HANDOFF.md handoff && g commit -qm "handoff init"
echo "wip" > src/wip.py
out="$(CLAUDE_CODE_REMOTE=true CLAUDE_CODE_REMOTE_SESSION_ID=cse_TEST123 python3 "$H" write --reason limit \
  --summary "util change done, tests pending" --done "changed helper" --next "run pytest -k util" \
  --decision "2026-09-27: helper returns 2" --needs-local "check in simulator" --commit)"
expect_contains "write reports note path" "$out" "wrote handoff/sessions/"
expect_contains "write commits" "$out" "committed "
note="$(ls handoff/sessions/*feature-a*cse_test123*.md 2>/dev/null | head -1)"
[ -n "$note" ] && ok "note file named by branch+session" || bad "note file name" "$(ls handoff/sessions)"
body="$(cat "$note" 2>/dev/null)"
expect_contains "note records cloud environment" "$body" "Environment: cloud session"
expect_contains "note records uncommitted work" "$body" "src/wip.py"
expect_contains "note records needs-local" "$body" "check in simulator"
last="$(g log -1 --name-only --format=%s)"
expect_contains "commit message" "$last" "handoff(limit): util change done"
expect_absent "commit contains only the note, not wip code" "$last" "src/wip.py"
CLAUDE_CODE_REMOTE_SESSION_ID=cse_TEST123 python3 "$H" write --summary "second entry" >/dev/null
n="$(ls handoff/sessions/*.md | wc -l | tr -d ' ')"
expect_code "same session appends to same file" "$n" 1
g push -q origin feature-a 2>/dev/null
g checkout -q feature-b 2>/dev/null
out="$(python3 "$H" read --all-branches 2>&1)"
expect_contains "read on another branch sees feature-a note" "$out" "origin/feature-a: "
expect_contains "read shows other branch summary" "$out" "second entry"
g checkout -q feature-a 2>/dev/null
out="$(python3 "$H" read)"
expect_contains "read shows HANDOFF.md" "$out" "## Decisions"
expect_contains "read shows git state" "$out" "uncommitted files:"
rm -f src/wip.py

echo "# portable-env / env_audit.py"
E="$S/portable-env/scripts/env_audit.py"
fh="$tmp/fakehome"
mkdir -p "$fh/.claude/skills/my-skill" "$fh/.claude/skills/shared-skill" "$fh/.claude/agents"
printf -- '---\nname: my-skill\ndescription: x\n---\nuse ~/.claude/data\n' > "$fh/.claude/skills/my-skill/SKILL.md"
printf -- '---\nname: shared-skill\ndescription: x\n---\nok\n' > "$fh/.claude/skills/shared-skill/SKILL.md"
printf -- '---\nname: rev\ndescription: x\n---\n' > "$fh/.claude/agents/rev.md"
echo "# personal rules" > "$fh/.claude/CLAUDE.md"
cat > "$fh/.claude/settings.json" <<'EOF'
{"hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"/Users/me/secret-hook.sh"}]}]},
 "enabledPlugins":{"foo@bar":true}}
EOF
cat > "$fh/.claude.json" <<EOF
{"mcpServers":{"notes":{"command":"x","env":{"API_TOKEN":"sk-SECRET-VALUE-123"}}},
 "projects":{"$tmp/a":{"mcpServers":{"localdb":{"command":"y"}}}}}
EOF
mkdir -p .claude/skills/shared-skill && cp "$fh/.claude/skills/shared-skill/SKILL.md" .claude/skills/shared-skill/
g add .claude && g commit -qm "shared skill"
out="$(python3 "$E" --repo "$tmp/a" --home "$fh")"
expect_contains "lists personal skill missing from repo" "$out" "| skill | my-skill | no |"
expect_contains "recognizes committed equivalent" "$out" "| skill | shared-skill | yes (tracked) |"
expect_contains "lists personal agent" "$out" "| agent | rev | no |"
expect_contains "lists user hook event" "$out" "| hook event | PreToolUse | no |"
expect_contains "lists user MCP server name" "$out" "| MCP server | notes | no |"
expect_contains "lists local-scope MCP server" "$out" "| MCP server | localdb | no |"
expect_contains "plugin advice" "$out" "Project settings > Plugins"
expect_absent "never prints MCP secret values" "$out" "sk-SECRET-VALUE-123"
expect_absent "never prints hook commands" "$out" "secret-hook.sh"
out="$(python3 "$E" --repo "$tmp/a" --home "$fh" --copy-skill my-skill)"
expect_contains "copy-skill copies into repo" "$out" ".claude/skills/my-skill"
python3 "$E" --repo "$tmp/a" --home "$fh" --copy-skill my-skill >/dev/null 2>&1
expect_code "copy refuses overwrite without --force" $? 1
out="$(python3 "$E" --repo "$tmp/a" --home "$fh")"
expect_contains "copied skill shows as present but untracked" "$out" "my-skill (UNTRACKED)"
expect_contains "portability scan flags ~/.claude reference" "$out" ".claude/skills/my-skill/SKILL.md:5 — reference to ~/.claude"
python3 "$E" --repo "$tmp/a" --home "$fh" --strict >/dev/null
expect_code "--strict exits 1 with untracked/portability issues" $? 1
python3 "$E" --repo "$tmp/a" --home "$fh" --json | python3 -c 'import json,sys; json.load(sys.stdin)' \
  && ok "--json is valid" || bad "--json invalid"

echo "# scripts/install.sh"
mkdir -p "$tmp/target" && (cd "$tmp/target" && g init -q)
out="$(bash "$here/scripts/install.sh" --repo "$tmp/target")"
expect_contains "installs into repo .claude/skills" "$out" "installed: $tmp/target/.claude/skills/integration-review"
[ -x "$tmp/target/.claude/skills/project-handoff/scripts/handoff.py" ] && ok "scripts executable after install" || bad "exec bit"
out="$(bash "$here/scripts/install.sh" --repo "$tmp/target" project-handoff)"
expect_contains "does not overwrite without --force" "$out" "skip:"

echo "# SKILL.md validation"
out="$(python3 "$here/tests/validate_skills.py")"; code=$?
echo "$out" | sed 's/^/    /'
expect_code "all SKILL.md files valid" $code 0

echo
echo "passed: $pass  failed: $fail"
[ "$fail" -eq 0 ]

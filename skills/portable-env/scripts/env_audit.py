#!/usr/bin/env python3
"""Audit which parts of your local Claude Code setup will reach a cloud session.

Cloud sessions (and Projects threads) start from a fresh clone of the repository.
Only what is committed there travels; ~/.claude does not. This script lists:

  * personal items (~/.claude skills/agents/commands, CLAUDE.md, hooks, plugins,
    user/local-scope MCP servers) and whether the repo has a committed equivalent
  * repo items under .claude/ and .mcp.json, and whether they are tracked by git
  * portability problems in committed files (absolute home paths, ~/.claude refs)

It prints names only. It never prints MCP env values, headers or hook commands.

Usage:
  env_audit.py [--repo PATH] [--home PATH] [--json] [--strict]
  env_audit.py --copy-skill NAME [--copy-agent NAME] [--force]

Standard library only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PORTABILITY_PATTERNS = [
    (re.compile(r"/Users/[^/\s\"']+"), "absolute macOS home path"),
    (re.compile(r"/home/[^/\s\"']+"), "absolute Linux home path"),
    (re.compile(r"~/\.claude"), "reference to ~/.claude (not present in cloud sessions)"),
    (re.compile(r"\$HOME/\.claude"), "reference to $HOME/.claude (not present in cloud sessions)"),
]
TEXT_SUFFIXES = {".md", ".json", ".sh", ".py", ".js", ".ts", ".txt", ".yaml", ".yml", ".toml"}


def git_root(start: Path) -> Path:
    p = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return Path(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else start


def tracked(repo: Path, rel: str) -> bool:
    p = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=repo,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.returncode == 0


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def list_skills(base: Path) -> list[str]:
    d = base / "skills"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if (p / "SKILL.md").is_file())


def list_md(base: Path, sub: str) -> list[str]:
    d = base / sub
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.rglob("*.md"))


def hook_events(settings: dict) -> list[str]:
    hooks = settings.get("hooks") or {}
    return sorted(hooks.keys()) if isinstance(hooks, dict) else []


def enabled_plugins(settings: dict) -> list[str]:
    ep = settings.get("enabledPlugins") or {}
    if isinstance(ep, dict):
        return sorted(k for k, v in ep.items() if v)
    if isinstance(ep, list):
        return sorted(str(x) for x in ep)
    return []


def collect(repo: Path, home: Path) -> dict:
    uc = home / ".claude"
    user_settings = load_json(uc / "settings.json")
    claude_json = load_json(home / ".claude.json")
    user_mcp = sorted((claude_json.get("mcpServers") or {}).keys())
    local_mcp: list[str] = []
    projects = claude_json.get("projects") or {}
    for key, val in projects.items():
        try:
            same = Path(key).resolve() == repo.resolve()
        except OSError:
            same = False
        if same and isinstance(val, dict):
            local_mcp = sorted((val.get("mcpServers") or {}).keys())
            break

    rc = repo / ".claude"
    repo_settings_rel = ".claude/settings.json"
    repo_settings = load_json(repo / repo_settings_rel)
    mcp_json = load_json(repo / ".mcp.json")

    def tracked_items(sub: str, names: list[str], skill: bool = False) -> dict:
        out = {}
        for n in names:
            rel = f".claude/{sub}/{n}/SKILL.md" if skill else None
            if not skill:
                hits = list((rc / sub).rglob(f"{n}.md"))
                rel = hits[0].relative_to(repo).as_posix() if hits else f".claude/{sub}/{n}.md"
            out[n] = tracked(repo, rel)
        return out

    repo_claude_md = [p for p in ("CLAUDE.md", ".claude/CLAUDE.md") if (repo / p).is_file()]
    return {
        "repo": str(repo),
        "personal": {
            "skills": list_skills(uc),
            "agents": list_md(uc, "agents"),
            "commands": list_md(uc, "commands"),
            "claude_md": (uc / "CLAUDE.md").is_file(),
            "hook_events": hook_events(user_settings),
            "plugins": enabled_plugins(user_settings),
            "mcp_user_scope": user_mcp,
            "mcp_local_scope": local_mcp,
        },
        "repo_items": {
            "skills": tracked_items("skills", list_skills(rc), skill=True),
            "agents": tracked_items("agents", list_md(rc, "agents")),
            "commands": tracked_items("commands", list_md(rc, "commands")),
            "claude_md": {p: tracked(repo, p) for p in repo_claude_md},
            "settings_json_tracked": tracked(repo, repo_settings_rel) if (repo / repo_settings_rel).is_file() else None,
            "hook_events": hook_events(repo_settings),
            "plugins": enabled_plugins(repo_settings),
            "mcp_json_servers": sorted((mcp_json.get("mcpServers") or {}).keys()),
            "mcp_json_tracked": tracked(repo, ".mcp.json") if (repo / ".mcp.json").is_file() else None,
            "settings_local_exists": (repo / ".claude/settings.local.json").is_file(),
        },
        "portability": scan_portability(repo),
    }


def scan_portability(repo: Path) -> list[dict]:
    findings = []
    targets = []
    rc = repo / ".claude"
    if rc.is_dir():
        targets += [p for p in rc.rglob("*") if p.is_file() and p.suffix in TEXT_SUFFIXES]
    for extra in ("CLAUDE.md", ".mcp.json"):
        if (repo / extra).is_file():
            targets.append(repo / extra)
    for p in targets:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines, 1):
            for rx, why in PORTABILITY_PATTERNS:
                if rx.search(line):
                    findings.append({"file": p.relative_to(repo).as_posix(), "line": i, "issue": why})
                    break
    return findings


def yn(v) -> str:
    return "yes" if v else "no"


def render(r: dict) -> str:
    P, R = r["personal"], r["repo_items"]
    out = [f"# Portable environment audit — {r['repo']}", ""]
    out.append("## Personal items that will NOT reach a cloud session")
    out.append("")
    out.append("| Kind | Name | Committed equivalent in repo? |")
    out.append("|---|---|---|")
    for kind, key in (("skill", "skills"), ("agent", "agents"), ("command", "commands")):
        for n in P[key]:
            eq = R[key].get(n)
            out.append(f"| {kind} | {n} | {'yes (tracked)' if eq else ('present, NOT committed' if eq is False else 'no')} |")
    if P["claude_md"]:
        out.append(f"| CLAUDE.md | ~/.claude/CLAUDE.md | repo CLAUDE.md: {', '.join(R['claude_md']) or 'none'} |")
    for e in P["hook_events"]:
        out.append(f"| hook event | {e} | {'repo has ' + e if e in R['hook_events'] else 'no'} |")
    for n in P["plugins"]:
        out.append(f"| plugin | {n} | cloud: add in Project settings > Plugins (repo enabledPlugins is not loaded) |")
    for n in P["mcp_user_scope"] + P["mcp_local_scope"]:
        out.append(f"| MCP server | {n} | {'in .mcp.json' if n in R['mcp_json_servers'] else 'no'} |")
    out.append("")
    out.append("## Repo items (travel only if committed)")
    out.append("")
    for key in ("skills", "agents", "commands"):
        items = R[key]
        if items:
            out.append(f"- {key}: " + ", ".join(f"{n} ({'tracked' if t else 'UNTRACKED'})" for n, t in items.items()))
    for p, t in R["claude_md"].items():
        out.append(f"- {p}: {'tracked' if t else 'UNTRACKED'}")
    if R["settings_json_tracked"] is not None:
        out.append(f"- .claude/settings.json: {'tracked' if R['settings_json_tracked'] else 'UNTRACKED'};"
                   f" hook events: {', '.join(R['hook_events']) or 'none'}")
    if R["mcp_json_tracked"] is not None:
        out.append(f"- .mcp.json: {'tracked' if R['mcp_json_tracked'] else 'UNTRACKED'};"
                   f" servers: {', '.join(R['mcp_json_servers']) or 'none'}")
    if R["settings_local_exists"]:
        out.append("- .claude/settings.local.json exists: personal file, normally not committed; it does not travel.")
    out.append("")
    out.append("## Caveats from the docs")
    out.append("")
    out.append("- Hooks, permission rules and `.mcp.json` apply in a cloud session with ONE repository."
               " In a Projects thread with several repositories they do not apply; CLAUDE.md and"
               " .claude/skills|agents|commands still load from every repository.")
    out.append("- Plugins enabled in the repo's .claude/settings.json are not installed in cloud sessions.")
    out.append("- MCP in cloud threads comes from claude.ai connectors (plus a single repo's .mcp.json).")
    out.append("")
    out.append(f"## Portability problems in committed config ({len(r['portability'])})")
    out.append("")
    for f in r["portability"]:
        out.append(f"- {f['file']}:{f['line']} — {f['issue']}")
    return "\n".join(out) + "\n"


def copy_item(src: Path, dst: Path, force: bool) -> str:
    if not src.exists():
        raise SystemExit(f"error: {src} does not exist")
    if dst.exists():
        if not force:
            raise SystemExit(f"error: {dst} exists (use --force to overwrite)")
        shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return str(dst)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--home", default=str(Path.home()), help="home directory to audit (for testing)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 if portability problems or untracked items exist")
    ap.add_argument("--copy-skill", action="append", default=[], metavar="NAME")
    ap.add_argument("--copy-agent", action="append", default=[], metavar="NAME")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    repo = git_root(Path(a.repo).resolve())
    home = Path(a.home).expanduser()

    if a.copy_skill or a.copy_agent:
        for n in a.copy_skill:
            print("copied " + copy_item(home / ".claude/skills" / n, repo / ".claude/skills" / n, a.force))
        for n in a.copy_agent:
            print("copied " + copy_item(home / ".claude/agents" / f"{n}.md", repo / ".claude/agents" / f"{n}.md", a.force))
        print("next: review the copied files for secrets and absolute paths, run the audit again, then commit.")
        return 0

    r = collect(repo, home)
    print(json.dumps(r, indent=2, ensure_ascii=False) if a.json else render(r), end="" if not a.json else "\n")
    if a.strict:
        R = r["repo_items"]
        untracked = any(v is False for k in ("skills", "agents", "commands", "claude_md") for v in R[k].values())
        untracked |= R["settings_json_tracked"] is False or R["mcp_json_tracked"] is False
        if r["portability"] or untracked:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

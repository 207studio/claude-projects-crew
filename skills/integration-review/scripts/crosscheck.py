#!/usr/bin/env python3
"""Cross-check this branch against the base branch and every other open branch/PR.

A session that only reviews its own diff misses what other sessions changed.
This script reports, from git alone (gh is optional):

  1. files this branch changes (committed since the merge-base + uncommitted)
  2. base drift: files the base branch changed since you branched that you also touch
  3. merge conflicts with the base (git merge-tree, no working-tree changes)
  4. for every other unmerged branch: overlapping files and predicted conflicts
  5. high-blast-radius files (lockfiles, manifests, CI, migrations, shared config)
  6. deleted/renamed files that are still referenced elsewhere in the repo

Usage:
  crosscheck.py [--base origin/main] [--repo PATH] [--fetch] [--gh] [--strict] [--json]

Exit code: 0 = report printed; with --strict, 1 if conflicts or overlaps were found.
Requires git >= 2.38 for conflict prediction (falls back to overlap-only).
Standard library only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BLAST_PATTERNS = [
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "requirements*.txt", "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile*",
    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock", "Gemfile*", "*.gradle*", "pom.xml",
    "Podfile*", "*.xcodeproj/*", "Package.swift", "Package.resolved",
    ".github/*", ".gitlab-ci.yml", "Dockerfile*", "docker-compose*", "Makefile",
    "*migrations/*", "*migrate*", "*.sql", "*schema*",
    "tsconfig*.json", ".eslintrc*", "*.config.js", "*.config.ts", ".env.example",
    "CLAUDE.md", "REVIEW.md", ".claude/*", ".mcp.json",
    "*/index.ts", "*/index.js", "*/__init__.py", "*/api/*", "*/types/*",
]


def sh(args: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess:
    p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"error: {' '.join(args)}: {p.stderr.strip()}")
    return p


def git(root: Path, *args: str, check: bool = False) -> str:
    return sh(["git", *args], root, check).stdout


def lines(s: str) -> list[str]:
    return [x for x in s.splitlines() if x.strip()]


def resolve_base(root: Path, base: str | None) -> str:
    candidates = [base] if base else ["origin/main", "origin/master", "main", "master"]
    for c in candidates:
        if sh(["git", "rev-parse", "--verify", "--quiet", c + "^{commit}"], root).returncode == 0:
            return c
    raise SystemExit(f"error: base branch not found (tried {', '.join(candidates)}); pass --base")


def changed_since(root: Path, base: str, ref: str) -> tuple[set[str], set[str]]:
    """Return (changed, deleted_or_renamed_from) between merge-base(base, ref) and ref."""
    mb = git(root, "merge-base", base, ref).strip()
    if not mb:
        return set(), set()
    out = git(root, "diff", "--name-status", "-M", mb, ref)
    changed, gone = set(), set()
    for ln in lines(out):
        parts = ln.split("\t")
        st = parts[0]
        if st.startswith("R") and len(parts) == 3:
            changed.update([parts[1], parts[2]])
            gone.add(parts[1])
        elif st.startswith("D"):
            changed.add(parts[1])
            gone.add(parts[1])
        else:
            changed.add(parts[-1])
    return changed, gone


def uncommitted(root: Path) -> set[str]:
    files = set()
    for ln in git(root, "status", "--porcelain").splitlines():
        if ln.strip():
            path = ln[3:]
            files.add(path.split(" -> ")[-1])
    return files


def merge_tree_conflicts(root: Path, a: str, b: str) -> list[str] | None:
    """Predict conflicts of merging a and b. None if git lacks merge-tree --write-tree."""
    p = sh(["git", "merge-tree", "--write-tree", "--name-only", "--no-messages", a, b], root)
    if p.returncode == 0:
        return []
    if p.returncode == 1:
        out = lines(p.stdout)
        return sorted(set(out[1:]))  # first line is the tree id
    return None


def blast(files: set[str]) -> list[str]:
    hits = []
    for f in sorted(files):
        name = f.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatch(f, pat) or fnmatch.fnmatch(name, pat) for pat in BLAST_PATTERNS):
            hits.append(f)
    return hits


def dangling_refs(root: Path, gone: set[str], limit: int = 5) -> dict[str, list[str]]:
    res = {}
    for g in sorted(gone):
        stem = Path(g).stem
        if len(stem) < 4 or stem in ("index", "__init__", "main", "README"):
            continue
        # file name, or the stem as a whole word (import util, require('./util'), "util")
        out = git(root, "grep", "-l", "-F", "-e", Path(g).name, "--", ".")
        out += "\n" + git(root, "grep", "-l", "-w", "-F", "-e", stem, "--", ".")
        refs = sorted(set(x for x in lines(out) if x != g))
        if refs:
            res[g] = refs[:limit]
    return res


def gh_prs(root: Path) -> dict[str, dict]:
    if not shutil.which("gh"):
        return {}
    p = sh(["gh", "pr", "list", "--state", "open", "--limit", "100",
            "--json", "number,title,headRefName,baseRefName,files"], root)
    if p.returncode != 0:
        return {"__error__": {"msg": p.stderr.strip()[:300]}}
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return {}
    return {d["headRefName"]: d for d in data}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--fetch", action="store_true", help="git fetch --prune origin first")
    ap.add_argument("--gh", action="store_true", help="also read open PRs with gh (needs auth)")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    root = Path(git(Path(a.repo), "rev-parse", "--show-toplevel", check=True).strip())
    if a.fetch:
        sh(["git", "fetch", "--prune", "origin"], root)
    base = resolve_base(root, a.base)
    head_name = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    head_sha = git(root, "rev-parse", "HEAD").strip()
    base_sha = git(root, "rev-parse", base).strip()

    mine, gone = changed_since(root, base, "HEAD")
    dirty = uncommitted(root)
    mine_all = mine | dirty
    mb = git(root, "merge-base", base, "HEAD").strip()
    base_moved = set(lines(git(root, "diff", "--name-only", mb, base))) if mb else set()
    drift = sorted(mine_all & base_moved)
    base_conf = merge_tree_conflicts(root, base, "HEAD")

    prs = gh_prs(root) if a.gh else {}
    gh_error = prs.pop("__error__", None) if prs else None

    others = []
    refs = lines(git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes"))
    seen_sha = {head_sha, base_sha}
    for ref in refs:
        if ref.endswith("/HEAD") or ref in (head_name, base) or ref.split("/", 1)[-1] == head_name:
            continue
        sha = git(root, "rev-parse", ref).strip()
        if sha in seen_sha:
            continue
        if sh(["git", "merge-base", "--is-ancestor", ref, base], root).returncode == 0:
            continue  # already merged into base
        seen_sha.add(sha)
        theirs, _ = changed_since(root, base, ref)
        overlap = sorted(mine_all & theirs)
        conf = merge_tree_conflicts(root, "HEAD", ref) if overlap else []
        short = ref.split("/", 1)[1] if ref.startswith("origin/") else ref
        pr = prs.get(short)
        others.append({
            "ref": ref, "files_changed": len(theirs), "overlap": overlap,
            "conflicts": conf, "pr": (f"#{pr['number']} {pr['title']}" if pr else None),
        })

    report = {
        "branch": head_name, "base": base, "changed": sorted(mine), "uncommitted": sorted(dirty),
        "base_drift": drift, "base_conflicts": base_conf, "others": others,
        "blast_radius": blast(mine_all), "dangling_references": dangling_refs(root, gone),
        "gh": ("error: " + gh_error["msg"]) if gh_error else ("used" if a.gh else "not used"),
    }

    if a.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        o = [f"# Integration cross-check — `{head_name}` vs `{base}`", ""]
        o.append(f"- Files changed on this branch: {len(mine)} committed, {len(dirty)} uncommitted")
        if base_conf is None:
            o.append("- Conflict prediction with base: unavailable (git < 2.38)")
        else:
            o.append(f"- Conflicts if merged into base now: {len(base_conf)}" + (" — " + ", ".join(base_conf) if base_conf else ""))
        o.append(f"- Base changed these files since you branched (re-read them): {len(drift)}" + (" — " + ", ".join(drift) if drift else ""))
        o.append(f"- GitHub PR metadata: {report['gh']}")
        o.append("")
        o.append(f"## Other unmerged branches ({len(others)})")
        o.append("")
        if others:
            o.append("| Branch | PR | Files | Overlap with you | Predicted conflicts |")
            o.append("|---|---|---|---|---|")
            for x in others:
                conf = "n/a" if x["conflicts"] is None else (", ".join(x["conflicts"]) or "none")
                o.append(f"| {x['ref']} | {x['pr'] or '-'} | {x['files_changed']} | {', '.join(x['overlap']) or '-'} | {conf} |")
        o.append("")
        o.append(f"## High blast-radius files you touch ({len(report['blast_radius'])})")
        o.append("")
        o += [f"- {f}" for f in report["blast_radius"]] or ["- none"]
        o.append("")
        o.append(f"## Deleted/renamed files possibly still referenced ({len(report['dangling_references'])})")
        o.append("")
        for g, refs_ in report["dangling_references"].items():
            o.append(f"- {g} ← " + ", ".join(refs_))
        if not report["dangling_references"]:
            o.append("- none")
        print("\n".join(o))

    if a.strict:
        bad = bool(base_conf) or bool(drift) or any(x["overlap"] for x in others) or bool(report["dangling_references"])
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

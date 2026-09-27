#!/usr/bin/env python3
"""Validate every skills/*/SKILL.md against the Agent Skills spec (agentskills.io/specification).

Checks: frontmatter present; name 1-64 chars, [a-z0-9-], no leading/trailing/double
hyphen, equals directory name; description 1-1024 chars; compatibility <= 500;
only spec fields; body non-empty and SKILL.md under 500 lines; referenced
relative files exist. No PyYAML needed (frontmatter here uses simple `key: value` lines).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, text, ["missing opening ---"]
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text, ["missing closing ---"]
    fm, body = text[4:end], text[end + 5:]
    data, errs = {}, []
    for ln in fm.splitlines():
        if not ln.strip() or ln.startswith(" "):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", ln)
        if not m:
            errs.append(f"unparsable frontmatter line: {ln[:60]}")
            continue
        val = m.group(2).strip()
        if val[:1] in "\"'" and val[-1:] == val[:1]:
            val = val[1:-1]
        if val[:1] in "[{&*!|>":
            errs.append(f"{m.group(1)}: value starts with YAML indicator {val[:1]!r}; quote it")
        if ": " in val and not m.group(2).strip()[:1] in "\"'":
            errs.append(f"{m.group(1)}: unquoted ': ' inside value breaks YAML")
        data[m.group(1)] = val
    return data, body, errs


def check(skill_dir: Path) -> list[str]:
    errs = []
    p = skill_dir / "SKILL.md"
    data, body, perrs = parse(p)
    errs += perrs
    if data is None:
        return errs
    name = data.get("name", "")
    if not (1 <= len(name) <= 64) or not NAME_RX.match(name):
        errs.append(f"invalid name {name!r}")
    if name != skill_dir.name:
        errs.append(f"name {name!r} != directory {skill_dir.name!r}")
    desc = data.get("description", "")
    if not (1 <= len(desc) <= 1024):
        errs.append(f"description length {len(desc)} not in 1..1024")
    if "compatibility" in data and not (1 <= len(data["compatibility"]) <= 500):
        errs.append("compatibility length not in 1..500")
    extra = set(data) - SPEC_FIELDS
    if extra:
        errs.append(f"non-spec fields: {sorted(extra)}")
    if not body.strip():
        errs.append("empty body")
    n_lines = len(p.read_text(encoding="utf-8").splitlines())
    if n_lines >= 500:
        errs.append(f"SKILL.md has {n_lines} lines (keep under 500)")
    for ref in re.findall(r"`((?:references|scripts)/[^`#\s]+)", body):
        if not (skill_dir / ref).exists():
            errs.append(f"referenced file missing: {ref}")
    return errs


def main() -> int:
    dirs = sorted(d for d in (ROOT / "skills").iterdir() if d.is_dir())
    bad = 0
    for d in dirs:
        errs = check(d)
        data, _, _ = parse(d / "SKILL.md")
        info = f"desc {len(data.get('description', ''))} chars" if data else ""
        print(f"{'OK  ' if not errs else 'FAIL'} {d.name} {info}")
        for e in errs:
            print(f"     - {e}")
        bad += bool(errs)
    print(f"{len(dirs) - bad}/{len(dirs)} skills valid")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

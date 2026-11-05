#!/usr/bin/env python3
"""Audit Agent Skills for description quality and trigger-surface collisions.

Reads every `*/SKILL.md` under the given roots, parses the YAML frontmatter, and
reports two classes of problem:

  1. Per-skill defects — a description an agent cannot route on: missing, too
     short, no trigger language, or a name that disagrees with its directory.
  2. Pairwise collisions — two skills whose descriptions compete for the same
     request, measured by Jaccard overlap on content words.

Under progressive disclosure an agent sees only `name` and `description` before
deciding which skill to load, so these two fields are the entire routing
surface. A skill the agent cannot find is a skill you do not have.

Standard library only, so it runs under any harness without a install step.

Usage:
    python3 audit_skills.py [ROOT ...] [--threshold 0.35] [--json] [--quiet]

With no ROOT, scans the conventional locations:
    ~/.claude/skills, ~/.claude/plugins, ./.claude/skills, ./.agents/skills, ./skills
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Words carrying no routing signal. Kept deliberately small: an aggressive stop
# list hides real overlap by deleting the very words two skills share.
STOPWORDS = {
    "a", "an", "and", "the", "to", "of", "for", "in", "on", "with", "when",
    "this", "that", "it", "is", "are", "be", "or", "as", "by", "from", "at",
    "use", "used", "using", "user", "users", "you", "your", "should", "can",
    "will", "into", "them", "they", "if", "any", "all", "each", "their",
}

# Phrases that tell an agent *when* to fire, not just what the skill does.
TRIGGER_PATTERNS = [
    r"\buse (?:this|it) when\b",
    r"\buse when\b",
    r"\buse before\b",
    r"\bwhen the user\b",
    r"\btrigger(?:s|ed)? (?:on|when)\b",
    r"\binvoke when\b",
    r"\bcall (?:this|it) when\b",
    r"\bfor when\b",
]

MIN_DESCRIPTION_CHARS = 40

DEFAULT_ROOTS = [
    "~/.claude/skills",
    "~/.claude/plugins",
    "./.claude/skills",
    "./.agents/skills",
    "./skills",
]


@dataclass
class Skill:
    path: str
    directory: str
    name: str = ""
    description: str = ""
    defects: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name or self.directory


@dataclass
class Collision:
    a: str
    b: str
    overlap: float
    shared: list[str]
    a_path: str
    b_path: str


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract top-level scalar keys from YAML frontmatter.

    Deliberately not a YAML parser. It handles the four forms that appear in
    real SKILL.md files -- inline scalars, plain multi-line scalars, `|` literal
    blocks, and `>` folded blocks -- and ignores everything else rather than
    failing on a file it does not fully understand. A partial read still tells you whether `description`
    is missing, which is the question being asked.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]

    fields: dict[str, str] = {}
    key: str | None = None
    buffer: list[str] = []
    block_indent: int | None = None

    def flush() -> None:
        nonlocal key, buffer, block_indent
        if key is not None:
            fields[key] = " ".join(p.strip() for p in buffer if p.strip()).strip()
        key, buffer, block_indent = None, [], None

    for line in block.splitlines():
        if not line.strip():
            if key is not None:
                buffer.append("")
            continue

        indent = len(line) - len(line.lstrip())
        # A continuation line of a block scalar.
        if key is not None and block_indent is not None and indent >= block_indent:
            buffer.append(line)
            continue

        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not match:
            if key is not None and indent > 0:
                buffer.append(line)
            continue

        flush()
        key, value = match.group(1), match.group(2).strip()
        # An empty value opens a plain multi-line scalar: the text sits on the
        # indented lines that follow, so collect them like a block scalar.
        if value in ("", "|", ">", "|-", ">-", "|+", ">+"):
            block_indent = indent + 1
            buffer = []
        else:
            buffer = [value.strip("'\"")]
            block_indent = None
            flush()

    flush()
    return fields


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def has_trigger_language(description: str) -> bool:
    low = description.lower()
    return any(re.search(p, low) for p in TRIGGER_PATTERNS)


def find_skills(roots: list[Path]) -> list[Skill]:
    seen: set[Path] = set()
    skills: list[Skill] = []
    for root in roots:
        if not root.exists():
            continue
        for skill_md in sorted(root.rglob("SKILL.md")):
            resolved = skill_md.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                text = skill_md.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"warning: cannot read {skill_md}: {exc}", file=sys.stderr)
                continue
            fm = parse_frontmatter(text)
            skills.append(
                Skill(
                    path=str(skill_md),
                    directory=skill_md.parent.name,
                    name=fm.get("name", ""),
                    description=fm.get("description", ""),
                )
            )
    return skills


def grade(skill: Skill) -> None:
    if not skill.name:
        skill.defects.append("no name in frontmatter")
    elif skill.name != skill.directory:
        skill.defects.append(f"name '{skill.name}' != directory '{skill.directory}'")

    if not skill.description:
        skill.defects.append("no description -- agent cannot route to this skill")
        return

    if len(skill.description) < MIN_DESCRIPTION_CHARS:
        skill.defects.append(
            f"description is {len(skill.description)} chars "
            f"(under {MIN_DESCRIPTION_CHARS}); too thin to disambiguate"
        )

    if not has_trigger_language(skill.description):
        skill.defects.append(
            "description says what it does but never when to use it "
            "(no 'use when' / 'when the user' clause)"
        )


def find_duplicates(skills: list[Skill]) -> dict[str, list[str]]:
    """Group skills that share a name.

    Usually version shadowing: a plugin cache holding 5.0.7 and 6.3.0 side by
    side exposes every skill twice. These are not competing descriptions, they
    are the same skill counted twice, and folding them into the collision list
    inflates it beyond use.
    """
    by_name: dict[str, list[str]] = {}
    for s in skills:
        if s.name:
            by_name.setdefault(s.name, []).append(s.path)
    return {n: sorted(p) for n, p in by_name.items() if len(p) > 1}


def find_collisions(skills: list[Skill], threshold: float) -> list[Collision]:
    """Overlap between skills with *different* names.

    Same-name pairs are handled by find_duplicates and excluded here.
    """
    described = [s for s in skills if s.description]
    tokens = {s.path: tokenize(s.description) for s in described}
    collisions: list[Collision] = []
    for i, a in enumerate(described):
        for b in described[i + 1:]:
            if a.name and b.name and a.name == b.name:
                continue
            score = jaccard(tokens[a.path], tokens[b.path])
            if score >= threshold:
                shared = sorted(tokens[a.path] & tokens[b.path])
                collisions.append(
                    Collision(
                        a=a.label, b=b.label, overlap=round(score, 3),
                        shared=shared[:12], a_path=a.path, b_path=b.path,
                    )
                )
    collisions.sort(key=lambda c: c.overlap, reverse=True)
    return collisions


def report(
    skills: list[Skill],
    collisions: list[Collision],
    duplicates: dict[str, list[str]],
    threshold: float,
) -> None:
    flagged = [s for s in skills if s.defects]
    width = 66

    print()
    print(f"whetstone skill audit -- {len(skills)} skills scanned")
    print("-" * width)

    if not skills:
        print("No SKILL.md files found. Pass a root explicitly.")
        return

    no_desc = sum(1 for s in skills if not s.description)
    no_trigger = sum(
        1 for s in skills
        if s.description and not has_trigger_language(s.description)
    )
    thin = sum(
        1 for s in skills
        if s.description and len(s.description) < MIN_DESCRIPTION_CHARS
    )

    print(f"  missing description        {no_desc:>4}")
    print(f"  no trigger language        {no_trigger:>4}")
    print(f"  description under {MIN_DESCRIPTION_CHARS} chars {thin:>4}")
    print(f"  colliding pairs (>={threshold})  {len(collisions):>4}")
    print(f"  duplicate names            {len(duplicates):>4}")
    print(f"  skills with >=1 defect     {len(flagged):>4}"
          f"  ({len(flagged) * 100 // max(len(skills), 1)}%)")
    print()

    if duplicates:
        print("Duplicate skill names (usually version shadowing)")
        print("-" * width)
        for name, paths in sorted(duplicates.items()):
            print(f"  {name}  ({len(paths)} copies)")
            for p in paths:
                print(f"    {p}")
        print()
        print("  Which copy wins depends on your harness's load order. Prune the")
        print("  stale versions rather than trusting the resolution to be stable.")
        print()

    if flagged:
        print("Per-skill defects")
        print("-" * width)
        for s in flagged:
            print(f"  {s.label}")
            print(f"    {s.path}")
            for d in s.defects:
                print(f"    - {d}")
        print()

    if collisions:
        print(f"Trigger-surface collisions (Jaccard >= {threshold})")
        print("-" * width)
        for c in collisions:
            print(f"  {c.overlap:.2f}  {c.a}  <->  {c.b}")
            print(f"        shared: {', '.join(c.shared)}")
        print()
        print("  For each pair, decide which skill owns the request, then make")
        print("  each description name a case the other explicitly excludes.")
        print()

    if not flagged and not collisions:
        print("No defects and no collisions. Nothing to sharpen.")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit Agent Skills for routing defects and overlap."
    )
    parser.add_argument("roots", nargs="*", help="directories to scan")
    parser.add_argument(
        "--threshold", type=float, default=0.35,
        help="Jaccard overlap at which two descriptions are judged to collide "
             "(default: 0.35)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--quiet", action="store_true",
        help="print the summary counts only, no per-item detail",
    )
    args = parser.parse_args(argv)

    raw_roots = args.roots or DEFAULT_ROOTS
    roots = [Path(os.path.expanduser(r)).resolve() for r in raw_roots]

    skills = find_skills(roots)
    for s in skills:
        grade(s)
    collisions = find_collisions(skills, args.threshold)
    duplicates = find_duplicates(skills)

    if args.json:
        print(json.dumps(
            {
                "scanned": len(skills),
                "roots": [str(r) for r in roots],
                "threshold": args.threshold,
                "skills": [asdict(s) for s in skills],
                "collisions": [asdict(c) for c in collisions],
                "duplicates": duplicates,
            },
            indent=2,
        ))
    elif args.quiet:
        flagged = sum(1 for s in skills if s.defects)
        print(f"{len(skills)} scanned, {flagged} flagged, "
              f"{len(collisions)} collisions, {len(duplicates)} duplicate names")
    else:
        report(skills, collisions, duplicates, args.threshold)

    # Non-zero when something needs attention, so this can gate CI.
    return 1 if any(s.defects for s in skills) or collisions or duplicates else 0


if __name__ == "__main__":
    sys.exit(main())

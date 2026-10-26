#!/usr/bin/env python3
"""Audit Agent Skills for description quality and trigger-surface collisions.

Reads every `*/SKILL.md` under the given roots, parses the YAML frontmatter, and
reports two classes of problem:

  1. Per-skill defects — a description an agent cannot route on: missing, too
     short, no trigger language, a name that disagrees with its directory, or
     routing text parked in a frontmatter field the harness never reads.
  2. Pairwise collisions — two skills whose descriptions compete for the same
     request, measured by Jaccard overlap on content words.

It also grades subagent definitions (`agents/*.md`) on the same routing surface,
because a plugin's agents route on `name` + `description` exactly like its
skills do, and a broken agent header is invisible to a skills-only scan.

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
    # "use this when", "use it when", and the very common "use this skill when"
    # / "use this agent when".
    r"\buse (?:this|it)(?: (?:skill|agent|tool|command|plugin))? when\b",
    r"\buse when\b",
    r"\bwhen the user\b",
    r"\btrigger(?:s|ed)? (?:on|when)\b",
    r"\binvoke when\b",
    r"\bcall (?:this|it) when\b",
    r"\bfor when\b",
    # Claude Code's own convention for agents that should be picked unprompted.
    r"\buse proactively\b",
]

# Frontmatter keys that look like routing metadata but that no major harness
# reads. Text placed here never reaches the router, so it is a silent defect.
UNREAD_SKILL_KEYS = {
    "triggers": "move these phrases into `description`",
}
UNREAD_AGENT_KEYS = {
    "identifier": "rename to `name`",
    "whenToUse": "fold this text into `description`",
    "triggers": "move these phrases into `description`",
}

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
    keys: list[str] = field(default_factory=list)

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

    Deliberately not a YAML parser. It handles the three forms that appear in
    real SKILL.md files -- inline scalars, `|` literal blocks, and `>` folded
    blocks -- and ignores everything else rather than failing on a file it does
    not fully understand. A partial read still tells you whether `description`
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
        if value in ("|", ">", "|-", ">-", "|+", ">+"):
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
                    keys=sorted(fm),
                )
            )
    return skills


@dataclass
class Agent:
    path: str
    stem: str
    name: str = ""
    description: str = ""
    has_frontmatter: bool = False
    defects: list[str] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name or self.stem


def find_agents(roots: list[Path]) -> list[Agent]:
    """Subagent definitions: any `*.md` directly inside a directory named `agents`."""
    seen: set[Path] = set()
    agents: list[Agent] = []
    for root in roots:
        if not root.exists():
            continue
        for md in sorted(root.rglob("agents/*.md")):
            resolved = md.resolve()
            if resolved in seen or not md.is_file():
                continue
            seen.add(resolved)
            try:
                text = md.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"warning: cannot read {md}: {exc}", file=sys.stderr)
                continue
            fm = parse_frontmatter(text)
            agents.append(
                Agent(
                    path=str(md),
                    stem=md.stem,
                    name=fm.get("name", ""),
                    description=fm.get("description", ""),
                    has_frontmatter=bool(fm),
                    keys=sorted(fm),
                )
            )
    return agents


def grade_agent(agent: Agent) -> None:
    if not agent.has_frontmatter:
        # README-style notes kept beside agents are common; not a defect.
        return
    if not agent.name:
        agent.defects.append(
            "no name in frontmatter -- Claude Code skips a standalone agent "
            "without one, and a plugin agent loads only under its filename"
        )
    for key, fix in UNREAD_AGENT_KEYS.items():
        if key in agent.keys:
            agent.defects.append(f"'{key}' is not read by the harness; {fix}")
    if not agent.description:
        agent.defects.append("no description -- agent cannot be routed to")
        return
    if len(agent.description) < MIN_DESCRIPTION_CHARS:
        agent.defects.append(
            f"description is {len(agent.description)} chars "
            f"(under {MIN_DESCRIPTION_CHARS}); too thin to disambiguate"
        )
    if not has_trigger_language(agent.description):
        agent.defects.append(
            "description says what it does but never when to delegate to it "
            "(no 'use when' / 'use proactively' clause)"
        )


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

    for key, fix in UNREAD_SKILL_KEYS.items():
        if key in skill.keys:
            skill.defects.append(f"'{key}' is not read by the harness; {fix}")


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
    agents: list[Agent] | None = None,
) -> None:
    agents = agents or []
    flagged = [s for s in skills if s.defects]
    flagged_agents = [a for a in agents if a.defects]
    width = 66

    print()
    print(f"whetstone skill audit -- {len(skills)} skills, "
          f"{len(agents)} agents scanned")
    print("-" * width)

    if not skills and not agents:
        print("No SKILL.md or agents/*.md files found. Pass a root explicitly.")
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
    print(f"  agents with >=1 defect     {len(flagged_agents):>4}"
          f"  ({len(flagged_agents) * 100 // max(len(agents), 1)}%)")
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

    if flagged_agents:
        print("Per-agent defects")
        print("-" * width)
        for a in flagged_agents:
            print(f"  {a.label}")
            print(f"    {a.path}")
            for d in a.defects:
                print(f"    - {d}")
        print()

    if not flagged and not flagged_agents and not collisions:
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
    agents = find_agents(roots)
    for a in agents:
        grade_agent(a)
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
                "agents": [asdict(a) for a in agents],
            },
            indent=2,
        ))
    elif args.quiet:
        flagged = sum(1 for s in skills if s.defects)
        flagged_agents = sum(1 for a in agents if a.defects)
        print(f"{len(skills)} scanned, {flagged} flagged, "
              f"{len(collisions)} collisions, {len(duplicates)} duplicate names, "
              f"{len(agents)} agents, {flagged_agents} agents flagged")
    else:
        report(skills, collisions, duplicates, args.threshold, agents)

    # Non-zero when something needs attention, so this can gate CI.
    return 1 if (
        any(s.defects for s in skills)
        or any(a.defects for a in agents)
        or collisions
        or duplicates
    ) else 0


if __name__ == "__main__":
    sys.exit(main())

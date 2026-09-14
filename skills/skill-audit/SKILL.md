---
name: skill-audit
description: |
  Audit installed Agent Skills for routing defects: missing or thin descriptions,
  descriptions that never say when to fire, names that disagree with their
  directory, duplicate skills shadowed across plugin versions, and pairs whose
  descriptions compete for the same request. Use when the user asks to audit,
  review, or disambiguate skill descriptions, says an agent picked the wrong
  skill, or asks why a skill never triggers. Not for authoring a new skill from
  scratch, which is skill-development's job.
---

# Skill Audit

Under progressive disclosure an agent sees only `name` and `description` before
deciding what to load. Those two fields are the whole routing surface. A skill
the agent cannot find is a skill you do not have.

## Run the audit

```sh
python3 ${PLUGIN_ROOT}/skills/skill-audit/scripts/audit_skills.py [ROOT ...]
```

With no argument it scans `~/.claude/skills`, `~/.claude/plugins`,
`./.claude/skills`, `./.agents/skills`, and `./skills`. Standard library only,
so it runs anywhere Python 3.10+ does.

Useful flags: `--threshold` (default 0.35) tunes how much description overlap
counts as a collision, `--json` emits machine-readable output, `--quiet` prints
summary counts only. Exit status is 1 when anything needs attention, so it can
gate CI.

## Read the output in this order

**Duplicate names first.** These are usually version shadowing: a plugin cache
holding two releases exposes every skill twice. They are not competing
descriptions and fixing them is pruning, not rewriting. Resolve these before
trusting any other number, because duplicates inflate everything downstream.

**Per-skill defects second.** The common one is a description that says what a
skill does and never when to use it. Compare:

> Create engaging newsletter content with consistent structure and personal tone.

against:

> Write a newsletter issue from an outline, transcript, or topic. Use when the
> user asks for a newsletter, an issue, or a subscriber email. Not for one-off
> announcements, which write-announcement handles.

The second tells the agent when to fire and when to stand down.

**Collisions last.** For each pair, decide which skill owns the request, then
edit both descriptions so each names a case the other excludes.

## Verify a fix with the three-way trigger test

Never accept a rewritten description without testing all three:

1. An obvious request phrased the way the docs would phrase it. Must fire.
2. The same request phrased the way a tired person would actually type it. Must
   still fire.
3. A neighboring request that belongs to a different skill. Must NOT fire.

Most rewrites pass 1 and fail 3. A description that fires on everything is as
broken as one that fires on nothing, and it is harder to notice.

## Rules

- Rewrite only descriptions that actually failed. Churning good ones costs
  review attention and risks regressions you will not catch.
- Never edit a skill outside version control. Every change should be revertable.
- Re-run the audit after edits and confirm the count moved in the right
  direction. A fix you did not measure is a fix you are guessing about.

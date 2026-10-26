# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `audit_skills.py` grades subagent definitions (`agents/*.md`) on the same
  routing surface as skills: missing `name`, missing or thin descriptions,
  descriptions with no "when" clause, and the unread `identifier` / `whenToUse`
  fields.
- Skills carrying an unread `triggers:` list are flagged.
- Regression tests under `tests/` (standard library `unittest`).

### Fixed

- "Use this skill when" / "use this agent when" were not recognised as trigger
  language, so correctly written descriptions were flagged. "Use proactively"
  is also recognised.

## [0.1.0] - 2026-09-14

### Added

- `skill-audit` skill and `audit_skills.py`, a standard-library auditor for
  description defects, duplicate names, and trigger-surface collisions across
  installed Agent Skills.
- `dry-promotion` skill for moving repeatedly regenerated code into a saved
  script the owning skill executes.
- `skill-repair` skill for converting a corrected run into a durable edit in the
  smallest place that fixes the cause.
- `verify-before-return` skill for adding acceptance criteria and evidence-based
  self-checks to an existing skill.
- Three manifests over one shared `skills/` tree: root `plugin.json` for the
  Agent Plugins 1.0 standard, `.claude-plugin/plugin.json` for Claude Code, and
  `.cursor-plugin/plugin.json` for Cursor.

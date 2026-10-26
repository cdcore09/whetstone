# whetstone

Meta-skills that sharpen your other skills.

Most skill libraries grow the same way: you add skills, you never audit them,
and the agent quietly starts picking the wrong one. whetstone is four skills
that work on your skills — promoting repeated code into saved scripts, auditing
descriptions for ambiguity and overlap, repairing a skill from a run that went
wrong, and requiring evidence before an agent hands you its output.

It ships as a portable [Agent Plugin](https://agent-plugins.org), so the same
package installs under Claude Code, Codex, Cursor, VS Code, and OpenCode.

## What it found on a real library

Run against 383 installed skills across every plugin on one machine:

```
  missing description           0
  no trigger language         306
  description under 40 chars    0
  colliding pairs (>=0.35)      3
  duplicate names              23
  skills with >=1 defect      306  (79%)
```

Four out of five skills describe what they do without ever saying when to fire.
Twenty-three exist in more than one cached version, where which copy wins
depends on load order. Only three pairs genuinely compete for the same request —
a much smaller number than the first run reported, because the first version of
the auditor counted version-shadowed duplicates as collisions and inflated the
figure by roughly 27x.

## Install

### Claude Code

```sh
claude plugin marketplace add cdcore09/whetstone
claude plugin install whetstone@whetstone
```

### Codex, Cursor, VS Code, and other Agent Plugins clients

Clone the repo and install from the local path, or add it to a marketplace your
client reads. The root `plugin.json` declares the
`agent-plugins.org/schemas/1.0.0` schema, which these clients detect directly.

### OpenCode

OpenCode reads skill directories rather than plugin manifests. Point it at the
skills:

```sh
git clone https://github.com/cdcore09/whetstone.git ~/.whetstone
ln -s ~/.whetstone/skills/* ~/.claude/skills/
```

### No harness at all

The auditor is a standalone script with no dependencies:

```sh
python3 skills/skill-audit/scripts/audit_skills.py ~/.claude/plugins
```

## The skills

| Skill | Use it when |
|---|---|
| `skill-audit` | An agent picked the wrong skill, a skill never triggers, or you want descriptions disambiguated |
| `dry-promotion` | The agent keeps rebuilding the same helper, or results drift between runs that should match |
| `skill-repair` | You have corrected the same mistake twice and want the fix to outlive the session |
| `verify-before-return` | You keep fixing the last 20% by hand |

Each has a slash-command entry point: `/audit`, `/promote`, `/repair`,
`/verify`.

## Auditing your own library

```sh
python3 skills/skill-audit/scripts/audit_skills.py            # conventional locations
python3 skills/skill-audit/scripts/audit_skills.py ./skills   # one directory
python3 skills/skill-audit/scripts/audit_skills.py --json     # machine-readable
python3 skills/skill-audit/scripts/audit_skills.py --threshold 0.25
```

It also grades subagent definitions (`agents/*.md`) under the same roots: missing
`name`, missing or what-without-when descriptions, and fields like `identifier`,
`whenToUse`, or a skill's `triggers:` list that look like routing metadata but
are never read.

Exit status is 1 when anything needs attention, so it works as a CI gate.

Tests: `python3 -m unittest discover -s tests`.

Read the output in order. Resolve **duplicate names** first, since duplicates
distort every number below them. Then **per-skill defects**, where the common
finding is a description that says what a skill does and never when to use it.
Then **collisions**, deciding for each pair which skill owns the request.

Verify any rewritten description with all three trigger tests: an obvious
request must fire, a casually reworded request must still fire, and a
neighboring request must not fire. Most rewrites pass the first two and fail the
third.

## A word on "self-improving"

These skills do not improve themselves. They help *you* improve them, with a
human approving every edit. `skill-repair` proposes diffs rather than writing
silently, and expects its target to be under version control, because an agent
editing its own instructions unsupervised drifts in ways that are hard to see
from the inside.

The honest claim is narrower than the phrase suggests, and more useful: the
corrections you already make can be captured instead of discarded.

## Prior art

The practices here come from Anthropic's Agent Skills work, particularly Barry
Zhang and Mahesh Murag's talk *Don't Build Agents, Build Skills Instead* and the
Anthropic engineering post
[Building Agents with Skills](https://claude.com/blog/building-agents-with-skills-equipping-agents-for-specialized-work).
The Agent Skills specification is an open standard at
[agentskills.io](https://agentskills.io); the plugin packaging standard is at
[agent-plugins.org](https://agent-plugins.org).

## License

MIT

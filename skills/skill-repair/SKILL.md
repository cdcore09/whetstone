---
name: skill-repair
description: |
  Turn a failed or corrected agent run into a durable edit in the skill that
  caused it, choosing the smallest place that actually fixes the cause: process
  step, reference file, explicit rule, or unreliable code. Use when the user
  corrects the same mistake twice, says a skill keeps getting something wrong,
  asks to fix a skill rather than fix one output, or wants a correction to
  survive past the current session.
---

# Skill Repair

Correcting an agent and closing the session throws the lesson away. The output
got fixed and the process stayed broken, so the next run reproduces it.

## Diagnose before editing

A correction lands in exactly one of four places. Naming which one prevents the
usual failure, which is bolting another rule onto a skill whose real problem is
that a step is in the wrong order.

**Process.** The steps are wrong or out of order. Fix the procedure in SKILL.md.

**Missing context.** The steps are right but the agent lacked an example, a
format, or domain knowledge. Add a reference file. Do not encode the example as
a rule.

**Weak rule.** The agent had the information and chose differently. Add an
explicit prohibition naming the failure mode. This is the only case where "add a
rule" is the right answer, and it is rarer than it feels.

**Unreliable code.** The agent regenerates logic that sometimes works. This is a
dry-promotion job, not a rule.

## Ask why the agent did the reasonable thing

Before writing the fix, make the agent show its work: what it searched, what it
read, what it concluded. Most repeated mistakes are correct reasoning from bad
routing. If the agent looked in the wrong place, the repair belongs in whatever
sent it there, not in the skill that got blamed.

## Smallest durable place

Prefer the edit that fixes the cause and touches the least. A skill accumulating
rules for every past mistake becomes a document no agent can follow, and the
rules start contradicting each other. When a new rule argues with an existing
instruction, the instruction usually wins, quietly, and you will not notice
until you measure.

If a rule and a template disagree, fix the template. That is where the behavior
actually comes from.

## Verify

Re-run the task that failed. Not a similar one, the same one. Confirm the
original failure is gone and nothing adjacent broke. Then run one neighboring
task the skill also owns, because rules written against one failure routinely
break the case next door.

## Rules

- Propose the edit as a diff and let a human approve it. An agent editing its
  own instructions without review drifts, and the drift is hard to see from
  inside.
- The target skill must be under version control before you edit it.
- Never record a correction you have not reproduced. You will encode a rule
  against a coincidence.

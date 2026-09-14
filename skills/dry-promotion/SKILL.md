---
name: dry-promotion
description: |
  Promote code an agent keeps rewriting into a saved script inside the owning
  skill, then rewrite the skill to execute that file instead of regenerating it.
  Use when the user notices the agent rebuilding the same helper across runs,
  asks to save a working script for reuse, mentions DRY for skills, or wants
  deterministic output where results currently drift between runs.
---

# DRY Promotion

An agent that rewrites the same script every run pays twice: tokens to
regenerate it, and correctness, because a fresh guess varies. Save the version
that worked and call it a tool for the agent's future self.

## When something qualifies

Promote when all three hold:

- The agent has produced functionally equivalent code on more than one run.
- The output is deterministic enough that a saved version stays correct.
- The variation between runs is noise, not adaptation to the specific task.

Do not promote code whose logic genuinely changes with each input. You will
freeze a bug into the skill and then wonder why results got worse.

## Procedure

1. Capture the version that worked. Not a reconstruction from memory, the actual
   text that produced the result you accepted.
2. Save it under the owning skill as `scripts/<name>.<ext>`.
3. Strip anything task-specific. Parameters become arguments, not constants.
4. Edit SKILL.md to execute the file, naming its path and arguments explicitly.
5. Add a one-line comment at the top of the script saying what it does and what
   it assumes. Future you is the reader.

## Verify before believing it

Run the same class of task twice and confirm:

- The saved script actually ran. Check for its output signature, or add a marker
  and look for it. An agent that silently regenerates the logic looks identical
  from the outside and defeats the whole exercise.
- The parts that should be stable are byte-identical between runs.
- The parts that should vary still vary.

Surrounding prose will still differ. That is fine. You replaced one fresh guess
with one proven artifact, not the whole run.

## Rules

- One script, one job. A promoted script that grows flags is a script that needs
  splitting.
- Keep the script runnable on its own from a shell. If it only works when an
  agent calls it, you have not actually made it a tool.
- Prefer the standard library. A promoted script that needs an install step will
  break on a machine you do not control.

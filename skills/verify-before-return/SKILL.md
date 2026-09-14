---
name: verify-before-return
description: |
  Add acceptance criteria and an evidence-based self-check to a skill so the
  agent inspects and repairs its own output before handing it over. Use when the
  user says they keep fixing the last 20 percent by hand, asks to add
  verification or quality gates to a skill, wants an agent to check its work, or
  reports that output arrives broken in ways the agent could have caught.
---

# Verify Before Return

A skill that hands over its first attempt makes you the quality gate. Your first
look should not be the agent's first look.

## Evidence, not self-assessment

An agent rereading its own draft and reporting "looks good" has verified
nothing. It is asking the model that produced the output whether the output is
good, using the same context that produced the mistake. Verification requires
evidence from outside the draft:

- **Rendered artifacts.** Screenshot the slide, the page, the chart. Look at it.
  Cropped text and overflow are invisible in source and obvious in a picture.
- **Execution.** Run the test, the script, the build. A passing exit code is
  evidence. A claim that it should pass is not.
- **Sources.** Open the primary source and match each claim to the passage
  supporting it. Cut anything that survives only because it sounds right.
- **Deterministic checks.** Counts, schema validation, linters. Cheapest and
  most reliable. Use these first.
- **Adversarial readers.** For subjective work, have distinct personas review:
  someone confused by jargon, someone who does not believe the claim, someone
  from the actual audience deciding whether to keep reading.

## The block to add

Append to the skill, adapting the verification method to what it produces:

> Before returning output, state the acceptance criteria. Produce a first
> version, check it with the verification method named below, fix every issue
> found, then check again. Return only when the criteria are met, with a short
> note on what you checked and how. If something could not be verified, say so
> explicitly rather than omitting it.

Name the method concretely. "Verify the output" produces nothing; "render each
slide to PNG and inspect for clipped text" produces a fix.

## Handling persona feedback

Do not apply every note. Accepting all of it makes output worse, sanded toward
whatever no reviewer objected to. Take findings that appear more than once,
make the strongest revision, and re-run the check.

## Where this stops

Verification catches the mechanical failures: broken formatting, unsupported
claims, failing tests, missing sections. It does not catch taste, strategy, or
whether the thing was worth making. You remain the final judge on those, and
should be. The goal is narrower than it sounds: stop spending your attention on
problems the agent could have found on its own.

## Rules

- Prefer a cheap deterministic check over an expensive subjective one. Run the
  linter before convening a persona panel.
- Cap the loop. Three passes, then return with the unresolved issues named.
  Unbounded self-revision burns tokens and converges on nothing.
- An unverifiable claim gets reported as unverified, never silently dropped.

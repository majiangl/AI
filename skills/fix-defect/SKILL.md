---
name: fix-defect
description: Fixes a defect tracked by a Jira ticket. Use when asked to fix a bug, defect, or
   issue referenced by a Jira ticket ID (e.g. PROJ-123).
---

## Goal

Investigate and fix the defect described in the Jira ticket, involving the user early to avoid
wasted effort. End with a fix, or a clear conclusion about the root cause and the fix.

## Prerequisites

Stop and notify the user if any prerequisite is unmet:
- [ ] The Atlassian MCP server is configured.

## Input

- **Jira ticket** — a ticket ID (e.g. `PROJ-123`) or a full Jira URL. Extract the ticket ID from
  the URL when a full URL is given.

## Process

### 1. Collect Defect Information

1. Fetch the ticket with the Atlassian `getJiraIssue` tool, setting `cloudId` to the site
   hostname (extracted from the full Jira URL). If the `cloudId` is unknown or the request fails,
   call `getAccessibleAtlassianResources` to list the available cloud IDs. Request the following
   fields:
   - Title, description, and status
   - Comments (may contain investigation notes; treat them as hints, not ground truth)
   - Parent
2. If the ticket has a parent, fetch it and repeat until no further parents remain.
3. Build a consolidated view in which lower-level tickets take precedence and parents provide
   broader context.

### 2. Identify the Root Cause

Reproducing the defect is the fastest way to narrow down the root cause. Follow this process to 
identify the root cause:
1. Reproduce the defect.
2. Collect information (such as logs, stack traces, network requests, and screenshots).
3. Identify the root cause.

#### Reproduce

The recommended way to reproduce is a live approach, which can also verify a potential fix. If
the reproduction approach is unknown or ambiguous, ask the user the following questions (adjust
the later questions based on the earlier answers):
- Do you want to reproduce and verify using a live approach?
- How should we reproduce and verify using the live approach?

If the user does not want to use the live approach, fall back to reproducing the defect only if
the ticket provides reproduction steps; optionally ask the user for more details. Skip
reproduction if the ticket does not provide reproduction steps.

#### Stop Gate
- If a fix already exists, stop and summarize the root cause and the fix.
- If the defect is not related to the current repo, stop and suggest a different repo to
  investigate.

#### Escalate to the User When Stalled

The user may hold context you cannot get from code (ticket history, cross-repo knowledge,
environment details, intended design). Involve them as soon as progress stalls; do NOT push
through alone. Treat any of the following as a stall:
- The root cause cannot be identified because context or knowledge is lacking, or analysis
  yields only hypotheses.
- The intended mechanism is ambiguous and multiple plausible fixes exist.
- Cannot proceed for whatever reason.

When stalled, stop working and prompt the user immediately. Present:
- What you found so far (root-cause hypothesis or the blocker).
- The decision needed, with concrete options (recommend one). Include a "type your own answer"
  path so the user can supply missing context.
- What you will do for each option.

Re-ask if a new stall appears after the user's guidance. Never silently proceed past a stall.

### 3. Fix and Verify

Make minimal changes following these principles:
- Prefer general solutions that eliminate design flaws over narrow patches that address only the
  current case.
- Add comments to non-obvious logic; leave self-explanatory code uncommented.

Verify the fix:
1. Run the relevant tests and lint.
2. Re-run the reproduction steps and confirm, when possible, that the defect is gone.

### 4. Rubber Duck Review

Invoke the `rubber-duck` agent (or an equivalent rubber duck process) to review:
- Correctness of the root cause and the proposed fix.
- Regression risks and potential side effects.
- Code quality, readability, and maintainability.

Address any issues raised.

## Output

- Root cause of the defect.
- What was changed to fix it.
- How the fix was verified.

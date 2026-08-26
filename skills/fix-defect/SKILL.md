---
name: fix-defect
description: Fixes a defect tracked by a Jira ticket. Use when asked to fix a bug, defect, or
   issue referenced by a Jira ticket ID (e.g. PROJ-123).
---

# Goal

Investigate and fix the defect described in the Jira ticket, involving the user early to avoid
wasted effort. End with a fix, or a clear conclusion about the root cause and the fix.

# Prerequisites

Stop and notify the user if any prerequisite is unmet:
- [ ] The Atlassian MCP server is configured.

# Input

- **Jira ticket** — a ticket ID (e.g. `PROJ-123`) or a full Jira URL (extract the ticket ID from
  the URL when a full URL is given).

# Process

## 1. Collect Defect Information

1. Fetch the ticket with the Atlassian `getJiraIssue` tool, setting `cloudId` to the site
   hostname (extracted from the Jira URL when given). If the `cloudId` is unknown or the request
   fails, call `getAccessibleAtlassianResources` to list the available cloud IDs. Request the
   following fields:
   - Title, description, and status
   - Comments (may contain investigation notes; treat them as hints, not ground truth)
   - Parent
2. If the ticket has a parent, fetch it and repeat until no further parents remain.
3. Build a consolidated view: lower-level tickets take precedence, while parents provide broader
   context.

## 2. Identify the Root Cause

The fastest way to narrow down the root cause is to reproduce the defect. Follow this process:
1. Reproduce the defect.
2. Collect information (logs, stack traces, network requests, screenshots).
3. Identify the root cause.

### Reproduce

Reproducing live is the recommended approach because it can also verify a potential fix. If the
live approach is unknown or ambiguous, ask the user (adjust the later questions based on the 
earlier answers):
- Whether to reproduce and verify using a live approach?
- How to reproduce and verify using the live approach?

If the user declines the live approach, reproduce the defect only when the ticket provides
reproduction steps (optionally asking the user for more details); otherwise skip reproduction.

### Stop Gate

- If a fix already exists, stop and summarize the root cause and the fix.
- If the defect is not related to the current repo, stop and suggest a different repo to
  investigate.

### Escalate to the User When Stalled

The user may hold context you cannot get from code (ticket history, cross-repo knowledge,
environment details, intended design). Involve them as soon as progress stalls; do not push
through alone. Treat any of the following as a stall:
- The root cause cannot be identified because context or knowledge is lacking, or analysis
  yields only hypotheses.
- The intended mechanism is ambiguous and multiple plausible fixes exist.
- Work cannot proceed for any other reason.

When stalled, stop working and prompt the user immediately. Present:
- What you found so far (root-cause hypothesis or the blocker).
- The decision needed, with concrete options (recommend one) and a "type your own answer" path so
  the user can supply missing context.
- What you will do for each option.

Re-ask whenever a new stall appears after the user's guidance. Never silently proceed past a
stall.

## 3. Fix and Verify

When fixing:
- List candidate solutions, compare solutions, and choose the most straightforward one that
  follows the original design.
- Prefer general solutions that eliminate design flaws over narrow patches that address only the
  current case.
- Add comments to non-obvious logic; leave self-explanatory code uncommented.

Verify the fix:
1. Run the relevant tests and lint.
2. Re-run the reproduction steps and confirm, when possible, that the defect is gone.

## 4. Rubber Duck Review

Invoke the `rubber-duck` agent (or an equivalent rubber duck process) to review:
- The root cause and the proposed fix.
- Regression risks and potential side effects.
- Code quality, readability, and maintainability.

Address any issues raised.

# Output

- Root cause of the defect.
- What was changed to fix it.
- How the fix was verified.

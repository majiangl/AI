---
name: fix-defect
description: Fixes a defect tracked by a Jira ticket or described in plain text. Use when asked to
  fix a bug, defect, or issue.
---

# Goal

Investigate and fix the given defect, involving the user when more details are needed or work
stalls. Conclude with a fix, or with a clear explanation of the root cause and why it cannot be
fixed.

# Prerequisites

Stop and notify the user if any prerequisite is unmet:
- [ ] The Atlassian MCP server is configured.

# Input

- **Defect ticket** — one of:
  - A Jira ticket ID (e.g. `PROJ-123`)
  - A full Jira URL (extract the ticket ID from the URL)
  - A plain-text description of the defect

# Process

## 1. Collect Defect Information

If the defect is a Jira ticket:
1. Fetch the ticket with the `getJiraIssue` tool, setting `cloudId` to the site hostname (extracted
   from the Jira URL when given). If `cloudId` is unknown or the request fails, call
   `getAccessibleAtlassianResources` to list available cloud IDs. Request these fields:
   - Title, description, and status
   - Comments (may contain investigation notes — treat them as hints, not ground truth)
   - Parent
2. If the ticket has a parent, fetch it and repeat until no further parents remain.
3. Build a consolidated view: lower-level tickets take precedence; parents provide broader context.

## 2. Identify the Root Cause

Follow the steps to identify the root cause:
1. Reproduce the defect.
2. Collect information (logs, stack traces, network requests, screenshots).
3. Identify the root cause.

**Reproduce before analyzing code** — reproduction narrows down the root cause quickly and
accurately.

### Reproduce

Reproducing live is the recommended approach because it lets you verify the fix. If the live
approach is unknown or ambiguous, ask the user, adapting each question to earlier answers:
- Should we reproduce and verify using the live approach?
- How should we reproduce and verify using the live approach?

If the user declines the live approach, fall back to the reproduction steps in the ticket, if any
(asking the user for more details when needed); otherwise, skip reproduction.

### Stop Gates

Stop and report if any of the following is met:
- A fix already exists — summarize the root cause and the fix.
- The defect is unrelated to the current repo — suggest the correct repo to investigate.

### Escalate When Stalled

The user may hold context you cannot get from code (ticket history, cross-repo knowledge,
environment details, intended design). Involve them as soon as progress stalls; do not push
through alone. Treat any of the following as a stall:
- The root cause cannot be identified because context or knowledge is lacking, or analysis
  yields only hypotheses.
- The intended mechanism is ambiguous and multiple plausible fixes exist.
- Work cannot proceed for any other reason.

When stalled, stop immediately and prompt the user with:
- What you found so far (hypothesis or blocker).
- The decision needed, with concrete options (recommend one) and an open path for the user to
  supply missing context.
- What you will do for each option.

Re-escalate whenever a new stall appears after the user's guidance. Never silently proceed past a
stall.

## 3. Figure Out the Fix

Follow the steps to figure out the fix:
1. List candidate solutions, choose one based on the following criteria:
    1. Prefer general fixes that eliminate the underlying design flaw over narrow patches that 
       address only the current case.
    2. Among equally general options, choose the most straightforward fix that follows the original
       design.
2. Make the fix:
   - Comment non-obvious logic; leave self-explanatory code uncommented.
3. Verify the fix:
   1. Run the relevant tests and lint.
   2. Re-run the reproduction steps and confirm, when possible, that the defect is gone.

## 4. Rubber Duck Review

Review the fix using the `rubber-duck` agent (or an equivalent rubber duck process) about:
- Regression risks and potential side effects.
- Code quality, readability, and maintainability.

Address any issues raised.

# Output

- Root cause of the defect.
- What was changed to fix it and why it was chosen.
- How the fix was verified.

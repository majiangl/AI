---
name: fix-defect
description: Fixes a defect tracked by a Jira ticket. Use when asked to fix a bug,
  defect, or issue referenced by a Jira ticket ID (e.g. PROJ-123).
---

## Prerequisites

Stop and notify the user if any of the following are unmet:
- [ ] The Atlassian MCP server is configured.

## Input

- **Jira ticket** — a ticket ID (e.g. `PROJ-123`) or a full Jira URL.
  Extract the ticket ID from the URL when a full URL is given.

## Process

### 1. Collect Defect Information

1. Fetch the ticket with the Atlassian `getJiraIssue` tool, setting `cloudId` to the
   site hostname. If the `cloudId` is unknown or the request fails, call
   `getAccessibleAtlassianResources` to list the available cloud IDs. Request the 
   following fields:
   - Title, description, and status
   - Comments (may contain investigation notes; treat them as hints, not ground truth)
   - Parent
2. If the ticket has a parent, fetch it and repeat until no further parents remain.
3. Build a consolidated view: lower-level tickets take precedence; parents provide
   broader context.
4. If a fix already exists, ask the user how to proceed (e.g. review and verify,
   amend, or start over from scratch) instead of assuming.

### 2. Identify the Root Cause

Reproduce the defect and collect debug information (logs, stack traces, network requests)
before analyzing code — it is more efficient to narrow down the root cause this way.

**If the root cause is external (e.g. in a package or service outside this repo),
summarize findings and stop.**

#### How to Reproduce

> Prefer reproduction in a dev environment, since it allows quick verification of a fix.
> Without such verification, the fix cannot be confirmed.

1. Ask the user whether to reproduce the defect in a dev environment.
2. If yes, ask how to reproduce the defect in a dev environment.
3. If a dev environment is unavailable, fall back to the reporter's environment
   if provided in the Jira ticket.
4. Otherwise, skip reproduction.

### 3. Fix and Verify

Make minimal changes following these principles:
- Prefer general solutions that eliminate design flaws over narrow patches that
  address only the current case.
- Comment non-obvious logic; leave self-explanatory code comment-free.

Verify the fix:
1. Run the relevant tests and lint.
2. When a dev environment is available, re-run the reproduction steps and confirm the
   defect is gone.

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

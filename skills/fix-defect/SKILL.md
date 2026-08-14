---
name: fix-defect
description: Fixes a defect tracked by a Jira ticket. Use when asked to fix a bug,
  defect, or issue referenced by a Jira ticket ID (e.g. PROJ-123).
---

## Prerequisites

Stop and notify the user if any of the following are unmet:

- [ ] Atlassian MCP server configured.

## Input

- **Jira ticket** — a ticket ID (e.g. `PROJ-123`) or a full Jira URL.
  Extract the ID from the URL if needed.

## Process

### 1. Collect Defect Information

> To fetch a Jira ticket, call the Atlassian `getJiraIssue` tool with `cloudId`
> set to the site hostname (e.g. `strategyagile.atlassian.net`). If the
> `cloudId` is unknown or the request is rejected, call
> `getAccessibleAtlassianResources` to list available cloud IDs.

1. Fetch the ticket and review:
   - Title, description, and status
   - Steps to reproduce
   - Expected vs. actual behaviour
   - Comments — may contain investigation notes; treat them as hints, not
     ground truth.
2. Read the parent ID from the ticket. If a parent ticket exists, fetch it and
   repeat until no more parents remain.
3. Build a consolidated view: lower-level tickets take precedence; parents
   provide broader context.

### 2. Reproduce the Defect

> **Skip reproduction** if the defect is hard to trigger locally (e.g. token
> limits, external API errors, large-dataset issues).

1. If reproduction steps are insufficient, ask the user for clarification.
2. Follow the reproduction steps to observe the failure.
3. Capture error messages, stack traces, and any unexpected behavior.

### 3. Identify the Root Cause

1. Trace the full call chain from user action to failure.
2. Identify the exact line or function that triggers the error.

Classify where the root cause resides:

- **External** (in other packages or services outside this repo): stop and
  summarize findings.
- **Internal** (inside this repo): proceed to the fix.

### 4. Rubber Duck Review

Verify the suspected root cause by explaining it out loud, as if teaching a
rubber duck:

1. Trace the failure backwards from the observed symptom through the call chain
   to the root cause.
2. Explain step by step why each symptom occurs and how it maps to the root
   cause.
3. If any symptom is unexplained, or the explanation relies on unverified
   assumptions, re-examine the analysis and identify a revised root cause.
4. Repeat until the explanation accounts for every observed symptom.

### 5. Fix and Verify

- Prefer general solutions that eliminate design flaws over fixes that only
  patch the current case.
- Add comments for non-obvious logic.
- Keep self-explanatory code comment-free.

**Acceptance criteria:**

- Rubber duck review passes: the root cause explains every observed symptom.
- Fix is validated locally (when reproduction steps apply).
- Relevant tests and lint pass.

## Output

- Root cause of the defect.
- What was changed to fix it.
- How the fix was verified.

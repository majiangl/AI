---
name: implement-design
description: Implements a feature from a design document referenced by a Confluence page
  or a Markdown file. Use when asked to implement a design, feature, or specification.
---

## Prerequisites

Stop and notify the user if any of the following are unmet:

- [ ] Atlassian MCP server configured (required only when the design is a
      Confluence page).

## Input

- **Design document** — a Confluence page URL or page ID, or a path to a
  Markdown file containing the design or specification to implement.

## Process

### 1. Understand the Design

> If the design is a Confluence page, convert it to Markdown first (e.g., with
> the `confluence-to-markdown` skill).

Read the design document:

1. Identify the affected components and the change required for each. A
   component is identified either by physical location (e.g., repo/npm package)
   or ownership.
2. Determine what should be implemented in this repo.

### 2. Plan the Implementation

Create a detailed implementation plan using a top-down approach:

1. Determine architecture styles, frameworks, and design patterns first. If
   multiple options exist, notify the user to make the decision.
2. Identify interactions with external components and cross-component
   dependency references (e.g., version pins) that must be updated so consumers
   pick up the new changes.
3. Break the work into tasks, list the files and modules to touch, and note
   dependencies between tasks.

### 3. Implement the Code

- Handle interaction between internal components. Update call sites and
  imports when a shared interface or signature changes.
- Handle edge cases. Cover null/empty inputs, boundary values, and failure
  paths (e.g., session timeout, missing data).
- Add unit tests for new code. Cover the happy path, edge cases, and error
  paths.
- Add necessary comments. Explain non-obvious logic and business rules, not
  what the code obviously does.

### 4. Rubber Duck Review

Invoke the `rubber-duck` agent (or an equivalent rubber duck process) to review the
implementation plan and the code changes. Address any issues raised.

## Output

- Summary of the implementation, including what was changed and how it was
  verified.

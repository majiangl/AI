---
name: frontend-implement
description: Implements a frontend feature design described in a Markdown file. Use when asked to implement a frontend design, feature, or specification referenced by a Markdown file path.
---

## Goal

Implement a feature according to a given design document.

## Input

- **Design file** — path to the Markdown file containing the design or specification to implement.

## Process

### Step 1 - Understand the Design

1. Identify all affected components, their inter-dependencies, and the high-level change each requires. Component is identified either by physical location (E.x., repo/npm package) or ownership.
2. Output a structured summary before proceeding — one entry per component:
   **Component** · **Ownship** · **Dependencies** · **High-level change**.

### Step 2 - Implement Owned Components

Implement each owned component in dependency order. **Identify and update any cross-component dependency references (e.g. version pins) so consumers pick up the new changes.**

### Step 3 - Verify the Implementation

Run the relevant tests to confirm the implementation works as specified and introduces no regressions.

### Step 4 - Review PR with Code Review Agent

Review the changes and apply fix silently.


---
name: polish-docs
description: Polishes documents to ensure clear structure and fluent wording. Use when asked to
  polish, improve documentation, README files, technical writing, or any prose content.
---

# Goal

Improve documents so each is clearly structured and fluent — without changing its meaning,
technical accuracy, or intent.

**When multiple documents are provided, treat each one independently and apply all process steps
to each in turn. Do not let edits to one document bleed into another.**

# Input

- **Documents** — paths to the document files.
- **Style guidance** (optional) — any project-specific conventions to follow (e.g. terminology,
  tone, heading style). If a style guide or existing sibling documents are available, infer
  conventions from them when no explicit guidance is given.

# Constraints

These apply throughout every step below, not as a separate pass:

- Do not alter technical facts, numbers, code samples, commands, or referenced names/links.
- Do not add information, examples, or claims that were not in the original.
- Do not remove content unless it is truly redundant or contradictory — when in doubt, keep it.
- Keep the author's voice and tone where appropriate; this is a refinement, not a rewrite.
- If something is ambiguous, technically suspect, or looks like a factual error, leave it
  unchanged and flag it in the summary rather than guessing at a fix.

# Process

1. **Understand the document**
   - Read the whole document before editing. Identify its purpose, audience, and key message.
   - Note its type (README, API reference, tutorial, design doc, etc.) — the right structure and
     tone depend on it.
   - Identify parts that must stay untouched as-is: code blocks, commands, config samples, file
     paths, names, links, and any quoted text or data.

2. **Improve structure**
   - Ensure a logical flow: introduction → body → conclusion (or the equivalent for the document
     type).
   - Use consistent heading levels (H1 for title, H2 for major sections, H3 for subsections) and
     avoid skipping levels.
   - Group related content under the same section rather than scattering it across the document.
   - Split large sections that cover multiple topics into separate, focused sections — each
     section should address exactly one topic.
   - Merge sections that are near-duplicates or redundant, keeping the clearer version.
   - Use bullet points or numbered lists for enumerations of three or more items; use numbered
     lists specifically when order or sequence matters.
   - Use code blocks, tables, and callouts appropriately and consistently with the rest of the
     document (or the project's existing conventions).
   - Preserve structures that serve a purpose. A list with a single item may exist for future
     extensibility — keep the list rather than collapsing it into a sentence.

3. **Improve wording**
   - Rewrite incoherent sentences — split run-ons, rejoin fragments, and rearrange phrases that
     are confusing or hard to follow so they read clearly while keeping the original meaning.
   - Replace vague or wordy phrases with direct, precise language. Cut filler words and hedging
     that add no information ("basically", "it should be noted that", "in order to").
   - Use active voice wherever possible (e.g. "The function returns X", not "X is returned by
     the function").
   - Use one term per concept consistently throughout the document, and match any terminology
     already established elsewhere in the project.
   - Keep sentences and paragraphs reasonably short; break up dense paragraphs that bury the
     point.
   - Fix grammar, spelling, capitalization, and punctuation errors.

4. **Verify before finishing**
   - Re-read the edited document end to end to confirm it still flows and nothing was left
     half-edited (dangling references, broken lists, mismatched headings).
   - Confirm links, code samples, and filenames were not altered.
   - Confirm the rendered Markdown (lists, tables, code fences) is well-formed.

# Output

For each document:

- Changes applied directly to the file.
- A short bullet-point summary of changes (e.g. "Merged duplicate sections on X", "Split
  introduction into two paragraphs", "Standardized terminology: 'config' → 'configuration'").
- A separate "Flagged for review" note listing anything left unchanged due to ambiguity or
  suspected factual/technical issues, if any were found.

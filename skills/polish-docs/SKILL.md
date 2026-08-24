---
name: polish-docs
description: Polishes documents to ensure clear structure and fluent wording. Use when asked to 
  polish, improve documentation, README files, technical writing, or any prose content.
---

## Goal

Improve documents so each is clearly structured and fluent — without changing its meaning, 
technical accuracy, or intent.

**When multiple documents are provided, apply all process steps to each document in parallel.**

## Input

- **Documents** — paths to the document files.

## Process

1. **Understand the document** — identify its purpose, audience, and key message before making 
   any changes.

2. **Improve structure**
   - Ensure a logical flow: introduction → body → conclusion (or the equivalent for the document 
     type).
   - Use consistent heading levels (H1 for title, H2 for major sections, H3 for subsections).
   - Group related content under the same section rather than scattering it across the document.
   - Split large sections that cover multiple topics into separate, focused sections — each 
     section should address exactly one topic.
   - Use bullet points or numbered lists for enumerations of three or more items.
   - Use code blocks, tables, and callouts appropriately and consistently.
   - Preserve structures that serve a purpose. A list with a single item may exist for future 
     extensibility — keep the list rather than collapsing it into a sentence.

3. **Improve wording**
   - Rewrite incoherent sentences — split run-ons, rejoin fragments, and rearrange phrases that 
     are confusing or hard to follow so they read clearly while keeping the original meaning.
   - Replace vague or wordy phrases with direct, precise language.
   - Use active voice wherever possible (e.g. "The function returns X", not "X is returned by 
     the function").
   - Eliminate redundant words and filler phrases (e.g. "basically", "in order to", "it should be 
     noted that").
   - Use one term per concept consistently throughout the document.
   - Fix grammar, spelling, and punctuation errors.

4. **Preserve intent**
   - Do not alter technical facts, code samples, or referenced names/links.
   - Do not add information that was not in the original.
   - Keep the author's voice where appropriate — this is a refinement, not a rewrite.

## Output

- Changes applied directly to the documents.
- A short summary of changes per document (e.g. "Merged duplicate sections on X", "Split 
  introduction into two paragraphs").

---
name: confluence-to-markdown
description: Use when asked to read, understand, or convert a Confluence page identified by an
  atlassian.net/wiki URL or a page ID.
---

# Confluence to Markdown

Prefer this skill to a direct Confluence fetch: it preserves content that a direct read can miss,
such as macros. The Markdown keeps tables, task lists, code blocks, and links. PlantUML diagrams
become `plantuml` code blocks, draw.io diagrams become `mermaid` code blocks, and other non-text
media such as images become inline placeholders.

## Usage

```
/confluence-to-markdown <PAGE> [OPTIONS]
```

`<PAGE>` is a full Confluence URL or a page ID (for example `6503628991`).

| Option                | Description                                                                               |
| --------------------- | ----------------------------------------------------------------------------------------- |
| `-o, --output <path>` | Write the Markdown to this path. Resolve a relative path from the current workspace root. |

Without `-o`, the converter writes `<kebab-case-page-title>.md` next to its input file, in the
temporary folder.

## Prerequisites

Stop and notify the user if any prerequisite is unmet:

- [ ] The Atlassian Teamwork Graph CLI, `twg`, is available. To install or set it up, follow
      <https://teamwork-graph.atlassian.com/cli/AGENTS.md>.
- [ ] `python3` is available.

## Conversion

### 1. Export the page

Save the page to a file in the temporary folder:

```bash
twg confluence content get <page-url-or-id> --detail full --format html -o json --output-file <tmp>/page.json
```

- **`--detail full --format html`**: summaries and outlines have no body, and the Markdown format
  replaces macros such as PlantUML with placeholders. Only the full HTML keeps the macro data.
- **`-o json`**: the HTML body alone does not include the page title. The JSON envelope carries the
  `title` next to the body (`body.value`), so the converter gets both from one file.

### 2. Convert to Markdown

Run [convert_html.py](./convert_html.py) on the exported JSON file:

```bash
python3 <path-to>/convert_html.py <tmp>/page.json -o <output_md_path>
```

### 3. Post-process the Markdown

Read the generated Markdown and resolve each case below that occurs. Handle unsupported macros and
data-types first, because rerunning the converter discards any diagrams already replaced.

| Case                           | How to recognize it                                                                       | Action                                                                         |
| ------------------------------ | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Unsupported macro or data-type | `~~(unsupported macro: <key>)~~` or `~~(unsupported data-type: <type>)~~` in the Markdown | Patch a copy of the converter ([details](#unsupported-macros-and-data-types)). |
| draw.io diagram                | `~~(drawio diagram: <name>)~~` in the Markdown                                            | Convert to Mermaid ([details](#drawio-diagrams)).                              |

#### Unsupported macros and data-types

Both leave a placeholder. An unsupported data-type's content is still rendered as plain text after
the placeholder, which may lose structure, so check the Markdown there.

1. Inspect the element in the source HTML to see what it carries.
2. Copy `convert_html.py` to the temporary folder and patch the copy. Leave the bundled script
   unchanged.
3. Rerun the conversion with the patched copy.
4. If the element cannot be represented in Markdown, keep the placeholder (or plain text) and
   report it.

#### draw.io diagrams

A draw.io macro stores only a reference to the diagram. The diagram itself is a `.drawio` attachment
whose file name matches the placeholder.

1. Use `twg` to find that attachment and download it to the temporary folder. If the page has no
   attachment with that name, the diagram may belong to another page.
   - List attachments with `twg confluence content attachments list --id <page-url>`. A numeric
     page ID can return 404, so pass the full page URL.
   - Download with `twg confluence content attachments download --attachment-id <id> --out <path>`,
     using the ID from the list output.
2. Print its outline: nodes (nested by visual containment), edges, and edge labels.

   ```bash
   python3 <path-to>/drawio_outline.py <drawio_file>
   ```

3. Write a Mermaid diagram from the outline and replace the placeholder with a fenced `mermaid`
   block.
   - Use `flowchart` for architecture diagrams, with a `subgraph` per container.
   - Use `sequenceDiagram`, `classDiagram`, or `stateDiagram-v2` only when the draw.io diagram is
     clearly one of those.
   - Keep every node, container, and edge label, with the original label text. Keep unlabeled
     containers too (a `subgraph` with a blank title). Drop colors, fonts, and exact positions.
   - Mermaid chooses the layout, so the direction (`TD` or `LR`) is your choice, not a copy of the
     original. Say so in the summary.
   - Escape `<` and `>` in labels as `&lt;` and `&gt;`.
4. If the attachment is missing or unreadable, keep the placeholder and say so in the summary.

### 4. Review the Markdown

Review the Markdown and resolve every checklist item:

- [ ] Correct spelling and grammar, including in tables. Leave code blocks, PlantUML, Mermaid, and
      URLs untouched.
- [ ] Fix Markdown syntax errors and any formatting broken during conversion.
- [ ] Check that no `unsupported` placeholder remains unless it was reported.

## Output

Report the path to the Markdown file, then briefly note:

- Diagrams converted (for example draw.io to Mermaid) and whether they were rendered.
- Changes made to a copy of the converter.
- Remaining `unsupported` placeholders.
- Corrections made during post-processing and review.

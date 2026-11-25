---
name: confluence-to-markdown
description: Use when asked to read, understand, or convert a Confluence page identified by an
  atlassian.net/wiki URL or a page ID.
---

# Confluence to Markdown

Prefer this skill to a direct Confluence fetch: it preserves content that a direct read can miss,
such as macros. The Markdown keeps tables, task lists, code blocks, and links. PlantUML diagrams
become `plantuml` code blocks. Media, such as images, and other non-text extensions become inline
placeholders.

## Usage

```
/confluence-to-markdown <PAGE> [OPTIONS]
```

`<PAGE>` is a full Confluence URL or a page ID (for example `6503628991`).

| Option                | Description                                                                               |
| --------------------- | ----------------------------------------------------------------------------------------- |
| `-o, --output <path>` | Write the Markdown to this path. Resolve a relative path from the current workspace root. |

If the user asks to save the file to the workspace root, or wants it in the workspace without naming
a location, pass `-o <workspace-root>/<kebab-case-page-title>.md` with the absolute workspace root
path.

Without `-o`, the converter writes `<kebab-case-page-title>.md` in the temporary folder, next to
its input file.

## Prerequisites

Stop and notify the user if any prerequisite is unmet:

- [ ] The Atlassian Teamwork Graph CLI, `twg`, is available. To install or set it up, follow
      <https://teamwork-graph.atlassian.com/cli/AGENTS.md>.
- [ ] `python3` is available.

## Conversion

### 1. Export the page

Save the page to a file in the temporary folder. `<tmp>` is the temporary directory that the
harness designates for the session:

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

If the conversion reports any `UNSUPPORTED` warnings:

1. Inspect the source HTML.
2. Copy the script and patch the copy to handle those node types.
3. Rerun the conversion with the patched copy.

Do **NOT** modify the bundled script.

### 3. Review the Markdown

Review the generated Markdown and resolve every checklist item:

- [ ] **Broken formatting** — fix syntax errors and broken formatting introduced during conversion.

## Output

Report the path to the Markdown file. Then briefly note any unconverted placeholders, fix-ups, and
patched logic.

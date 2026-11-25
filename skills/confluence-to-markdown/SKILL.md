---
name: confluence-to-markdown
description: Use when asked to read, understand, or convert a Confluence page identified by an
  atlassian.net/wiki URL or a page ID.
---

# Confluence to Markdown

Prefer this skill to a direct page fetch: it preserves content that a direct read can miss,
including diagrams and macros. The Markdown retains tables, task lists, code blocks, and links.
PlantUML diagrams become fenced code blocks; non-text media such as images become inline 
placeholders.

## Usage

```
/confluence-to-markdown <PAGE> [OPTIONS]
```

`<PAGE>` accepts a full Confluence URL or a page ID (e.g. `6503628991`).

| Option                | Description                          |
| --------------------- | ------------------------------------- |
| `-o, --output <path>` | Write the Markdown to the given path. Resolve relative paths from the current workspace root. |

If you omit `-o`, the converter writes `<kebab-case-page-title>.md` next to the input file in the
temporary folder. For example, `Support Manage Access for MTDI/OLAP cubes` becomes
`support-manage-access-for-mtdi-olap-cubes.md`.

## Prerequisites

Stop and notify the user if any prerequisite is unmet:

- [ ] The `twg` CLI is installed and `twg doctor` shows "Authenticated successfully".
- [ ] `python3` is available.

## Conversion

### 1. Export the full page as HTML

Use the `twg` CLI’s output-file option to save the full HTML body in the temporary folder. Avoid
shell redirection for large exports. Request full detail: summaries and outlines omit the body,
and Markdown exports replace macros such as PlantUML with placeholders.

Prefer JSON that includes the page title (`title`) alongside the HTML body (`body.value`), even
if the page object is nested. If you save only the `.html` body, pass the page title with
`--title` during conversion.

### 2. Convert the export to Markdown

Run [convert_html.py](./convert_html.py) with the saved JSON or HTML file:

```bash
python3 <path-to-convert_html.py> <tmp>/page.json -o <output_md_path> # JSON with title
python3 <path-to-convert_html.py> <tmp>/page.html --title "<title>" -o <output_md_path> # bare HTML
```

If the converter reports an `UNSUPPORTED` warning for an unknown macro or `data-type`, inspect
the source HTML. Patch a **copy** of the script to handle the element, then rerun the conversion
with that copy. Leave the bundled script unchanged.

### 3. Review the Markdown

- [ ] Correct spelling and grammar, including in tables. Leave code blocks, PlantUML, and URLs 
  untouched.
- [ ] Fix Markdown syntax errors and any formatting broken during conversion.
- [ ] Check that the headings match the source page and that no `UNSUPPORTED` warnings remain 
  unexplained.

## Output

Report the path to the Markdown file. Briefly note any omitted media or extensions, corrections
to the Markdown, and changes made to a copy of the converter.

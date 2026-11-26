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

| Option                | Description                                                                                                                                                                                                                                         |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-o, --output <path>` | Write the Markdown to this path. Resolve a relative path from the current workspace root. If the path is a directory, write `<kebab-case-page-title>.md` inside it. If omitted, write next to the exported JSON file. |

## Prerequisites

Stop and notify the user if any prerequisite is unmet:

- [ ] The Atlassian Teamwork Graph CLI, `twg`, is available. To install or set it up, follow
      <https://teamwork-graph.atlassian.com/cli/AGENTS.md>.
- [ ] `python3` is available.
- [ ] `npx` is available.

## Conversion

### 1. Export the page

Fetch the full page, which includes the title and macro data, and save it to the session's
temporary folder as `<tmp>/page.json`.

#### Fetch with a page URL

```bash
twg confluence content get <page-url> --detail full --format html -o json --output-file <tmp>/page.json
```

#### Fetch with a page ID

A bare page ID does not carry a site. List the Confluence sites available to the user:

```bash
twg access --product confluence.ondemand -o json
```

Then try each site, one by one, until one succeeds:

```bash
twg confluence content get <page-id> --site <name> --detail full --format html -o json --output-file <tmp>/page.json
```

If every site returns 404, tell the user the page was not found on any accessible site and ask
for the full URL.

### 2. Convert to Markdown

Run [convert_html.py](./convert_html.py) from this skill's base directory:
- `<output_md_path>` must be a file path, not a directory.
- If the user gave a directory, build the file name from the `title` in the JSON.

```bash
python3 <skill-base-dir>/convert_html.py <tmp>/page.json -o <output_md_path>
```

If the conversion reports any `UNSUPPORTED` warnings:

1. Inspect the source HTML.
2. Copy the script and patch the copy to handle those node types.
3. Rerun the conversion with the patched copy.

Do **NOT** modify the bundled script while converting a page.

### 3. Verify

Lint the Markdown and fix all issues found:

```bash
npx -y markdownlint-cli2 <output_md_path>
```

Rerun the linter until it reports no errors.

## Output

Report the path to the Markdown file, then summarize:

- Omitted content left as placeholders.
- Logic patched during conversion.
- Fix-ups made during linting.

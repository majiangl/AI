---
name: confluence-to-markdown
description: Converts a Confluence page to Markdown. Always use this skill when asked
  to convert, read, or understand a Confluence page.
---

## Goal

Convert a Confluence page to Markdown, preserving all text content (including PlantUML
diagrams) and replacing non-text content (images, media) with inline placeholders.

## Prerequisites

Stop and notify the user if any of the following are unmet:
- [ ] Atlassian MCP server configured.

## Input

- **Confluence page** — full URL or plain page ID (e.g. `6503628991`).
- **Save location** — optional output path.

## Process

### 1. Fetch the Page

Call the Atlassian `getConfluencePage` tool with content format **ADF** and `cloudId`
set to the site hostname. If the `cloudId` is unknown or the request fails, call
`getAccessibleAtlassianResources` to list the available cloud IDs.

> For large pages, the tool saves the full JSON payload to a file and returns
> its path. Pass that path as `<adf_json_path>` — no reassembly needed.

### 2. Convert ADF to Markdown

Run [convert.py](./convert.py):

```bash
python3 <path-to-convert.py> <adf_json_path> <output_md_path>
```

> If the conversion reports any `UNSUPPORTED` warnings, inspect the ADF,
> copy the script, patch the copy to handle those node types, and re-run the
> conversion with the patched copy. Do **NOT** modify the bundled script.

#### Save Location

1. Use the user-specified path if provided.
2. Otherwise, save as `<kebab-case-page-title>.md` in the session temporary
   folder (e.g. `"Support Manage Access for MTDI/OLAP cubes"` →
   `support-manage-access-for-mtdi-olap-cubes.md`).

### 3. Review the Markdown

Work through the Markdown and resolve every checklist item:
- [ ] **Typos and grammar** — fix every spelling and grammar error, including
      inside tables.
- [ ] **Broken formatting** — fix syntax errors and broken formatting
      introduced during conversion.

## Output

- Path of the created Markdown file.
- Brief summary of omitted media/extensions, fix-ups, and patched logic.

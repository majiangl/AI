#!/usr/bin/env python3
"""
ADF → Markdown converter for the confluence-to-markdown skill.

Usage:
    python3 convert.py <adf_json_path> <output_md_path>

    <adf_json_path>  Path to the JSON file saved by the Atlassian MCP getConfluencePage tool.
    <output_md_path> Destination .md file path.
"""

import json
import re
import sys
import zlib
import base64
import html
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

# ---------------------------------------------------------------------------
# PlantUML decoder
# ---------------------------------------------------------------------------

def decode_plantuml(encoded: str) -> str:
    """Decode PlantUML extension data: standard base64 → raw deflate decompress.

    Some macros URL-encode the PlantUML source before compressing. Unquote the
    result only when it actually looks like a PlantUML document, so sources that
    were stored raw are left untouched.
    """
    try:
        raw = zlib.decompress(base64.b64decode(encoded), -15).decode("utf-8")
    except Exception as exc:
        return f"# decode error: {exc}"
    decoded = unquote(raw)
    if decoded.lstrip().startswith("@startuml"):
        return decoded
    return raw


# ---------------------------------------------------------------------------
# Media markers
# ---------------------------------------------------------------------------

def _media_name(node: dict) -> str:
    """Best-effort display name for a media node (alt text / filename / id)."""
    attrs = node.get("attrs", {})
    name = attrs.get("alt") or attrs.get("id") or ""
    if not name:
        for child in node.get("content", []) or []:
            if child.get("type") == "media":
                name = _media_name(child)
                if name:
                    break
    return name


def _media_marker(name: str) -> str:
    """Markdown marker (struck through) signalling an image is not represented (non-text content)."""
    return f"~~(image: {name})~~" if name else "~~(image)~~"


def _safe_fence(code: str) -> str:
    """Return a backtick fence longer than any run of backticks in *code*."""
    longest = max((len(m.group()) for m in re.finditer(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)


# ---------------------------------------------------------------------------
# Inline content (text, marks, mentions, links …)
# ---------------------------------------------------------------------------

def _clean_inline(s: str) -> str:
    """Normalize spaces in joined inline text without touching code span contents.

    - Drops a space right after an opening ** (artifacts like "** OnPrem")
    - Drops a space right before a closing ** (artifacts like "OnPrem **")
    - Strips leading/trailing whitespace of the whole inline run.
    """
    s = re.sub(r"(^|\s)\*\*\s+", r"\1**", s)
    s = re.sub(r"\s+\*\*(?=\s|$|[.,;:!?)\]}>])", "**", s)
    return s.strip()


def _inlinecard_title(url: str) -> str:
    """Derive a human-readable link title from a URL.

    Strategy (in order of priority):

    1. Figma — use the file name from the path.
    2. Atlassian (Confluence/Jira) — use the last meaningful path segment,
       decoding URL encoding and replacing hyphens/underscores with spaces.
    3. Swagger/API-docs pages — combine the tag and operation name from the
       URL fragment (``#/Tag/operationId``).
    4. Rally — return a generic label.
    5. Generic fallback — use the last non-empty path segment, cleaned up.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = unquote(parsed.path)
    fragment = unquote(parsed.fragment)

    # 1. Figma
    if "figma.com" in host:
        parts = [p for p in path.split("/") if p and p not in ("design", "file", "proto")]
        if parts:
            # The first meaningful segment is the file ID; the second is the name
            name = parts[1] if len(parts) > 1 else parts[0]
            return _slug_to_title(name)
        return "Figma design"

    # 2. Atlassian (Confluence wiki pages and Jira issues)
    if "atlassian.net" in host:
        # Confluence page: …/pages/<id>/<title-slug>
        m = re.search(r"/pages/\d+/([^/]+)$", path)
        if m:
            return _slug_to_title(m.group(1))
        # Confluence page with ID only (no title slug): …/pages/<id>
        m = re.search(r"/pages/(\d+)$", path)
        if m:
            return f"Confluence page {m.group(1)}"
        # Jira issue: …/browse/PROJ-123
        m = re.search(r"/browse/([A-Z]+-\d+)", path)
        if m:
            return m.group(1)
        # Spaces index or other Confluence URL — use last non-trivial segment
        segments = [p for p in path.split("/") if p and p not in ("wiki", "spaces", "pages")]
        if segments:
            return _slug_to_title(segments[-1])
        return "Atlassian page"

    # 3. Swagger / API-docs fragment: #/Tag/operationId
    if "api-docs" in path or "swagger" in path or "api-docs" in fragment:
        if fragment:
            parts = [p for p in fragment.lstrip("/").split("/") if p]
            if len(parts) >= 2:
                tag = _slug_to_title(parts[-2])
                op = _camel_to_title(re.sub(r"_\d+$", "", parts[-1]))
                return f"{tag} — {op}"
            if parts:
                return _slug_to_title(re.sub(r"_\d+$", "", parts[-1]))

    # 4. Rally
    if "rallydev.com" in host or "rally1.rally" in host:
        return "Rally item"

    # 5. Generic: last non-empty path segment
    segments = [p for p in path.split("/") if p]
    if segments:
        last = segments[-1]
        # Strip common file extensions
        last = re.sub(r"\.[a-z]{2,4}$", "", last)
        return _slug_to_title(last)

    return host or url


def _slug_to_title(slug: str) -> str:
    """Convert a URL slug or file name to readable prose.

    Handles hyphens, underscores, and percent-decoded spaces.
    Collapses runs of digits-only tokens that look like page IDs.
    """
    slug = unquote(slug)
    slug = re.sub(r"[-_+]", " ", slug)
    slug = slug.strip()
    tokens = [t for t in slug.split() if not re.fullmatch(r"\d{6,}", t)]
    return " ".join(tokens) if tokens else slug


def _camel_to_title(name: str) -> str:
    """Split a camelCase or PascalCase identifier into spaced Title Case words."""
    # Insert space before each uppercase letter that follows a lowercase letter or digit
    spaced = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", name)
    # Also split on underscores/hyphens
    spaced = re.sub(r"[-_]", " ", spaced)
    return spaced.strip().capitalize()


def _apply_marks(text: str, marks: list) -> str:
    """Wrap text in strong/em/strike delimiters, keeping edge whitespace outside.

    Confluence text nodes can carry trailing/leading whitespace inside the mark
    (e.g. strong ``"Clear: "``), which would otherwise render as ``**Clear: **``.
    CommonMark treats whitespace before a closing delimiter as a literal space,
    so the emphasis would silently fail to render. Whitespace is therefore moved
    outside the delimiters (``**Clear:** ``).
    """
    if not any(m in marks for m in ("strong", "em", "strike")):
        return text
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()):]
    core = text.strip()
    if not core:
        return text
    if "strong" in marks:
        core = f"**{core}**"
    if "em" in marks:
        core = f"*{core}*"
    if "strike" in marks:
        core = f"~~{core}~~"
    return leading + core + trailing


def inline_content(nodes: list) -> str:
    parts = []
    for n in nodes:
        t = n.get("type", "")

        if t == "text":
            text = n.get("text", "")
            marks = [m["type"] for m in n.get("marks", [])]
            if "code" not in marks:
                text = text.replace("\xa0", " ")
                text = re.sub(r" {2,}", " ", text)
            if "code" in marks:
                text = f"`{text}`"
            else:
                text = _apply_marks(text, marks)
            for m in n.get("marks", []):
                if m["type"] == "link":
                    href = m.get("attrs", {}).get("href", "")
                    leading = text[: len(text) - len(text.lstrip())]
                    trailing = text[len(text.rstrip()):]
                    text = leading + f"[{text.strip()}]({href})" + trailing
            parts.append(text)

        elif t == "hardBreak":
            parts.append("\n")
        elif t == "mention":
            name = n.get("attrs", {}).get("text", "")
            parts.append(f"@{name}" if name and not name.startswith("@") else f"{name}" if name else "@unknown")
        elif t == "inlineCard":
            url = n.get("attrs", {}).get("url", "")
            title = n.get("attrs", {}).get("title") or _inlinecard_title(url)
            parts.append(f"[{title}]({url})")
        elif t == "emoji":
            parts.append(n.get("attrs", {}).get("text", ""))
        elif t == "status":
            _STATUS_COLORS = {
                "neutral": ("#dfe1e6", "#42526e"),
                "purple":  ("#eae6ff", "#403294"),
                "blue":    ("#deebff", "#0747a6"),
                "red":     ("#ffebe6", "#bf2600"),
                "yellow":  ("#fffae6", "#172b4d"),
                "green":   ("#e3fcef", "#006644"),
            }
            attrs = n.get("attrs", {})
            text = attrs.get("text", "")
            color = attrs.get("color", "neutral").lower()
            bg, fg = _STATUS_COLORS.get(color, _STATUS_COLORS["neutral"])
            parts.append(
                f'<span style="background:{bg};color:{fg};border-radius:3px;'
                f'padding:1px 6px;font-size:0.85em;font-weight:bold;">{text}</span>'
            )
        elif t == "date":
            raw_ts = n.get("attrs", {}).get("timestamp", "")
            try:
                dt = datetime.fromtimestamp(int(raw_ts) / 1000, tz=timezone.utc)
                parts.append(dt.strftime("%Y-%m-%d"))
            except (ValueError, TypeError):
                parts.append(str(raw_ts))
        elif t in ("media", "mediaInline"):
            parts.append(_media_marker(_media_name(n)))
        elif t == "placeholder":
            print(
                f"DROPPED placeholder: {n.get('attrs', {}).get('text', '')!r}",
                file=sys.stderr,
            )
        else:
            children = n.get("content", [])
            if children:
                parts.append(inline_content(children))

    return _clean_inline("".join(parts))


def _task_item_md(item: dict, depth: int = 0) -> str:
    """Render a taskItem, recursing into nested taskItem/taskList children."""
    indent = "  " * depth
    checked = item.get("attrs", {}).get("state", "") == "DONE"
    check = "[x]" if checked else "[ ]"
    main: list[str] = []
    nested: list[str] = []
    for c in item.get("content", []) or []:
        t = c.get("type", "")
        if t == "taskItem":
            nested.append(_task_item_md(c, depth + 1))
        elif t == "taskList":
            for sub in c.get("content", []) or []:
                nested.append(_task_item_md(sub, depth + 1))
        else:
            s = inline_content([c])
            if s:
                main.append(s)
    main_text = " ".join(main)
    if not main_text and nested:
        return "\n".join(n for n in nested if n)
    result = f"{indent}- {check} {main_text}".rstrip()
    if nested:
        result += "\n" + "\n".join(n for n in nested if n)
    return result


def task_items_to_md(nodes: list) -> list[str]:
    """Render ADF taskList children (taskItem nodes) as GFM checkbox lines."""
    return [_task_item_md(item) for item in nodes]


# ---------------------------------------------------------------------------
# Table cell (block content flattened to inline for GFM compatibility)
# ---------------------------------------------------------------------------

def table_cell_content(cell_nodes: list) -> str:
    parts = []
    for n in cell_nodes:
        t = n.get("type", "")
        if t == "paragraph":
            parts.append(inline_content(n.get("content", [])))
        elif t in ("bulletList", "orderedList"):
            ordered = t == "orderedList"
            items = []
            for i, li in enumerate(n.get("content", [])):
                item_text = "".join(
                    inline_content(sub.get("content", []))
                    for sub in li.get("content", [])
                    if sub.get("type") == "paragraph"
                )
                prefix = f"{i + 1}. " if ordered else "- "
                items.append(f"{prefix}{item_text}")
            parts.append("<br>".join(items))
        elif t == "taskList":
            parts.append("<br>".join(task_items_to_md(n.get("content", []))))
        elif t == "heading":
            parts.append(f"**{inline_content(n.get('content', []))}**")
        elif t == "codeBlock":
            code = "".join(
                c.get("text", "") for c in n.get("content", []) if c.get("type") == "text"
            )
            parts.append(f"<pre>{html.escape(code).replace(chr(10), '&#10;')}</pre>")
        elif t in ("mediaSingle", "mediaGroup"):
            parts.append(_media_marker(_media_name(n)))
        else:
            sub = inline_content(n.get("content", []))
            if sub:
                parts.append(sub)
    return "<br>".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

def table_to_md(table_node: dict) -> str:
    rows = table_node.get("content", [])
    if not rows:
        return ""

    md_rows: list[str] = []
    separator_added = False

    for row in rows:
        cells = row.get("content", [])
        is_header = any(c.get("type") == "tableHeader" for c in cells)
        cell_texts = [
            table_cell_content(c.get("content", []))
            .strip()
            .replace("|", "\\|")
            .replace("\n", "<br>")
            for c in cells
        ]
        md_rows.append("| " + " | ".join(cell_texts) + " |")
        if is_header and not separator_added:
            md_rows.append("| " + " | ".join(["---"] * len(cell_texts)) + " |")
            separator_added = True

    # Drop tables that end up with only a header row (no data)
    if separator_added and len(md_rows) <= 2:
        return ""

    if not separator_added and md_rows:
        # No header row found — add an empty header so the table is valid GFM
        num_cols = md_rows[0].count("|") - 1
        md_rows = [
            "| " + " | ".join([""] * num_cols) + " |",
            "| " + " | ".join(["---"] * num_cols) + " |",
        ] + md_rows

    return "\n".join(md_rows)


# ---------------------------------------------------------------------------
# List items (recursive, supports nested lists)
# ---------------------------------------------------------------------------

def list_item_to_md(li_node: dict, depth: int = 0, ordered: bool = False, index: int = 1) -> str:
    indent = "  " * depth
    prefix = f"{index}. " if ordered else "- "
    main_parts: list[str] = []
    nested: list[str] = []

    for n in li_node.get("content", []):
        t = n.get("type", "")
        if t == "paragraph":
            main_parts.append(inline_content(n.get("content", [])))
        elif t in ("bulletList", "orderedList"):
            sub_ordered = t == "orderedList"
            sub_items = [
                list_item_to_md(sli, depth + 1, sub_ordered, i + 1)
                for i, sli in enumerate(n.get("content", []))
            ]
            nested.append("\n".join(item for item in sub_items if item))
        elif t == "taskList":
            nested.append(
                "\n".join(
                    f"  {indent}{line}" for line in task_items_to_md(n.get("content", []))
                )
            )
        else:
            md = node_to_md(n)
            if md.strip():
                nested.append("\n".join(f"  {indent}{line}" for line in md.splitlines()))

    main_text = " ".join(p for p in main_parts if p)
    nested_text = "\n".join(line for line in nested if line)
    if not main_text and not nested_text:
        return ""  # skip empty list items entirely
    result = f"{indent}{prefix}{main_text}"
    if nested_text:
        result += "\n" + nested_text
    return result


# ---------------------------------------------------------------------------
# Main node dispatcher
# ---------------------------------------------------------------------------

def node_to_md(node: dict, depth: int = 0) -> str:  # noqa: C901 (complexity OK here)
    t = node.get("type", "")
    children = node.get("content", [])
    attrs = node.get("attrs", {})

    if t == "heading":
        level = attrs.get("level", 1)
        text = inline_content(children)
        return "#" * level + " " + text

    if t == "paragraph":
        return inline_content(children)

    if t == "codeBlock":
        lang = attrs.get("language", "")
        code = "".join(n.get("text", "") for n in children if n.get("type") == "text")
        fence = _safe_fence(code)
        return f"{fence}{lang}\n{code}\n{fence}"

    if t == "bulletList":
        items = [list_item_to_md(li, depth) for li in children]
        return "\n".join(i for i in items if i)

    if t == "orderedList":
        items = [
            list_item_to_md(li, depth, ordered=True, index=i + 1)
            for i, li in enumerate(children)
        ]
        return "\n".join(i for i in items if i)

    if t == "taskList":
        return "\n".join(task_items_to_md(children))

    if t == "table":
        return table_to_md(node)

    if t == "extension":
        return _extension_to_md(node)

    if t == "bodiedExtension":
        return _bodied_extension_to_md(node, children)

    if t == "expand":
        title = attrs.get("title", "").strip()
        inner = _join_blocks(children)
        body_parts = ([f"**{title}**"] if title else [])
        if inner.strip():
            body_parts.append(inner)
        label = title if title else "expand"
        return f"<!-- expand: {label} -->\n" + "\n\n".join(body_parts) + "\n<!-- /expand -->"

    if t == "rule":
        return "---"

    if t == "panel":
        panel_type = attrs.get("panelType", "info")
        label = panel_type.capitalize()
        inner = _join_blocks(children)
        lines = inner.splitlines()
        first = f"> **{label}:** {lines[0]}" if lines else f"> **{label}:**"
        rest = "\n".join(f"> {line}" for line in lines[1:]) if len(lines) > 1 else ""
        return first + ("\n" + rest if rest else "")

    if t in ("mediaSingle", "mediaGroup"):
        return _media_marker(_media_name(node))

    if t == "mediaInline":
        return _media_marker(_media_name(node))

    if t == "media":
        return ""  # covered by its mediaSingle/mediaGroup parent

    if t in ("layoutSection", "layoutColumn"):
        return _join_blocks(children)

    # Fallback: recurse into children
    if children:
        return _join_blocks(children)

    return ""


def _extension_to_md(node: dict) -> str:
    attrs = node.get("attrs", {})
    key = attrs.get("extensionKey", "")
    params = attrs.get("parameters", {}).get("macroParams", {})

    # Table of contents — always discard
    _TOC_KEYS = {"toc", "table-of-contents", "toc2", "pagetree"}
    if key in _TOC_KEYS or key.startswith("toc-"):
        return ""

    # PlantUML
    _PLANTUML_KEYS = {"plantuml", "puml", "plantuml-macro", "plantumlrender"}
    if key in _PLANTUML_KEYS or "plantuml" in key.lower() or "puml" in key.lower():
        encoded = params.get("data", {}).get("value", "")
        if encoded:
            return f"```plantuml\n{decode_plantuml(encoded)}\n```"
        return ""

    # Code block macros
    _CODE_KEYS = {"code", "code-pro", "code-block", "syntaxhighlighter"}
    if key in _CODE_KEYS:
        lang = params.get("language", {}).get("value", "")
        body = node.get("body", "") or params.get("__bodyContent", {}).get("value", "")
        fence = _safe_fence(body)
        return f"{fence}{lang}\n{body}\n{fence}"

    # Alert/info panels
    _PANEL_KEYS = {"info", "note", "warning", "tip", "panel"}
    if key in _PANEL_KEYS:
        label = key.capitalize()
        body_text = params.get("body", {}).get("value", "")
        return f"> **{label}:** {body_text}"

    # Draw.io diagrams
    _DRAWIO_KEYS = {"drawio", "drawio-confluence-plugin", "drawio-sketch"}
    if key in _DRAWIO_KEYS or "drawio" in key.lower():
        name = (
            params.get("diagramName", {}).get("value", "")
            or params.get("diagramDisplayName", {}).get("value", "")
        )
        return f"~~(drawio diagram: {name})~~" if name else "~~(drawio diagram)~~"

    # Better Code Block (paste-code-macro)
    if key == "paste-code-macro":
        lang = params.get("language", {}).get("value", "")
        title = params.get("title", {}).get("value", "")
        body = params.get("__bodyContent", {}).get("value", "")
        fence = _safe_fence(body)
        result = []
        if title:
            result.append(f"**{title}**\n\n")
        result.append(f"{fence}{lang}\n{body}\n{fence}")
        return "".join(result)

    print(f"UNSUPPORTED extension: {key!r}", file=sys.stderr)
    return f"~~(unsupported macro: {key})~~"


def _bodied_extension_to_md(node: dict, children: list) -> str:
    attrs = node.get("attrs", {})
    key = attrs.get("extensionKey", "")
    params = attrs.get("parameters", {}).get("macroParams", {})

    _PANEL_KEYS = {"info", "note", "warning", "tip"}
    if key in _PANEL_KEYS:
        label = key.capitalize()
        inner = _join_blocks(children)
        return f"> **{label}:**\n" + "\n".join(f"> {line}" for line in inner.splitlines())

    if key == "details":
        return _join_blocks(children)

    _EXPAND_KEYS = {"expand", "expand-macro"}
    if key in _EXPAND_KEYS or "expand" in key:
        title = params.get("title", {}).get("value", "").strip()
        inner = _join_blocks(children)
        body_parts = ([f"**{title}**"] if title else [])
        if inner.strip():
            body_parts.append(inner)
        label = title if title else "expand"
        return f"<!-- expand: {label} -->\n" + "\n\n".join(body_parts) + "\n<!-- /expand -->"

    return _join_blocks(children)


def _join_blocks(nodes: list) -> str:
    """Convert a list of block nodes and join non-empty results with a blank line."""
    parts = [node_to_md(n) for n in nodes]
    return "\n\n".join(p for p in parts if p.strip())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: convert.py <adf_json_path> <output_md_path>", file=sys.stderr)
        sys.exit(1)

    json_path, out_path = sys.argv[1], sys.argv[2]

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data["title"]
    top_nodes = data["body"]["content"]

    converted = [node_to_md(n) for n in top_nodes]

    markdown = "# " + title + "\n\n" + "\n\n".join(converted)

    # Normalise whitespace
    lines = [line.rstrip() for line in markdown.splitlines()]
    markdown = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Written: {out_path} ({len(markdown.splitlines())} lines)")


if __name__ == "__main__":
    main()

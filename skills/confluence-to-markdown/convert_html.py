#!/usr/bin/env python3
"""
Confluence HTML → Markdown converter for the confluence-to-markdown skill.

Usage:
    python3 convert_html.py <input> [-o OUTPUT_MD] [--title TITLE]

    <input>        A JSON file containing the page as HTML (a "title" next to a
                   "body": {"value": "<html>"} anywhere in the JSON), or a plain .html
                   file (then pass --title).
    -o OUTPUT_MD   Destination file. Defaults to <kebab-case-title>.md next to <input>.
    --title TITLE  Page title; only needed for a plain .html file.

Layout of this file, top to bottom:
    1. Constants           tag sets, data-types and labels used by the converters
    2. Diagnostics         stderr logging for placeholders and unsupported content
    3. Text helpers        small string utilities
    4. Link titles         derive a readable title from a bare URL (one function per site)
    5. Minimal DOM         HTML parsing into Node trees
    6. Inline              text-level elements; add a tag by registering in INLINE_HANDLERS
    7. Blocks              block-level elements; add a tag by registering in BLOCK_HANDLERS
    8. Macros              Confluence extensions; add a macro by registering in EXTENSION_HANDLERS
    9. Lists and tables
   10. Entry point
"""

import argparse
import base64
import json
import re
import sys
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------

VOID_TAGS = {"input", "br", "hr", "img", "meta", "link"}
BLOCK_TAGS = {"p", "ul", "ol", "table", "pre", "div", "figure", "details", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6", "hr"}
TOC_KEYS = {"toc", "table-of-contents", "toc2", "pagetree"}
EXTENSION_TYPES = {"extension", "bodied-extension", "inline-extension"}
KNOWN_TYPES = {"mention", "placeholder", "task-list", "task-item", "media-single", "media",
               "status", "date", "emoji"} | EXTENSION_TYPES
PANEL_LABELS = {"panel-info": "Info", "panel-note": "Note", "panel-warning": "Warning",
                "panel-error": "Error", "panel-success": "Success", "panel-tip": "Tip"}


# ---------------------------------------------------------------------------
# 2. Diagnostics
# ---------------------------------------------------------------------------

_warned_types = set()


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _placeholder(kind: str, name: str = "") -> str:
    """Return a struck-through placeholder for non-text content, and log that it was omitted."""
    marker = f"~~({kind}: {name})~~" if name else f"~~({kind})~~"
    _log(f"Content omitted, converted to placeholder: {marker}")
    return marker


def warn_unknown(n: "Node") -> str:
    """Handle an unknown data-type; its content is still rendered as plain text.

    Log a warning once per data-type, and return a placeholder to place where the element
    occurs, so every occurrence is easy to find in the Markdown. Return "" for known types.
    """
    dt = n.dtype
    if not dt or dt in KNOWN_TYPES or dt.startswith("panel"):
        return ""
    if dt not in _warned_types:
        _warned_types.add(dt)
        _log(f"UNSUPPORTED data-type: {dt!r} (rendered as plain content)")
    return f"~~(unsupported data-type: {dt})~~"


# ---------------------------------------------------------------------------
# 3. Text helpers
# ---------------------------------------------------------------------------

def _longest_backtick_run(text: str) -> int:
    return max((len(m.group()) for m in re.finditer(r"`+", text)), default=0)


def _safe_fence(code: str) -> str:
    """Return a backtick fence longer than any run of backticks in *code*."""
    return "`" * max(3, _longest_backtick_run(code) + 1)


def _code_span(text: str) -> str:
    """Return *text* as an inline code span, padded and fenced so embedded backticks survive."""
    fence = "`" * (_longest_backtick_run(text) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _wrap(text: str, mark: str) -> str:
    """Wrap text in a Markdown mark (**, *, ~~), keeping surrounding spaces outside the mark."""
    core = text.strip()
    if not core:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return f"{lead}{mark}{core}{mark}{trail}"


def _clean_inline(s: str) -> str:
    """Normalize spaces in joined inline text without touching code span contents.

    - Drops a space right after an opening ** (artifacts like "** OnPrem")
    - Drops a space right before a closing ** (artifacts like "OnPrem **")
    - Strips leading/trailing whitespace of the whole inline run.
    """
    s = re.sub(r"(^|\s)\*\*\s+", r"\1**", s)
    s = re.sub(r"\s+\*\*(?=\s|$|[.,;:!?)\]}>])", "**", s)
    return s.strip()


def _indent(s: str, prefix: str) -> str:
    """Indent every non-empty line of s with prefix."""
    return "\n".join(prefix + l if l else l for l in s.splitlines())


def slugify(title: str) -> str:
    """Turn a page title into a kebab-case file name."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "page"


def decode_plantuml(encoded: str) -> str:
    """Decode PlantUML extension data: standard base64 → raw deflate decompress.

    Some macros URL-encode the PlantUML source before compressing. Unquote the
    result only when it actually looks like a PlantUML document, so sources that
    were stored raw are left untouched.
    """
    # Some macros store the source URL-encoded and uncompressed.
    if encoded.startswith(("%40startuml", "@startuml")):
        return unquote(encoded)
    try:
        raw = zlib.decompress(base64.b64decode(encoded), -15).decode("utf-8")
    except Exception as exc:
        return f"# decode error: {exc}"
    decoded = unquote(raw)
    return decoded if decoded.lstrip().startswith("@startuml") else raw


# ---------------------------------------------------------------------------
# 4. Link titles
# ---------------------------------------------------------------------------

def _slug_to_title(slug: str) -> str:
    """Convert a URL slug or file name to readable prose.

    Handles hyphens, underscores, and percent-decoded spaces.
    Collapses runs of digits-only tokens that look like page IDs.
    """
    slug = re.sub(r"[-_+]", " ", unquote(slug)).strip()
    tokens = [t for t in slug.split() if not re.fullmatch(r"\d{6,}", t)]
    return " ".join(tokens) if tokens else slug


def _camel_to_title(name: str) -> str:
    """Split a camelCase or PascalCase identifier into spaced Title Case words."""
    spaced = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", name)
    return re.sub(r"[-_]", " ", spaced).strip().capitalize()


def _path_segments(path: str, skip=()) -> list:
    return [p for p in path.split("/") if p and p not in skip]


def _title_figma(host, path, fragment):
    parts = _path_segments(path, skip=("design", "file", "proto"))
    if not parts:
        return "Figma design"
    # The first meaningful segment is the file ID; the second is the name.
    return _slug_to_title(parts[1] if len(parts) > 1 else parts[0])


def _title_atlassian(host, path, fragment):
    # Confluence page: …/pages/<id>/<title-slug>
    m = re.search(r"/pages/\d+/([^/]+)$", path)
    if m:
        return _slug_to_title(m.group(1))
    # Confluence page with ID only: …/pages/<id>
    m = re.search(r"/pages/(\d+)$", path)
    if m:
        return f"Confluence page {m.group(1)}"
    # Jira issue: …/browse/PROJ-123
    m = re.search(r"/browse/([A-Z]+-\d+)", path)
    if m:
        return m.group(1)
    # Spaces index or other Confluence URL: last non-trivial segment
    segments = _path_segments(path, skip=("wiki", "spaces", "pages"))
    return _slug_to_title(segments[-1]) if segments else "Atlassian page"


def _title_swagger(host, path, fragment):
    """Combine the tag and operation name from a fragment like ``#/Tag/operationId``."""
    parts = [p for p in fragment.lstrip("/").split("/") if p]
    if len(parts) >= 2:
        op = _camel_to_title(re.sub(r"_\d+$", "", parts[-1]))
        return f"{_slug_to_title(parts[-2])} — {op}"
    if parts:
        return _slug_to_title(re.sub(r"_\d+$", "", parts[-1]))
    return None


def _title_rally(host, path, fragment):
    return "Rally item"


# Tried in order; the first matcher that holds wins, unless its handler returns None.
# To support a new site, add a (matcher, handler) pair here.
LINK_TITLE_RULES = [
    (lambda host, path, frag: "figma.com" in host, _title_figma),
    (lambda host, path, frag: "atlassian.net" in host, _title_atlassian),
    (lambda host, path, frag: "api-docs" in path or "swagger" in path or "api-docs" in frag,
     _title_swagger),
    (lambda host, path, frag: "rallydev.com" in host or "rally1.rally" in host, _title_rally),
]


def _inlinecard_title(url: str) -> str:
    """Derive a human-readable link title from a URL using LINK_TITLE_RULES.

    Falls back to the last non-empty path segment, without a file extension.
    """
    parsed = urlparse(url)
    host, path, fragment = parsed.hostname or "", unquote(parsed.path), unquote(parsed.fragment)
    for matches, handler in LINK_TITLE_RULES:
        if matches(host, path, fragment):
            title = handler(host, path, fragment)
            if title is not None:
                return title
    segments = _path_segments(path)
    if segments:
        return _slug_to_title(re.sub(r"\.[a-z]{2,4}$", "", segments[-1]))
    return host or url


# ---------------------------------------------------------------------------
# 5. Minimal DOM
# ---------------------------------------------------------------------------

class Node:
    """One HTML element; text nodes are plain str entries in children."""

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.parent = parent

    @property
    def dtype(self):
        return self.attrs.get("data-type", "")

    def elements(self, *tags):
        """Child elements (no text nodes), optionally restricted to the given tags."""
        return [c for c in self.children
                if not isinstance(c, str) and (not tags or c.tag in tags)]

    def first(self, tag):
        """First child element with this tag, or None."""
        return next(iter(self.elements(tag)), None)


class _Builder(HTMLParser):
    """Builds a Node tree from HTML; unclosed or mismatched tags are tolerated."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID_TAGS:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        # Close the nearest open ancestor with this tag; ignore stray end tags.
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(markup: str) -> Node:
    """Parse an HTML string into a Node tree and return its root."""
    b = _Builder()
    b.feed(markup)
    b.close()
    return b.root


def _text(n) -> str:
    """Return the plain text of a node and all its descendants."""
    if isinstance(n, str):
        return n
    return "".join(_text(c) for c in n.children)


# ---------------------------------------------------------------------------
# 6. Inline
# ---------------------------------------------------------------------------

def _inline_link(n: Node) -> str:
    href = n.attrs.get("href", "")
    text = inline(n.children).strip()
    if not href:
        return text
    if not text or text == href:
        text = _inlinecard_title(href)
    return f"[{text}]({href})"


def _inline_status(n: Node) -> str:
    label = _text(n).strip()
    return f"**`{label.upper()}`**" if label else ""


# Tag → function(node) returning Markdown. Tags not listed render their children as-is.
INLINE_HANDLERS = {
    "br": lambda n: "<br>",
    "strong": lambda n: _wrap(inline(n.children), "**"),
    "b": lambda n: _wrap(inline(n.children), "**"),
    "em": lambda n: _wrap(inline(n.children), "*"),
    "i": lambda n: _wrap(inline(n.children), "*"),
    "s": lambda n: _wrap(inline(n.children), "~~"),
    "del": lambda n: _wrap(inline(n.children), "~~"),
    "strike": lambda n: _wrap(inline(n.children), "~~"),
    "code": lambda n: _code_span(_text(n)),
    "a": _inline_link,
    "input": lambda n: "",
}

# data-type → function(node), consulted when the tag has no handler.
INLINE_TYPE_HANDLERS = {
    "status": _inline_status,
}


def inline(nodes) -> str:
    """Convert inline nodes (text, emphasis, code, links) to a single Markdown string."""
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(re.sub(r"\s+", " ", n))
            continue
        out.append(warn_unknown(n))
        if n.dtype == "placeholder":
            continue
        handler = INLINE_HANDLERS.get(n.tag) or INLINE_TYPE_HANDLERS.get(n.dtype)
        out.append(handler(n) if handler else inline(n.children))
    return "".join(out)


# ---------------------------------------------------------------------------
# 7. Blocks
# ---------------------------------------------------------------------------

def blocks(nodes) -> str:
    """Convert a sequence of mixed block/inline nodes; stray inline runs become paragraphs."""
    parts, run = [], []

    def flush():
        if run:
            s = _clean_inline(inline(run))
            if s:
                parts.append(s)
            run.clear()

    for n in nodes:
        if isinstance(n, str) or n.tag not in BLOCK_TAGS:
            run.append(n)
        else:
            flush()
            s = block(n)
            if s.strip():
                parts.append(s)
    flush()
    return "\n\n".join(parts)


def block(n: Node) -> str:
    """Convert one block-level node, preceded by a placeholder if its data-type is unknown."""
    note = warn_unknown(n)
    md = BLOCK_HANDLERS.get(n.tag, lambda n: blocks(n.children))(n)
    return f"{note}\n{md}" if note and md.strip() else md


def quote(inner: str, label: str = "") -> str:
    """Prefix every line with "> ", optionally starting with a bold label (used for panels)."""
    body = "\n".join(f"> {l}" if l else ">" for l in inner.splitlines())
    return f"> **{label}:**\n{body}" if label else body


def _heading(n: Node) -> str:
    return "#" * int(n.tag[1]) + " " + _clean_inline(inline(n.children))


def _list_block(n: Node) -> str:
    return task_list(n) if n.dtype == "task-list" else list_md(n)


def pre_md(n: Node) -> str:
    """Convert <pre><code class="language-x"> to a fenced code block."""
    code = n.first("code")
    m = re.search(r"language-(\S+)", code.attrs.get("class", "")) if code is not None else None
    lang = m.group(1) if m else ""
    text = _text(code if code is not None else n)
    fence = _safe_fence(text)
    return f"{fence}{lang}\n{text}\n{fence}"


def media_md(n: Node) -> str:
    """Replace an image/media element with a placeholder; media is not downloaded."""
    def find(x):
        for c in x.elements():
            if c.dtype == "media" or c.tag == "img":
                return c
            found = find(c)
            if found:
                return found

    m = find(n)
    name = (m.attrs.get("data-alt") or m.attrs.get("alt") or m.attrs.get("data-id") or "") if m else ""
    return _placeholder("image", name)


def details_md(n: Node) -> str:
    """Convert an expand macro (<details>) to HTML comment markers around its content."""
    summary = n.first("summary")
    title = _clean_inline(inline(summary.children)) if summary else ""
    inner = blocks([c for c in n.children if c is not summary])
    body = ([f"**{title}**"] if title else []) + ([inner] if inner.strip() else [])
    return f"<!-- expand: {title or 'expand'} -->\n" + "\n\n".join(body) + "\n<!-- /expand -->"


def div_md(n: Node) -> str:
    """Convert a <div> by its data-type: macro, panel, media, or plain container."""
    dt = n.dtype
    if dt in EXTENSION_TYPES:
        return extension_md(n)
    if dt.startswith("panel"):
        return quote(blocks(n.children), PANEL_LABELS.get(dt, "Note"))
    if dt == "media":
        return _placeholder("image", n.attrs.get("data-alt", ""))
    return blocks(n.children)


# Tag → function(node) returning Markdown. Tags not listed render their children as blocks.
BLOCK_HANDLERS = {
    **{f"h{i}": _heading for i in range(1, 7)},
    "p": lambda n: _clean_inline(inline(n.children)),
    "ul": _list_block,
    "ol": _list_block,
    "table": lambda n: table_md(n),
    "pre": pre_md,
    "hr": lambda n: "---",
    "blockquote": lambda n: quote(blocks(n.children)),
    "details": details_md,
    "figure": media_md,
    "div": div_md,
}


# ---------------------------------------------------------------------------
# 8. Macros
# ---------------------------------------------------------------------------

def _param(params: dict, name: str) -> str:
    return params.get(name, {}).get("value", "")


def _ext_toc(n, params):
    """Table-of-contents macros carry no content of their own."""
    return ""


def _ext_plantuml(n, params):
    enc = _param(params, "data")
    return f"```plantuml\n{decode_plantuml(enc)}\n```" if enc else ""


def _ext_drawio(n, params):
    """draw.io data is an attachment, not in the page body; leave a placeholder to resolve later."""
    name = _param(params, "diagramName") or _param(params, "diagramDisplayName")
    return _placeholder("drawio diagram", name)


def _ext_code_snippet(n, params):
    """Code Snippet macro: the code is in a parameter, not in the page body."""
    body, title, lang = (_param(params, k) for k in ("__bodyContent", "title", "language"))
    fence = _safe_fence(body)
    head = f"**{title}**\n\n" if title else ""
    return f"{head}{fence}{lang}\n{body}\n{fence}"


# Tried in order against the macro key; the first match renders the macro.
# To support a new macro, add a (matcher, handler) pair; handler(node, macroParams) → Markdown.
EXTENSION_HANDLERS = [
    (lambda key: key in TOC_KEYS or key.startswith("toc-"), _ext_toc),
    (lambda key: "plantuml" in key.lower() or "puml" in key.lower(), _ext_plantuml),
    (lambda key: "drawio" in key.lower(), _ext_drawio),
    (lambda key: key == "paste-code-macro", _ext_code_snippet),
]


def extension_md(n: Node) -> str:
    """Convert a Confluence macro. Unknown macros become a placeholder and a stderr warning."""
    key = n.attrs.get("data-extension-key", "")
    try:
        params = json.loads(n.attrs.get("data-parameters", "{}") or "{}").get("macroParams", {})
    except json.JSONDecodeError:
        params = {}
    for matches, handler in EXTENSION_HANDLERS:
        if matches(key):
            return handler(n, params)
    # Bodied macros wrap ordinary content, so render their children.
    if n.dtype == "bodied-extension":
        return blocks(n.children)
    _log(f"UNSUPPORTED extension: {key!r}")
    return f"~~(unsupported macro: {key})~~"


# ---------------------------------------------------------------------------
# 9. Lists and tables
# ---------------------------------------------------------------------------

def _item_body(li: Node, indent: int):
    """Return (first-line text, list of continuation lines) for an <li>."""
    texts, extra = [], []
    for c in li.children:
        if isinstance(c, str):
            texts.append(inline([c]))
        elif c.tag in ("ul", "ol"):
            extra.append(task_list(c, indent + 1) if c.dtype == "task-list" else list_md(c, indent + 1))
        elif c.tag in ("pre", "table", "div", "figure", "details"):
            extra.append(_indent(block(c), "  " * (indent + 1)))
        elif c.tag == "p":
            texts.append(inline(c.children))
        else:
            texts.append(inline([c]))
    return _clean_inline(" ".join(t.strip() for t in texts if t.strip())), extra


def list_md(n: Node, indent: int = 0) -> str:
    """Convert <ul>/<ol> to a Markdown list, nesting by two spaces per level."""
    ordered = n.tag == "ol"
    start = int(n.attrs.get("start", 1) or 1) if ordered else 1
    lines = []
    for i, li in enumerate(n.elements("li")):
        marker = f"{start + i}." if ordered else "-"
        text, extra = _item_body(li, indent)
        lines.append("  " * indent + f"{marker} {text}")
        lines.extend(extra)
    return "\n".join(lines)


def task_list(n: Node, indent: int = 0) -> str:
    """Convert a Confluence task list to "- [ ]" / "- [x]" items."""
    lines = []
    for li in n.elements("li", "div"):
        box = li.first("input")
        done = (box is not None and ("checked" in box.attrs or n.attrs.get("data-state") == "DONE")) \
            or li.attrs.get("data-state") == "DONE"
        text, extra = _item_body(li, indent)
        lines.append("  " * indent + f"- [{'x' if done else ' '}] {text}")
        lines.extend(extra)
    return "\n".join(lines)


def _pre_in_cell(m: "re.Match") -> str:
    """Fenced code does not render inside a table cell, so emit an HTML <pre> block instead."""
    code = m.group(1).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # \0 stands in for a line break so _cell does not collapse or re-escape it.
    return "<pre><code>" + code.replace("|", "&#124;").replace("\n", "\0") + "</code></pre>"


def _cell(c: Node) -> str:
    """Render a table cell on one line: blocks are joined with <br>, pipes are escaped."""
    s = blocks(c.children)
    # Must run before newlines become <br>, while the fence markers are still intact.
    s = re.sub(r"```\w*\n(.*?)\n```", _pre_in_cell, s, flags=re.S)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.replace("\n", "<br>").replace("|", "\\|").replace("\0", "<br>").strip()


def _table_rows(n: Node) -> list:
    rows = []
    for c in n.elements():
        if c.tag == "tr":
            rows.append(c)
        elif c.tag in ("thead", "tbody", "tfoot", "colgroup"):
            rows.extend(_table_rows(c))
    return rows


def table_md(n: Node) -> str:
    """Convert a <table> to a Markdown table; a header row is empty unless the first row is all <th>."""
    rows = _table_rows(n)
    if not rows:
        return ""
    grid = [[(_cell(c), c.tag) for c in r.elements("td", "th")] for r in rows]
    width = max(len(r) for r in grid)
    grid = [r + [("", "td")] * (width - len(r)) for r in grid]
    if all(tag == "th" for _, tag in grid[0]):
        header, body = [c for c, _ in grid[0]], grid[1:]
    else:
        header, body = [""] * width, grid
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    out += ["| " + " | ".join(c for c, _ in r) + " |" for r in body]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 10. Entry point
# ---------------------------------------------------------------------------

def _find_page(obj):
    """Find the dict holding the page body anywhere in a JSON envelope, whatever its wrapper."""
    if isinstance(obj, dict):
        body = obj.get("body")
        if isinstance(body, dict) and "value" in body:
            return obj
        if isinstance(body, str) and "title" in obj:
            return {**obj, "body": {"value": body, "format": "html"}}
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for v in children:
        found = _find_page(v)
        if found:
            return found
    return None


def load(path: str, title_arg: str):
    """Return (title, html) from a JSON page envelope or a plain HTML file."""
    raw = Path(path).read_text(encoding="utf-8")
    if not raw.lstrip().startswith(("{", "[")):
        return title_arg, raw
    data = json.loads(raw)
    if isinstance(data, dict) and (data.get("ok") is False or ("error" in data and "data" not in data)):
        err = data.get("error", {})
        sys.exit(f"Input is an error response, not page content: {err.get('message', data)}")
    page = _find_page(data)
    if not page:
        sys.exit("No page body found in the JSON; fetch the full body (not a summary/outline) as HTML")
    body = page["body"]
    if body.get("format", "html") != "html":
        sys.exit(f"Expected body format 'html', got {body.get('format')!r}")
    return title_arg or page.get("title", ""), body["value"]


def convert(markup: str, title: str = "") -> str:
    """Convert page HTML to a Markdown document, with the title as its first heading."""
    md = blocks(parse(markup).children)
    md = f"# {title}\n\n{md}" if title else md
    md = "\n".join(l.rstrip() for l in md.splitlines())
    return re.sub(r"\n{3,}", "\n\n", md).rstrip() + "\n"


def _output_path(requested: str, input_path: str, title: str) -> Path:
    """Return the requested file path, or <slug>.md next to the input when none is given."""
    if requested:
        return Path(requested)
    return Path(input_path).resolve().parent / (slugify(title) + ".md")


def main() -> None:
    """Parse arguments, convert the page, and write the Markdown file."""
    ap = argparse.ArgumentParser(description="Convert a Confluence HTML page to Markdown.")
    ap.add_argument("input", help="page JSON envelope, or a plain .html file (then pass --title)")
    ap.add_argument("-o", "--output", default="", help="output file path")
    ap.add_argument("--title", default="", help="page title; only needed for a plain .html file")
    args = ap.parse_args()

    title, markup = load(args.input, args.title)
    out = _output_path(args.output, args.input, title)
    md = convert(markup, title)
    out.write_text(md, encoding="utf-8")
    print(f"Written: {out} ({len(md.splitlines())} lines)")


if __name__ == "__main__":
    main()

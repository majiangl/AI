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

"""

import base64
import json
import re
import sys
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

# ---------------------------------------------------------------------------
# Helpers
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


def _media_marker(name: str) -> str:
    """Markdown marker (struck through) signalling an image is not represented (non-text content)."""
    return f"~~(image: {name})~~" if name else "~~(image)~~"


def _safe_fence(code: str) -> str:
    """Return a backtick fence longer than any run of backticks in *code*."""
    longest = max((len(m.group()) for m in re.finditer(r"`+", code)), default=0)
    return "`" * max(3, longest + 1)


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


VOID = {"input", "br", "hr", "img", "meta", "link"}
TOC_KEYS = {"toc", "table-of-contents", "toc2", "pagetree"}


# ---------------------------------------------------------------------------
# Minimal DOM
# ---------------------------------------------------------------------------

class Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.parent = parent

    @property
    def dtype(self):
        return self.attrs.get("data-type", "")


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse(markup: str) -> Node:
    b = _Builder()
    b.feed(markup)
    b.close()
    return b.root


# ---------------------------------------------------------------------------
# Inline
# ---------------------------------------------------------------------------

def _wrap(text: str, mark: str) -> str:
    core = text.strip()
    if not core:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return f"{lead}{mark}{core}{mark}{trail}"


def inline(nodes) -> str:
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(re.sub(r"\s+", " ", n))
            continue
        t = n.tag
        warn_unknown(n)
        if n.dtype == "placeholder":
            continue
        if t == "br":
            out.append("<br>")
        elif t in ("strong", "b"):
            out.append(_wrap(inline(n.children), "**"))
        elif t in ("em", "i"):
            out.append(_wrap(inline(n.children), "*"))
        elif t in ("s", "del", "strike"):
            out.append(_wrap(inline(n.children), "~~"))
        elif t == "code":
            text = "".join(_text(c) for c in n.children)
            fence = "`" * (max((len(m) for m in re.findall(r"`+", text)), default=0) + 1)
            pad = " " if text.startswith("`") or text.endswith("`") else ""
            out.append(f"{fence}{pad}{text}{pad}{fence}")
        elif t == "a":
            href = n.attrs.get("href", "")
            text = inline(n.children).strip()
            if not href:
                out.append(text)
            else:
                if not text or text == href:
                    text = _inlinecard_title(href)
                out.append(f"[{text}]({href})")
        elif t == "input" and n.attrs.get("type") == "checkbox":
            continue
        elif t in ("span", "u", "sub", "sup", "mark", "time"):
            out.append(inline(n.children))
        elif t == "input":
            continue
        else:
            out.append(inline(n.children))
    return "".join(out)


def _text(n) -> str:
    if isinstance(n, str):
        return n
    return "".join(_text(c) for c in n.children)


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

KNOWN_TYPES = {"mention", "placeholder", "task-list", "task-item", "media-single", "media",
               "extension", "bodied-extension", "inline-extension", "status", "date", "emoji"}
_warned = set()


def warn_unknown(n: "Node") -> None:
    dt = n.dtype
    if dt and dt not in KNOWN_TYPES and not dt.startswith("panel") and dt not in _warned:
        _warned.add(dt)
        print(f"UNSUPPORTED data-type: {dt!r} (rendered as plain content)", file=sys.stderr)


BLOCK_TAGS = {"p", "ul", "ol", "table", "pre", "div", "figure", "details", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6", "hr"}


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
    t = n.tag
    warn_unknown(n)
    if re.fullmatch(r"h[1-6]", t):
        return "#" * int(t[1]) + " " + _clean_inline(inline(n.children))
    if t == "p":
        return _clean_inline(inline(n.children))
    if t in ("ul", "ol"):
        if n.dtype == "task-list":
            return task_list(n)
        return list_md(n)
    if t == "table":
        return table_md(n)
    if t == "pre":
        return pre_md(n)
    if t == "hr":
        return "---"
    if t == "blockquote":
        return quote(blocks(n.children))
    if t == "details":
        return details_md(n)
    if t == "figure":
        return media_md(n)
    if t == "div":
        return div_md(n)
    return blocks(n.children)


def quote(inner: str, label: str = "") -> str:
    lines = inner.splitlines()
    if label:
        return f"> **{label}:**\n" + "\n".join(f"> {l}" if l else ">" for l in lines)
    return "\n".join(f"> {l}" if l else ">" for l in lines)


def pre_md(n: Node) -> str:
    code = next((c for c in n.children if not isinstance(c, str) and c.tag == "code"), None)
    lang = ""
    if code is not None:
        m = re.search(r"language-(\S+)", code.attrs.get("class", ""))
        lang = m.group(1) if m else ""
    text = _text(code if code is not None else n)
    fence = _safe_fence(text)
    return f"{fence}{lang}\n{text}\n{fence}"


def media_md(n: Node) -> str:
    def find(x):
        for c in x.children:
            if isinstance(c, str):
                continue
            if c.dtype == "media" or c.tag == "img":
                return c
            r = find(c)
            if r:
                return r
    m = find(n)
    name = (m.attrs.get("data-alt") or m.attrs.get("alt") or m.attrs.get("data-id") or "") if m else ""
    return _media_marker(name)


def details_md(n: Node) -> str:
    summary = next((c for c in n.children if not isinstance(c, str) and c.tag == "summary"), None)
    title = _clean_inline(inline(summary.children)) if summary else ""
    rest = [c for c in n.children if c is not summary]
    inner = blocks(rest)
    body = ([f"**{title}**"] if title else []) + ([inner] if inner.strip() else [])
    return f"<!-- expand: {title or 'expand'} -->\n" + "\n\n".join(body) + "\n<!-- /expand -->"


def div_md(n: Node) -> str:
    dt = n.dtype
    if dt in ("extension", "bodied-extension", "inline-extension"):
        return extension_md(n)
    if dt.startswith("panel"):
        label = {"panel-info": "Info", "panel-note": "Note", "panel-warning": "Warning",
                 "panel-error": "Error", "panel-success": "Success", "panel-tip": "Tip"}.get(dt, "Note")
        return quote(blocks(n.children), label)
    if dt == "media":
        return _media_marker(n.attrs.get("data-alt", ""))
    return blocks(n.children)


def extension_md(n: Node) -> str:
    key = n.attrs.get("data-extension-key", "")
    try:
        params = json.loads(n.attrs.get("data-parameters", "{}") or "{}").get("macroParams", {})
    except json.JSONDecodeError:
        params = {}
    if key in TOC_KEYS or key.startswith("toc-"):
        return ""
    if "plantuml" in key.lower() or "puml" in key.lower():
        enc = params.get("data", {}).get("value", "")
        return f"```plantuml\n{decode_plantuml(enc)}\n```" if enc else ""
    if "drawio" in key.lower():
        name = (params.get("diagramName", {}).get("value", "")
                or params.get("diagramDisplayName", {}).get("value", ""))
        return f"~~(drawio diagram: {name})~~" if name else "~~(drawio diagram)~~"
    if n.dtype == "bodied-extension":
        return blocks(n.children)
    print(f"UNSUPPORTED extension: {key!r}", file=sys.stderr)
    return f"~~(unsupported macro: {key})~~"


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

def _item_body(li: Node, indent: int):
    """Return (first-line text, list of continuation lines) for an <li>."""
    texts, extra = [], []
    for c in li.children:
        if not isinstance(c, str) and c.tag in ("ul", "ol"):
            nested = task_list(c, indent + 1) if c.dtype == "task-list" else list_md(c, indent + 1)
            extra.append(nested)
        elif not isinstance(c, str) and c.tag in ("pre", "table", "div", "figure", "details"):
            extra.append(textwrap_indent(block(c), "  " * (indent + 1)))
        elif not isinstance(c, str) and c.tag == "p":
            texts.append(inline(c.children))
        else:
            texts.append(inline([c]))
    return _clean_inline(" ".join(t.strip() for t in texts if t.strip())), extra


def textwrap_indent(s: str, prefix: str) -> str:
    return "\n".join(prefix + l if l else l for l in s.splitlines())


def list_md(n: Node, indent: int = 0) -> str:
    ordered = n.tag == "ol"
    start = int(n.attrs.get("start", 1) or 1) if ordered else 1
    lines = []
    for i, li in enumerate(c for c in n.children if not isinstance(c, str) and c.tag == "li"):
        marker = f"{start + i}." if ordered else "-"
        text, extra = _item_body(li, indent)
        lines.append("  " * indent + f"{marker} {text}")
        lines.extend(extra)
    return "\n".join(lines)


def task_list(n: Node, indent: int = 0) -> str:
    lines = []
    for li in (c for c in n.children if not isinstance(c, str) and c.tag in ("li", "div")):
        box = next((c for c in li.children if not isinstance(c, str) and c.tag == "input"), None)
        done = box is not None and ("checked" in box.attrs or n.attrs.get("data-state") == "DONE")
        if li.attrs.get("data-state") == "DONE":
            done = True
        text, extra = _item_body(li, indent)
        lines.append("  " * indent + f"- [{'x' if done else ' '}] {text}")
        lines.extend(extra)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def _cell(c: Node) -> str:
    s = blocks(c.children)
    s = re.sub(r"\n{2,}", "\n", s)
    s = s.replace("\n", "<br>").replace("|", "\\|")
    return s.strip()


def table_md(n: Node) -> str:
    rows = []

    def walk(x):
        for c in x.children:
            if isinstance(c, str):
                continue
            if c.tag == "tr":
                rows.append(c)
            elif c.tag in ("thead", "tbody", "tfoot", "colgroup"):
                walk(c)
    walk(n)
    if not rows:
        return ""
    grid = [[(_cell(c), c.tag) for c in r.children if not isinstance(c, str) and c.tag in ("td", "th")]
            for r in rows]
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
# Entry point
# ---------------------------------------------------------------------------

def _find_page(obj):
    """Find the dict holding the page body anywhere in a JSON envelope, whatever its wrapper."""
    if isinstance(obj, dict):
        body = obj.get("body")
        if isinstance(body, dict) and "value" in body:
            return obj
        if isinstance(body, str) and "title" in obj:
            return {**obj, "body": {"value": body, "format": "html"}}
        for v in obj.values():
            r = _find_page(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_page(v)
            if r:
                return r
    return None


def load(path: str, title_arg: str):
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


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "page"


def main() -> None:
    args = sys.argv[1:]
    opts = {"-o": "", "--output": "", "--title": ""}
    for flag in list(opts):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(f"{flag} requires a value")
            opts[flag] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 1:
        print("Usage: convert_html.py <input> [-o OUTPUT_MD] [--title TITLE]", file=sys.stderr)
        sys.exit(1)

    title, markup = load(args[0], opts["--title"])
    md = blocks(parse(markup).children)
    md = "# " + title + "\n\n" + md if title else md
    lines = [l.rstrip() for l in md.splitlines()]
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"

    out = opts["-o"] or opts["--output"] or str(Path(args[0]).resolve().parent / (slugify(title) + ".md"))
    Path(out).write_text(md, encoding="utf-8")
    print(f"Written: {out} ({len(md.splitlines())} lines)")


if __name__ == "__main__":
    main()

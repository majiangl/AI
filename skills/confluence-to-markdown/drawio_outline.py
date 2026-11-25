#!/usr/bin/env python3
"""Print a text outline of a .drawio file: containers, nodes, and labeled edges.

Usage: python3 drawio_outline.py <file.drawio>

The outline is the input for hand-writing a Mermaid diagram; it is not a renderer.
"""
import base64
import html
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib


def diagram_xml(path: str):
    """Return the mxGraphModel element, decoding the diagram when draw.io stored it compressed."""
    root = ET.parse(path).getroot()
    diagram = root if root.tag == "mxGraphModel" else root.find(".//diagram")
    if diagram is None:
        raise SystemExit("No <diagram> found")
    if diagram.tag == "mxGraphModel":
        return diagram
    inner = diagram.find("mxGraphModel")
    if inner is not None:
        return inner
    # Compressed form: base64 -> raw deflate -> URL-encoded XML.
    raw = (diagram.text or "").strip()
    data = zlib.decompress(base64.b64decode(raw), -15).decode()
    return ET.fromstring(urllib.parse.unquote(data))


def clean(label: str) -> str:
    """Reduce a draw.io HTML label to plain text; keep it as-is if stripping leaves nothing."""
    label = re.sub(r"<img[^>]*>", "[image]", label)
    label = re.sub(r"<br\s*/?>|</div>|</p>", " / ", label)
    stripped = re.sub(r"<[^>]+>", "", label).strip(" /")
    return html.unescape(stripped) or label.strip()


def main() -> None:
    model = diagram_xml(sys.argv[1])
    cells = {c.get("id"): c for c in model.iter("mxCell")}

    def label(cid: str) -> str:
        """Display name of a cell, or a placeholder when it has no text."""
        c = cells.get(cid)
        return (clean(c.get("value", "")) if c is not None else "") or f"(unlabeled {cid[-6:]})"

    def rect(c):
        """Absolute (x, y, w, h) of a cell. Child geometry is relative to its parent, so add parent offsets."""
        geo = c.find("mxGeometry")
        if geo is None or geo.get("width") is None:
            return None
        x, y = float(geo.get("x", 0)), float(geo.get("y", 0))
        parent = cells.get(c.get("parent"))
        while parent is not None and parent.get("vertex") == "1":
            pg = parent.find("mxGeometry")
            x, y = x + float(pg.get("x", 0)), y + float(pg.get("y", 0))
            parent = cells.get(parent.get("parent"))
        return x, y, float(geo.get("width")), float(geo.get("height"))

    # Shapes only: skip edge labels (children of edges) and cells without geometry.
    nodes = {
        cid: c for cid, c in cells.items()
        if c.get("vertex") == "1" and cells.get(c.get("parent")) is not None
        and cells[c.get("parent")].get("edge") != "1"
        and (c.get("value", "").strip() or c.find("mxGeometry") is not None and rect(c))
    }
    rects = {cid: rect(c) for cid, c in nodes.items()}

    def container(cid):
        """Smallest other shape that fully encloses this one. Containers are often not parents in the XML."""
        r = rects[cid]
        best = None
        for oid, o in rects.items():
            if oid == cid or r is None or o is None:
                continue
            if o[0] <= r[0] and o[1] <= r[1] and o[0] + o[2] >= r[0] + r[2] and o[1] + o[3] >= r[1] + r[3] \
                    and o[2] * o[3] > r[2] * r[3]:
                if best is None or o[2] * o[3] < rects[best][2] * rects[best][3]:
                    best = oid
        return best

    children = {}
    for cid in nodes:
        children.setdefault(container(cid), []).append(cid)

    def show(cid) -> bool:
        """Print labeled shapes, and unlabeled ones only when they enclose something."""
        return bool(clean(nodes[cid].get("value", ""))) or cid in children

    def walk(parent, level):
        """Print the containment tree, top-to-bottom then left-to-right."""
        for cid in sorted(children.get(parent, []), key=lambda i: (rects[i][1], rects[i][0]) if rects[i] else (0, 0)):
            if show(cid):
                text = clean(nodes[cid].get("value", "")) or "(unlabeled box)"
                print("  " * level + f"- {text} [{cid[-6:]}]")
                walk(cid, level + 1)

    print("NODES (indent = visually contained in the node above; [id] disambiguates same-named nodes)")
    walk(None, 0)

    print("\nEDGES (source -> target [label])")
    for cid, c in cells.items():
        if c.get("edge") == "1":
            src, dst = c.get("source"), c.get("target")
            if not src or not dst:
                continue
            text = " ".join(
                clean(o.get("value", ""))
                for o in cells.values()
                if o.get("parent") == cid and o.get("value")
            ) or clean(c.get("value", ""))
            # An arrowhead at both ends means a two-way edge.
            both = "startArrow=" in c.get("style", "") and "startArrow=none" not in c.get("style", "")
            arrow = "<->" if both else "->"
            print(f"  {label(src)} [{src[-6:]}] {arrow} {label(dst)} [{dst[-6:]}]" + (f"  [{text}]" if text else ""))


if __name__ == "__main__":
    main()

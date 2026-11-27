"""Open .docx parts, read styles and relationships, stream the body.

The body of ``word/document.xml`` is streamed with ``lxml.etree.iterparse``:
each direct child of ``w:body`` is handed out once and freed afterwards, so
documents of 50+ MB (TS 38.331, TS 24.501) do not have to be held in memory
as one tree. Only the package parts (styles, relationships, media) are read
whole.
"""
import os
import posixpath
import re
import zipfile

from lxml import etree

from .headings import outline_level
from .ns import PKG_REL, W

PART_RE = re.compile(r"^(\d{5}(?:-\d+)?-[0-9a-z]\d{2})_(.+)$")
NUM_PART_RE = re.compile(r"^(\d{5}(?:-\d+)?-[0-9a-z]\d{2}_)(\d+)(?=_)")  # '_10_s...' part prefix
CODE_RE = re.compile(r"^(\d{2})(\d{3})(-\d+)?-([0-9a-z])([0-9a-z])([0-9a-z])$")
COVER_VERSION_RE = re.compile(r"3GPP\s+(T[SR])\s+(\d+\.\d+(?:-\d+)?)\s+V(\d+)\.(\d+)\.(\d+)")


def basename(path):
    return path.replace("\\", "/").split("/")[-1]


def part_sort_key(path):
    """File-name sort key; a numeric part prefix ('38133-j60_10_sA06...') sorts as a number."""
    return NUM_PART_RE.sub(lambda m: m.group(1) + m.group(2).zfill(9), basename(path))


def stem(path):
    return os.path.splitext(basename(path))[0]


def split_name(path):
    """'36101-j60_s08-XX.docx' -> ('36101-j60', 's08-XX'); single file -> (stem, None)."""
    s = stem(path)
    m = PART_RE.match(s)
    if m:
        return m.group(1), m.group(2)
    return s, None


def spec_code(path):
    return split_name(path)[0]


def _vchar(c):
    return int(c) if c.isdigit() else ord(c) - ord("a") + 10


def version_from_code(code):
    """'38331-i10' -> ('38.331', '18.1.0'); '38101-1-j70' -> ('38.101-1', '19.7.0')."""
    m = CODE_RE.match(code)
    if not m:
        return None, None
    number = f"{m.group(1)}.{m.group(2)}{m.group(3) or ''}"
    version = ".".join(str(_vchar(c)) for c in m.group(4, 5, 6))
    return number, version


def load_styles(z):
    """Return (styles, char_vert_align, style_numbering).

    styles: styleId -> (name, outline level or None), same as inspect_docx.load_styles.
    char_vert_align: character styleId -> 'superscript' / 'subscript'.
    style_numbering: paragraph styleId -> (numId, ilvl) for styles with w:numPr.
    """
    styles = {}
    try:
        root = etree.fromstring(z.read("word/styles.xml"), etree.XMLParser(huge_tree=True))
    except KeyError:
        return styles, {}, {}
    char_va = {}
    style_num = {}
    for s in root.iter(W + "style"):
        sid = s.get(W + "styleId")
        name_el = s.find(W + "name")
        name = name_el.get(W + "val") if name_el is not None else sid
        lvl = None
        ppr = s.find(W + "pPr")
        if ppr is not None:
            ol = ppr.find(W + "outlineLvl")
            if ol is not None:
                lvl = outline_level(ol)
            num = ppr.find(W + "numPr")
            if num is not None:
                nid = num.find(W + "numId")
                il = num.find(W + "ilvl")
                style_num[sid] = (nid.get(W + "val") if nid is not None else None,
                                  il.get(W + "val") if il is not None else None)
        styles[sid] = (name, lvl)
        if s.get(W + "type") == "character":
            va = s.find(W + "rPr/" + W + "vertAlign")
            if va is not None:
                char_va[sid] = va.get(W + "val")
    return styles, char_va, style_num


def load_rels(z):
    """rId -> (zip member path or URL, external?)."""
    rels = {}
    try:
        root = etree.fromstring(z.read("word/_rels/document.xml.rels"))
    except KeyError:
        return rels
    for r in root.iter(PKG_REL + "Relationship"):
        target = r.get("Target") or ""
        if r.get("TargetMode") == "External":
            rels[r.get("Id")] = (target, True)
            continue
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            path = posixpath.normpath(posixpath.join("word", target))
        rels[r.get("Id")] = (path, False)
    return rels


class Part:
    """One .docx file (a whole spec, or one part of a multi-part spec)."""

    def __init__(self, path):
        self.path = path
        self.name = basename(path)
        self.code, self.part = split_name(path)
        self.zip = zipfile.ZipFile(path)
        self.styles, self.char_vert_align, self.style_numbering = load_styles(self.zip)
        self.rels = load_rels(self.zip)
        self.members = set(self.zip.namelist())

    def close(self):
        self.zip.close()

    def style_name(self, sid):
        if not sid:
            return "Normal"
        return self.styles.get(sid, (sid, None))[0] or sid

    def iter_body(self):
        """Yield the direct children of w:body in document order, freeing each one after use."""
        depth = 0
        with self.zip.open("word/document.xml") as f:
            for event, el in etree.iterparse(f, events=("start", "end"), huge_tree=True,
                                             remove_comments=True, remove_pis=True):
                if event == "start":
                    depth += 1
                    continue
                depth -= 1
                if depth != 2:
                    continue
                yield el
                el.clear()
                parent = el.getparent()
                if parent is not None:
                    while el.getprevious() is not None:
                        del parent[0]


def para_plain_text(p):
    return "".join(t.text or "" for t in p.iter(W + "t"))


def find_cover_version(part, max_elements=4000):
    """Search the cover (before the first heading) for '3GPP TS 38.331 V18.1.0'.

    Returns (kind 'TS'/'TR', number, version) or None. ZA paragraphs are
    preferred, any paragraph text is accepted as fallback.
    """
    from .headings import para_style  # local import to avoid a cycle at module load
    fallback = None
    for i, el in enumerate(part.iter_body()):
        if i > max_elements:
            break
        paras = [el] if el.tag == W + "p" else list(el.iter(W + "p"))
        for p in paras:
            name, lvl = para_style(p, part.styles)
            if el.tag == W + "p" and lvl and "".join(t.text or "" for t in p.iter(W + "t")).strip():
                return fallback
            text = para_plain_text(p)
            m = COVER_VERSION_RE.search(text)
            if m:
                found = (m.group(1), m.group(2), f"{int(m.group(3))}.{int(m.group(4))}.{int(m.group(5))}")
                if name == "ZA":
                    return found
                fallback = fallback or found
    return fallback

"""Heading interpretation (output-contract.md section 3).

This is a port of the reference implementation in
``skills/3gpp-docx-structure/scripts/inspect_docx.py`` (``para_style``,
``parse_clause``, ``clause_level``, ``clause_parent``, ``norm_heading``,
``para_text``). The checker compares our manifest with that script's outline,
so these functions must give identical results; ``tests/test_headings.py``
checks them against the script directly.
"""
import re

from .ns import M, W

HEADING_RE = re.compile(r"^(?:heading\s*|h)(\d)$", re.I)
CLAUSE_RE = re.compile(
    r"^\s*((?:[A-Z]{1,2}|\d+[A-Za-z]{0,2}\d*)(?:\.(?:\d+[A-Za-z]{0,2}\d*|[A-Z]))*)\.?[\s ]+(.+)$")
ANNEX_RE = re.compile(r"^\s*Annex\s+([A-Z]{1,2})\b\s*(.*)$", re.I)
# typo in the source number "5. 2.2.4.2.3<TAB>Title" (space after the first dot) -> "5.2.2.4.2.3"
SPLIT_NUM_RE = re.compile(r"^(\d+[A-Za-z]{0,2}\d*)\.\s+(\d+[A-Za-z]{0,2}\d*(?:\.\d+[A-Za-z]{0,2}\d*)+)(?=\t)")


def outline_level(ol):
    """w:outlineLvl val 0-8 -> level 1-9; val 9 means 'body text' (no level)."""
    try:
        v = int(ol.get(W + "val"))
    except (TypeError, ValueError):
        return None
    return v + 1 if v < 9 else None


def norm_heading(text):
    """Heading text with line breaks folded to one space (titles are one line)."""
    return re.sub(r"[ \t]*\n\s*", " ", text.strip())


def heading_text(p):
    """Plain text of a heading paragraph, exactly as inspect_docx.para_text builds it."""
    parts = []
    for el in p.iter():
        tag = el.tag
        if tag in (W + "t", M + "t") and el.text:
            parts.append(el.text)
        elif tag == W + "tab":
            parts.append("\t")
        elif tag in (W + "br", W + "cr"):
            parts.append("\n")
    return "".join(parts)


def para_style(p, styles):
    """Return (style name, outline level or None) for a paragraph.

    ``styles`` maps styleId -> (name, outline level or None).
    """
    ppr = p.find(W + "pPr")
    sid = None
    if ppr is not None:
        ps = ppr.find(W + "pStyle")
        if ps is not None:
            sid = ps.get(W + "val")
    name, lvl = styles.get(sid, (sid or "Normal", None)) if sid else ("Normal", None)
    if ppr is not None:
        ol = ppr.find(W + "outlineLvl")
        if ol is not None:
            lvl = outline_level(ol)
    m = HEADING_RE.match(name or "")
    if m:
        lvl = int(m.group(1))
    return name, lvl


def parse_clause(text):
    """Return (clause_id, title) from heading text. Unnumbered -> (None, title)."""
    t = SPLIT_NUM_RE.sub(r"\1.\2", norm_heading(text))
    a = ANNEX_RE.match(t)
    if a:
        title = re.sub(r"^\(?(normative|informative)\)?\s*:?\s*", "", a.group(2).strip(), flags=re.I)
        return a.group(1).upper(), title.strip() or t
    m = CLAUSE_RE.match(t)
    if m and (m.group(1)[0].isdigit() or "." in m.group(1)):
        return m.group(1), m.group(2).strip()
    # 38.331 IE/field headings "-<TAB>RRCReconfiguration": the dash is a list marker
    return None, re.sub(r"^[–\-]\s+", "", t)


def is_annex(text):
    return ANNEX_RE.match(norm_heading(text)) is not None


def clause_level(clause, style_level):
    """Numbered clause -> number depth (A.1 -> 2); unnumbered -> style level."""
    return clause.count(".") + 1 if clause else style_level


def clause_parent(clause):
    return clause.rsplit(".", 1)[0] if clause and "." in clause else None


def slugify(s):
    """Same as check_output.slugify: lowercase, non-alnum runs -> '-', trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


class Heading:
    """A heading paragraph interpreted per the contract."""

    __slots__ = ("clause", "title", "level", "style", "style_level", "annex", "display", "key",
                 "parent", "path", "source_file", "equations")

    def __init__(self, text, style, style_level, source_file):
        clause, title = parse_clause(text)
        self.annex = is_annex(text)
        self.clause = clause
        self.title = title
        self.style = style
        self.style_level = style_level
        self.level = 1 if self.annex else clause_level(clause, style_level)
        self.key = clause or slugify(title)
        self.source_file = source_file
        one_title = re.sub(r"[ \t]+", " ", title).strip()
        if self.annex:
            self.display = re.sub(r"[ \t]+", " ", norm_heading(text)).strip()
        elif clause:
            self.display = clause + " " + one_title
        else:
            self.display = one_title
        self.title = one_title
        self.parent = None
        self.path = []
        self.equations = 0

    @property
    def label(self):
        return self.display

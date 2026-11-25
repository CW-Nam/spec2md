"""Body elements (paragraphs, tables) -> Markdown blocks (output-contract.md section 5).

``Renderer`` turns one ``w:p`` into inline "pieces" (text with sub/superscript,
inline/display math, images) and then into Markdown, HTML-cell or pipe-cell
text. Paragraph styles decide the block form (list, NOTE, definition, caption,
code line). Tables become GFM pipe tables when nothing would be lost, HTML
otherwise.
"""
import html
import posixpath
import re
import struct
from collections import Counter

from .ns import A, MC, M, O, R, V, W, local
from . import mtef
from .omml import OmmlConverter
from .symbols import font_kind, is_pua, map_char

SEP = "\x00SEP\x00"
SEP_RE = re.compile(r"(?:[ \t]*\x00SEP\x00[ \t]*)+")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
LIST_RE = re.compile(r"^b([1-9])$")
COVER_RE = re.compile(r"^z[a-z]$")
NOTE_STYLES = {"no", "nf", "nw", "tan", "editor's note"}
DEF_STYLES = {"ex", "ew"}
PLAIN_STYLES = {"normal", "tal", "tac", "tah", "tar", "fp", "h6", "th", "tf", "eq", "pl"}
# run-level wrappers whose content is part of the paragraph
WRAPPERS = {"hyperlink", "smartTag", "customXml", "fldSimple", "ins", "moveTo", "dir", "bdo",
            "ruby", "rubyBase"}
SKIP_TAGS = {"pPr", "rPr", "bookmarkStart", "bookmarkEnd", "proofErr", "permStart", "permEnd",
             "commentRangeStart", "commentRangeEnd", "commentReference", "annotationRef",
             "lastRenderedPageBreak", "fldChar", "instrText", "delText", "del", "moveFrom",
             "moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
             "separator", "continuationSeparator", "footnoteRef", "endnoteRef", "dayShort",
             "monthShort", "yearShort", "dayLong", "monthLong", "yearLong", "pgNum",
             "customXmlInsRangeStart", "customXmlInsRangeEnd", "customXmlDelRangeStart",
             "customXmlDelRangeEnd", "rubyPr", "rt", "sectPr", "contentPart", "smartTagPr",
             "customXmlPr", "sdtPr", "sdtEndPr", "attr"}


def style_kind(name):
    n = (name or "").strip().lower()
    if n.startswith("toc") or n == "tt":
        return "toc"
    if COVER_RE.match(n):
        return "cover"
    if n == "pl":
        return "pl"
    m = LIST_RE.match(n)
    if m:
        return "list"
    if n in NOTE_STYLES or n.startswith("editor"):
        return "note"
    if n in DEF_STYLES:
        return "def"
    if n == "th":
        return "th"
    if n == "tf":
        return "tf"
    if n == "eq":
        return "eq"
    if n in PLAIN_STYLES or re.match(r"^heading\s*\d$", n):
        return "plain"
    return "unknown"


def _on(el):
    """w:b / w:vanish style boolean: present and not val=0/false/off."""
    if el is None:
        return False
    v = el.get(W + "val")
    return v is None or v.lower() not in ("0", "false", "off")


def clean_text(s, stats):
    if CTRL_RE.search(s):
        s = CTRL_RE.sub("", s)
    if "\ufffd" in s:
        stats["U+FFFD replacement character"] += 1
        s = s.replace("\ufffd", "?")
    return s


class Inline:
    """Rendered pieces of one paragraph plus element counts."""

    __slots__ = ("pieces", "figures", "equations", "rids")

    def __init__(self):
        # [kind, value, vertAlign]; kinds: t text, x text placeholder (footnote ref),
        # m inline math (latex, lead space, trail space), D display math,
        # i image (src, alt), g drawing placeholder "[drawing: ...]"
        self.pieces = []
        self.figures = 0
        self.equations = 0
        self.rids = set()  # image relationships already output in this paragraph

    def has_text(self):
        return any(k in ("t", "x") and v.strip() for k, v, _ in self.pieces)

    def has_image(self):
        return any(k in ("i", "g") for k, _, _ in self.pieces)

    def has_math(self):
        return any(k in ("m", "D") for k, _, _ in self.pieces)


class MediaStore:
    """Copies images from the docx parts into {out}/media once each."""

    def __init__(self, media_dir):
        self.media_dir = media_dir
        self.done = {}

    def link(self, part, rel_id):
        """Return the link target ('../media/x.wmf' or URL) for a relationship, or None."""
        if not rel_id or rel_id not in part.rels:
            return None
        target, external = part.rels[rel_id]
        if external:
            return target
        key = (part.name, target)
        if key in self.done:
            return self.done[key]
        if target not in part.members:
            self.done[key] = None
            return None
        name = posixpath.basename(target)
        if part.part:
            name = f"{part.part}_{name}"
        import os
        os.makedirs(self.media_dir, exist_ok=True)
        with open(os.path.join(self.media_dir, name), "wb") as f:
            f.write(part.zip.read(target))
        self.done[key] = "../media/" + name
        return self.done[key]


class Renderer:
    def __init__(self, media):
        self.media = media
        self.part = None
        self.omml = OmmlConverter()
        self.unhandled_elements = Counter()
        self.unhandled_styles = Counter()
        self.unmapped_symbols = Counter()
        self.notes = Counter()
        self.ole_stats = Counter({"latex": 0, "image_only": 0})
        self.ole_failures = Counter()

    # ------------------------------------------------------------------
    # inline walk
    # ------------------------------------------------------------------
    def inline(self, p):
        res = Inline()
        self._walk(p, res, None, None)
        return res

    def _walk(self, el, res, va, font):
        for c in el:
            tag = c.tag
            if not isinstance(tag, str):
                continue
            if tag == W + "r":
                self._run(c, res)
            elif tag == M + "oMathPara":
                for om in c.findall(M + "oMath"):
                    latex = self.omml.convert(om)
                    if latex:  # an equation with no content produces no "$$ $$"
                        res.pieces.append(["D", (latex, None), None])
                    res.equations += 1
            elif tag == M + "oMath":
                self._math(c, res)
            elif tag == W + "sdt":
                content = c.find(W + "sdtContent")
                if content is not None:
                    self._walk(content, res, va, font)
            elif tag == MC + "AlternateContent":
                self._alternate(c, res, lambda node, r: self._walk(node, r, va, font))
            else:
                name = local(tag)
                if tag.startswith(W) and name in WRAPPERS:
                    self._walk(c, res, va, font)
                elif tag.startswith(W) and name in SKIP_TAGS:
                    continue
                else:
                    self.unhandled_elements[_qname(tag)] += 1
                    self._walk(c, res, va, font)

    def _math(self, om, res):
        """Inline m:oMath. Spaces at the edges of the math text go outside the $...$."""
        text = "".join(t.text or "" for t in om.iter(M + "t"))
        lead, trail = text[:1].isspace(), text[-1:].isspace()
        latex = self.omml.convert(om)
        if latex:
            res.pieces.append(["m", (latex, lead, trail, None), None])
        elif lead or trail:
            res.pieces.append(["t", " ", None])
        res.equations += 1

    def _alternate(self, ac, res, walk):
        """mc:AlternateContent: only mc:Choice is read; mc:Fallback repeats the same
        content in an older format (VML) and would output it twice."""
        choice = ac.find(MC + "Choice")
        if choice is None:
            choice = ac.find(MC + "Fallback")
        if choice is not None:
            walk(choice, res)

    def _run(self, r, res):
        rpr = r.find(W + "rPr")
        va = None
        font = None
        if rpr is not None:
            if _on(rpr.find(W + "vanish")) or _on(rpr.find(W + "webHidden")):
                return
            v = rpr.find(W + "vertAlign")
            if v is not None:
                va = v.get(W + "val")
            else:
                rs = rpr.find(W + "rStyle")
                if rs is not None:
                    va = self.part.char_vert_align.get(rs.get(W + "val"))
            rf = rpr.find(W + "rFonts")
            if rf is not None:
                font = font_kind(rf.get(W + "ascii") or rf.get(W + "hAnsi") or rf.get(W + "cs"))
        if va not in ("superscript", "subscript"):
            va = None
        for c in r:
            tag = c.tag
            if not isinstance(tag, str):
                continue
            if tag == W + "t":
                if c.text:
                    res.pieces.append(["t", self._sym_text(c.text, font), va])
            elif tag in (W + "tab", W + "ptab"):
                res.pieces.append(["t", "\t", None])
            elif tag == W + "br":
                if c.get(W + "type") not in ("page", "column"):
                    res.pieces.append(["t", "\n", None])
            elif tag == W + "cr":
                res.pieces.append(["t", "\n", None])
            elif tag == W + "sym":
                res.pieces.append(["t", self._sym(c), va])
            elif tag == W + "noBreakHyphen":
                res.pieces.append(["t", "-", va])
            elif tag == W + "softHyphen":
                continue
            elif tag == W + "drawing":
                self._drawing(c, res)
            elif tag == W + "pict":
                self._pict(c, res)
            elif tag == W + "object":
                self._object(c, res)
            elif tag == MC + "AlternateContent":
                self._alternate(c, res, lambda node, rr: self._run_like(node, rr))
            elif tag in (W + "footnoteReference", W + "endnoteReference"):
                res.pieces.append(["x", f"[{local(tag)} {c.get(W + 'id')}]", None])
                self.unhandled_elements["w:" + local(tag)] += 1
            elif tag == M + "oMath":
                self._math(c, res)
            elif tag.startswith(W) and local(tag) in SKIP_TAGS:
                continue
            else:
                self.unhandled_elements[_qname(tag)] += 1
                for t in c.iter(W + "t"):
                    if t.text:
                        res.pieces.append(["t", self._sym_text(t.text, font), va])

    def _run_like(self, node, res):
        """Children of mc:Choice/Fallback inside a run (w:drawing, w:pict, ...)."""
        fake = _FakeRun(list(node))
        self._run(fake, res)

    def _sym_text(self, text, font):
        if font or any(is_pua(ch) for ch in text):
            out = []
            for ch in text:
                code = ord(ch)
                if font or 0xF000 <= code <= 0xF0FF:
                    m = map_char(code, font or "symbol")
                    if m is not None:
                        out.append(m)
                        continue
                if is_pua(ch):
                    self.unmapped_symbols[f"U+{code:04X}"] += 1
                out.append(ch)
            text = "".join(out)
        return text

    def _sym(self, el):
        ch = el.get(W + "char") or ""
        kind = font_kind(el.get(W + "font")) or "symbol"
        try:
            code = int(ch, 16)
        except ValueError:
            self.unmapped_symbols["w:sym " + ch] += 1
            return ""
        m = map_char(code, kind)
        if m is None:
            self.unmapped_symbols[f"w:sym {el.get(W + 'font')} {ch}"] += 1
            return chr(code)
        return m

    # -- figures / objects --------------------------------------------
    def _image(self, res, rel_id, alt):
        src = self.media.link(self.part, rel_id)
        if not src:
            return False
        if src not in res.rids:  # same image twice in one paragraph (grouped shapes) -> once
            res.rids.add(src)
            res.pieces.append(["i", (src, alt), None])
        return True

    def _textbox_text(self, el):
        """Text of text boxes in a drawing, one entry per paragraph, mc:Fallback skipped."""
        by_para = {}
        for t in el.iter(W + "t"):
            if not t.text or _in_fallback(t, el):
                continue
            node = t.getparent()
            while node is not None and node.tag != W + "p":
                node = node.getparent()
            by_para.setdefault(node, []).append(t.text)
        texts = ["".join(v).strip() for v in by_para.values()]
        return " / ".join(t for t in texts if t)

    def _drawing(self, d, res):
        res.figures += 1
        found = False
        for blip in d.iter(A + "blip"):
            if _in_fallback(blip, d):
                continue
            rid = blip.get(R + "embed") or blip.get(R + "link")
            found = self._image(res, rid, "Figure") or found
        if not found:
            t = self._textbox_text(d)
            res.pieces.append(["g", f"[drawing: {t}]" if t else "[drawing]", None])

    def _pict(self, pict, res):
        res.figures += 1
        found = False
        for im in pict.iter(V + "imagedata"):
            if _in_fallback(im, pict):
                continue
            rid = im.get(R + "id") or im.get(O + "relid")
            found = self._image(res, rid, "Figure") or found
        if not found:
            t = self._textbox_text(pict)
            res.pieces.append(["g", f"[drawing: {t}]" if t else "[drawing]", None])

    def _object(self, obj, res):
        ole = obj.find(".//" + O + "OLEObject")
        prog = ole.get("ProgID") if ole is not None else None
        if prog is None:
            emb = obj.find(".//" + W + "objectEmbed")
            if emb is not None:
                prog = emb.get(W + "progId")
        prog = prog or "unknown"
        is_eq = prog.startswith("Equation")
        alt = "equation" if is_eq else "Figure"
        if is_eq:
            res.equations += 1
            latex = self._ole_latex(ole)
            if latex is not None:
                preview = None
                for im in obj.iter(V + "imagedata"):
                    preview = self.media.link(self.part, im.get(R + "id") or im.get(O + "relid"))
                    if preview:
                        break
                res.pieces.append(["m", (latex, False, False, preview), None])
                self.ole_stats["latex"] += 1
                return
            self.ole_stats["image_only"] += 1
        else:
            res.figures += 1
        found = False
        for im in obj.iter(V + "imagedata"):
            rid = im.get(R + "id") or im.get(O + "relid")
            found = self._image(res, rid, alt) or found
        if not found:
            for blip in obj.iter(A + "blip"):
                found = self._image(res, blip.get(R + "embed") or blip.get(R + "link"), alt) or found
        if not found:
            res.pieces.append(["g", f"[embedded object: {prog}]", None])

    def _ole_latex(self, ole):
        """o:OLEObject -> LaTeX from its 'Equation Native' stream, or None (reason counted)."""
        rid = ole.get(R + "id") if ole is not None else None
        target = self.part.rels.get(rid) if rid else None
        if not target or target[1] or target[0] not in self.part.members:
            self.ole_failures["no embedded object"] += 1
            return None
        try:
            return mtef.to_latex(mtef.read_equation_native(self.part.zip.read(target[0])))
        except mtef.MtefError as e:
            self.ole_failures[str(e)] += 1
        except (IndexError, ValueError, struct.error) as e:  # malformed stream
            self.ole_failures["malformed: " + type(e).__name__] += 1
        return None

    # ------------------------------------------------------------------
    # pieces -> text
    # ------------------------------------------------------------------
    def finish(self, res, mode, display=False):
        """Render pieces. mode: md | html | pipe | code. Returns a string.

        In md mode with display=True, display math (oMathPara, or a paragraph
        that holds nothing but equations) becomes ``$$...$$`` blocks separated
        from the surrounding text by blank lines. Drawing placeholders go on a
        line of their own. Adjacent inline equations are separated by one
        space, and spaces at the edges of the math text are put outside ``$``.
        """
        pieces = res.pieces
        if display and mode == "md":
            only_math = res.has_math() and not res.has_text() and not res.has_image()
            if only_math:
                pieces = [["D", (v[0], v[3]), None] if k == "m" else [k, v, a] for k, v, a in pieces]
        else:
            pieces = [["m", (v[0], False, False, v[1]), None] if k == "D" else [k, v, a] for k, v, a in pieces]
        out = []
        buf = []  # pending text pieces [(text, va)]
        state = {"space": False, "math": False}  # space owed after math; last piece was math

        def emit(text, is_math=False):
            if not text:
                return
            owed = state["space"] or (is_math and state["math"])
            # a letter or digit glued to an inline equation gets one space (not before punctuation)
            owed = owed or (state["math"] and _first_visible(text).isalnum()) \
                or (is_math and out and _last_visible(out[-1]).isalnum())
            if owed and out and not out[-1][-1:].isspace() and not text[:1].isspace():
                out.append(" ")
            state["space"] = False
            state["math"] = is_math
            out.append(text)

        def flush():
            if not buf:
                return
            merged = []
            for t, a in buf:
                if merged and merged[-1][1] == a:
                    merged[-1][0] += t
                else:
                    merged.append([t, a])
            for t, a in merged:
                t = clean_text(t, self.notes)
                t = self._esc(t, mode)
                if a and mode != "code" and t.strip():
                    tagname = "sup" if a == "superscript" else "sub"
                    t = f"<{tagname}>{t}</{tagname}>"
                emit(t)
            buf.clear()
        for kind, val, va in pieces:
            if kind == "t":
                buf.append((val, va))
                continue
            flush()
            if kind == "x":
                emit(self._esc(val, mode))
            elif kind == "m":
                latex, lead, trail, note = val
                if lead and out and not out[-1][-1:].isspace():
                    out.append(" ")
                emit("$" + self._esc_math(latex, mode) + "$" + _ole_note(note), is_math=True)
                state["space"] = trail
            elif kind == "D":
                latex, note = val
                out.append("\n\n$$\n" + latex + "\n$$\n" + (_ole_note(note) + "\n" if note else "") + "\n")
                state.update(space=False, math=False)
            elif kind == "g":
                out.append(SEP + self._esc(val, mode) + SEP)
                state.update(space=False, math=False)
            elif kind == "i":
                src, alt = val
                if mode in ("html", "pipe"):
                    emit(f'<img src="{html.escape(src, quote=True)}" alt="{alt}">')
                else:
                    emit(f"![{alt}]({src})")
        flush()
        text = "".join(out)
        if SEP in text:
            nl = "<br>" if mode in ("html", "pipe") else "\n"
            text = SEP_RE.sub(SEP, text).strip()
            while text.startswith(SEP) or text.endswith(SEP):
                text = text[len(SEP):] if text.startswith(SEP) else text[:-len(SEP)]
                text = text.strip()
            text = SEP_RE.sub(nl, text)
        return text

    def finish_caption(self, res, mark):
        """TH/TF: caption text wrapped in ``mark``; figures and drawing placeholders
        on their own lines, in document order, never inside the caption markup."""
        groups = []
        for piece in res.pieces:
            fig = piece[0] in ("i", "g")
            if groups and groups[-1][0] == fig:
                groups[-1][1].append(piece)
            else:
                groups.append((fig, [piece]))
        out = []
        for fig, pieces in groups:
            tmp = Inline()
            tmp.pieces = pieces
            text = collapse_tabs(self.finish(tmp, "md")).strip()
            if not text:
                continue
            if fig:
                out.append(text)
            else:
                out.append(mark + " ".join(line.strip() for line in text.split("\n")) + mark)
        return "\n\n".join(out)

    @staticmethod
    def _esc(t, mode):
        if mode == "html":
            return html.escape(t, quote=False).replace("\n", "<br>").replace("\t", " ")
        if mode == "pipe":
            return t.replace("|", "\\|").replace("\n", "<br>").replace("\t", " ")
        return t

    @staticmethod
    def _esc_math(t, mode):
        if mode == "html":
            return html.escape(t, quote=False)
        if mode == "pipe":
            return t.replace("|", "\\|")
        return t


class _FakeRun:
    """Minimal run-like wrapper so that mc:Choice children can go through Renderer._run."""

    def __init__(self, children):
        self._children = children

    def find(self, _):
        return None

    def __iter__(self):
        return iter(self._children)


TAG_EDGE_RE = re.compile(r"^(?:<su[bp]>)+|(?:</su[bp]>)+$")


def _first_visible(text):
    """First character of rendered text, looking past <sub>/<sup> tags."""
    return TAG_EDGE_RE.sub("", text)[:1]


def _last_visible(text):
    return TAG_EDGE_RE.sub("", text)[-1:]


def _ole_note(src):
    return f"<!-- ole-equation: {src} -->" if src else ""


def _in_fallback(node, stop):
    """True if node sits inside an mc:Fallback below ``stop``."""
    n = node.getparent()
    while n is not None and n is not stop:
        if n.tag == MC + "Fallback":
            return True
        n = n.getparent()
    return False


def _qname(tag):
    for prefix, ns in (("w", W), ("m", M), ("mc", MC), ("v", V), ("o", O), ("a", A)):
        if tag.startswith(ns):
            return prefix + ":" + tag[len(ns):]
    return tag


# ----------------------------------------------------------------------
# paragraph blocks
# ----------------------------------------------------------------------
def collapse_tabs(s):
    return re.sub(r"\t+", " ", s)


def numbering_level(p, part):
    """ilvl of an automatically numbered paragraph (w:numPr, direct or from its style), else None.

    numId 0 means "numbering removed".
    """
    ppr = p.find(W + "pPr")
    sid = None
    num = None
    if ppr is not None:
        ps = ppr.find(W + "pStyle")
        sid = ps.get(W + "val") if ps is not None else None
        num = ppr.find(W + "numPr")
    nid, ilvl = part.style_numbering.get(sid, (None, None)) if sid else (None, None)
    if num is not None:
        n = num.find(W + "numId")
        i = num.find(W + "ilvl")
        if n is not None:
            nid = n.get(W + "val")
        if i is not None:
            ilvl = i.get(W + "val")
    if nid in (None, "", "0"):
        return None
    try:
        return int(ilvl or 0)
    except ValueError:
        return 0


def _bullet(text, pad):
    """'- ' marker for an auto-numbered paragraph; continuation lines aligned under the text."""
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join((pad + "- " if i == 0 else pad + "  ") + ln for i, ln in enumerate(lines))


def paragraph_block(renderer, p, style_name):
    """Body-level paragraph -> (kind, text, Inline). kind: 'md' | 'code' | 'skip'.

    'code' text is one PL line (may contain newlines from w:br); consecutive
    code lines are grouped into one fenced block by the caller.
    """
    kind = style_kind(style_name)
    res = renderer.inline(p)
    if kind == "pl":
        return "code", renderer.finish(res, "code"), res
    if kind == "unknown":
        renderer.unhandled_styles[style_name] += 1
    numbered = numbering_level(p, renderer.part) if kind in ("list", "plain", "unknown") else None
    if kind == "list":
        n = int(LIST_RE.match(style_name.strip().lower()).group(1))
        text = collapse_tabs(renderer.finish(res, "md")).strip()
        if not text:
            return "skip", "", res
        pad = " " * ((n - 1) * 2)
        if numbered is not None:
            return "md", _bullet(text, pad), res
        return "md", "\n".join(pad + line.strip() for line in text.split("\n")), res
    if numbered is not None:
        text = collapse_tabs(renderer.finish(res, "md")).strip()
        if not text:
            return "skip", "", res
        return "md", _bullet(text, " " * (numbered * 2)), res
    if kind == "note":
        text = collapse_tabs(renderer.finish(res, "md")).strip()
        if not text:
            return "skip", "", res
        return "md", "\n".join("> " + line.strip() if line.strip() else ">" for line in text.split("\n")), res
    if kind == "def":
        raw = renderer.finish(res, "md").strip()
        if not raw:
            return "skip", "", res
        if "\t" in raw:
            term, _, rest = raw.partition("\t")
            term, rest = term.strip(), collapse_tabs(rest).strip()
            if term and rest:
                return "md", f"- **{term}**: {rest}", res
            raw = (term or rest)
        return "md", f"- **{collapse_tabs(raw).strip()}**", res
    if kind in ("th", "tf"):
        text = renderer.finish_caption(res, "**" if kind == "th" else "*")
        if not text:
            return "skip", "", res
        return "md", text, res
    if kind == "eq":
        text = renderer.finish(res, "md", display=True)
        text = "\n".join(line.replace("\t", " ").strip() for line in text.split("\n"))
        return _md_or_skip(text, res)
    # plain / unknown / heading-styled body text
    text = renderer.finish(res, "md", display=True)
    text = "\n".join(collapse_tabs(line).rstrip() for line in text.split("\n"))
    return _md_or_skip(text, res)


def _md_or_skip(text, res):
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return "skip", "", res
    return "md", text, res


# ----------------------------------------------------------------------
# tables
# ----------------------------------------------------------------------
def _int(el, default=0):
    if el is None:
        return default
    try:
        return int(el.get(W + "val"))
    except (TypeError, ValueError):
        return default


def _unwrap(el, tag):
    """Children with the given tag, looking through w:sdt / w:customXml wrappers."""
    for c in el:
        if c.tag == tag:
            yield c
        elif c.tag == W + "sdt":
            content = c.find(W + "sdtContent")
            if content is not None:
                yield from _unwrap(content, tag)
        elif c.tag == W + "customXml":
            yield from _unwrap(c, tag)


def needs_html(tbl, part):
    for el in tbl.iter():
        tag = el.tag
        if tag == W + "gridSpan" and _int(el, 1) > 1:
            return True
        if tag in (W + "vMerge", W + "hMerge"):
            return True
        if tag in (W + "gridBefore", W + "gridAfter") and _int(el) > 0:
            return True
        if tag == W + "tbl" and el is not tbl:
            return True
        if tag in (W + "drawing", W + "pict", W + "object"):
            return True
        if tag == W + "pStyle" and style_kind(part.style_name(el.get(W + "val"))) == "pl":
            return True
    return False


class TableResult:
    __slots__ = ("text", "figures", "equations")

    def __init__(self):
        self.text = ""
        self.figures = 0
        self.equations = 0


def _p_style(p, part):
    ppr = p.find(W + "pPr")
    ps = ppr.find(W + "pStyle") if ppr is not None else None
    return part.style_name(ps.get(W + "val") if ps is not None else None)


def _cell(renderer, tc, mode, acc):
    """Cell content -> (text, is_header)."""
    parts = []
    pre = []
    styles = []

    def flush_pre():
        if pre:
            parts.append("<pre>" + "<br>".join(pre) + "</pre>")
            pre.clear()
    for c in tc:
        if c.tag == W + "sdt":
            content = c.find(W + "sdtContent")
            children = list(content) if content is not None else []
        elif c.tag == W + "customXml":
            children = list(c)
        else:
            children = [c]
        for el in children:
            if el.tag == W + "p":
                sname = _p_style(el, renderer.part)
                res = renderer.inline(el)
                acc.figures += res.figures
                acc.equations += res.equations
                if style_kind(sname) == "pl" and mode == "html":
                    line = renderer.finish(res, "code")
                    pre.append(html.escape(line, quote=False).replace("\n", "<br>"))
                    continue
                flush_pre()
                t = renderer.finish(res, mode).strip()
                if t and numbering_level(el, renderer.part) is not None:
                    t = "- " + t
                if t:
                    parts.append(t)
                    styles.append(sname.lower())
            elif el.tag == W + "tbl":
                flush_pre()
                inner = table_block(renderer, el, force_html=True)
                acc.figures += inner.figures
                acc.equations += inner.equations
                parts.append(inner.text)
    flush_pre()
    header = bool(styles) and all(s == "tah" for s in styles)
    return "<br>".join(parts), header


def table_block(renderer, tbl, force_html=False):
    part = renderer.part
    acc = TableResult()
    html_mode = force_html or needs_html(tbl, part)
    rows = list(_unwrap(tbl, W + "tr"))
    if not html_mode:
        grid = []
        for tr in rows:
            grid.append([_cell(renderer, tc, "pipe", acc)[0] for tc in _unwrap(tr, W + "tc")])
        ncol = max((len(r) for r in grid), default=0)
        if ncol == 0:
            acc.text = ""
            return acc
        lines = []
        for i, r in enumerate(grid):
            r = r + [""] * (ncol - len(r))
            lines.append("| " + " | ".join(c if c else " " for c in r) + " |")
            if i == 0:
                lines.append("|" + "|".join([" --- "] * ncol) + "|")
        acc.text = "\n".join(lines)
        return acc

    # HTML: work out rowspans from vMerge
    model = []
    for tr in rows:
        trpr = tr.find(W + "trPr")
        before = _int(trpr.find(W + "gridBefore")) if trpr is not None else 0
        after = _int(trpr.find(W + "gridAfter")) if trpr is not None else 0
        col = before
        cells = []
        for tc in _unwrap(tr, W + "tc"):
            tcpr = tc.find(W + "tcPr")
            span = max(1, _int(tcpr.find(W + "gridSpan"), 1)) if tcpr is not None else 1
            vm = None
            if tcpr is not None:
                v = tcpr.find(W + "vMerge")
                if v is not None:
                    vm = "restart" if v.get(W + "val") == "restart" else "continue"
            cells.append({"col": col, "span": span, "vm": vm, "tc": tc, "rowspan": 1, "skip": False})
            col += span
        model.append((before, after, cells))
    index = [{c["col"]: c for c in cells} for _, _, cells in model]
    for i, (_, _, cells) in enumerate(model):
        for c in cells:
            if c["vm"] != "restart":
                continue
            j = i + 1
            while j < len(model):
                nxt = index[j].get(c["col"])
                if nxt is None or nxt["vm"] != "continue":
                    break
                nxt["skip"] = True
                c["rowspan"] += 1
                j += 1
    lines = ["<table>"]
    for before, after, cells in model:
        row = ["<tr>"]
        if before:
            row.append(f'<td colspan="{before}"></td>' if before > 1 else "<td></td>")
        for c in cells:
            if c["skip"]:
                continue
            text, header = _cell(renderer, c["tc"], "html", acc)
            tagname = "th" if header else "td"
            attrs = ""
            if c["span"] > 1:
                attrs += f' colspan="{c["span"]}"'
            if c["rowspan"] > 1:
                attrs += f' rowspan="{c["rowspan"]}"'
            row.append(f"<{tagname}{attrs}>{text}</{tagname}>")
        if after:
            row.append(f'<td colspan="{after}"></td>' if after > 1 else "<td></td>")
        row.append("</tr>")
        lines.append("".join(row))
    lines.append("</table>")
    acc.text = "\n".join(lines)
    return acc

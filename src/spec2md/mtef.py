"""OLE equations (Equation.3 = MTEF v3, Equation.DSMT4 = MTEF v5) -> LaTeX.

Data path: ``w:object`` -> ``o:OLEObject r:id`` -> ``word/embeddings/oleObjectN.bin``
(a compound file) -> stream ``Equation Native`` = EQNOLEFILEHDR (``cbHdr`` bytes,
normally 28) followed by MTEF.

The MTEF byte stream is parsed into a small tree (LINE, CHAR, TMPL, PILE,
MATRIX, EMBELL) and rendered as LaTeX. Size/font/colour/preference records are
read and ignored. Anything unknown raises ``MtefError`` with a short kind
(``"v3 tmpl 48"``); the caller then keeps the WMF preview image instead.
"""
import io
import struct

from .omml import ESCAPE_MATH, ESCAPE_TEXT, GREEK, SYMBOLS

try:  # olefile is pinned in requirements.txt; without it OLE equations stay images
    import olefile
except ImportError:  # pragma: no cover
    olefile = None


class MtefError(Exception):
    pass


# ---------------------------------------------------------------------------
# record model
# ---------------------------------------------------------------------------
class Line:
    __slots__ = ("items", "null")

    def __init__(self, items=None, null=False):
        self.items = items or []
        self.null = null


class Char:
    __slots__ = ("typeface", "code", "embells")

    def __init__(self, typeface, code, embells):
        self.typeface = typeface
        self.code = code
        self.embells = embells


class Tmpl:
    __slots__ = ("selector", "variation", "options", "items")

    def __init__(self, selector, variation, options, items):
        self.selector = selector
        self.variation = variation
        self.options = options
        self.items = items


class Pile:
    __slots__ = ("halign", "lines")

    def __init__(self, halign, lines):
        self.halign = halign
        self.lines = lines


class Matrix:
    __slots__ = ("rows", "cols", "cells")

    def __init__(self, rows, cols, cells):
        self.rows = rows
        self.cols = cols
        self.cells = cells


# ---------------------------------------------------------------------------
# reader
# ---------------------------------------------------------------------------
END, LINE, CHAR, TMPL, PILE, MATRIX, EMBELL, RULER, FONT, SIZE = range(10)
FULL, SUB, SUB2, SYM, SUBSYM = range(10, 15)
COLOR, COLOR_DEF, FONT_DEF, EQN_PREFS, ENCODING_DEF = range(15, 20)


class Reader:
    def __init__(self, data, version):
        self.d = data
        self.i = 0
        self.v = version

    def byte(self):
        if self.i >= len(self.d):
            raise MtefError("truncated")
        b = self.d[self.i]
        self.i += 1
        return b

    def word(self):
        lo = self.byte()
        hi = self.byte()
        return lo | (hi << 8)

    def cstr(self):
        j = self.d.find(b"\x00", self.i)
        if j < 0:
            raise MtefError("truncated")
        self.i = j + 1

    def nudge(self):
        dx, dy = self.byte(), self.byte()
        if dx == 128 and dy == 128:
            self.word()
            self.word()

    def eof(self):
        return self.i >= len(self.d)

    # -- record header ----------------------------------------------------
    def tag(self):
        """Return (record type, options)."""
        b = self.byte()
        if self.v >= 5:
            if b in (END, RULER, FONT, SIZE, FULL, SUB, SUB2, SYM, SUBSYM, COLOR, FONT_DEF, ENCODING_DEF):
                return b, 0
            if b >= 100:  # future record: 2-byte length, skip
                n = self.word()
                self.i += n
                return -1, 0
            return b, self.byte()
        return b & 0x0F, b >> 4

    # -- object lists -----------------------------------------------------
    def objects(self):
        """Read records until END; return the structural ones."""
        out = []
        while True:
            if self.eof():
                return out
            rec, opt = self.tag()
            if rec == END:
                return out
            obj = self.record(rec, opt)
            if obj is not None:
                out.append(obj)

    def record(self, rec, opt):
        v5 = self.v >= 5
        if rec == -1:
            return None
        if rec == LINE:
            if opt & 0x08:
                self.nudge()
            if opt & 0x04:
                self.word()  # line spacing
            if opt & 0x02:
                self.ruler()
            if opt & 0x01:
                return Line(null=True)
            return Line(self.objects())
        if rec == CHAR:
            if opt & 0x08:
                self.nudge()
            tf = self.byte() - 128
            if v5:
                code = None
                if not opt & 0x20:     # mtefOPT_CHAR_ENC_NO_MTCODE
                    code = self.word()
                if opt & 0x04:         # mtefOPT_CHAR_ENC_CHAR_8
                    pos = self.byte()
                    code = pos if code is None else code
                if opt & 0x10:         # mtefOPT_CHAR_ENC_CHAR_16
                    pos = self.word()
                    code = pos if code is None else code
                embell = bool(opt & 0x01)
            else:
                code = self.word()
                embell = bool(opt & 0x02)
            embells = []
            if embell:
                for e in self.objects():
                    if isinstance(e, int):
                        embells.append(e)
            return Char(tf, code, embells)
        if rec == TMPL:
            if opt & 0x08:
                self.nudge()
            sel = self.byte()
            var = self.byte()
            if v5 and var & 0x80:
                var = (var & 0x7F) | (self.byte() << 7)
            topt = self.byte()
            return Tmpl(sel, var, topt, self.objects())
        if rec == PILE:
            if opt & 0x08:
                self.nudge()
            halign = self.byte()
            self.byte()  # valign
            if opt & 0x02:
                self.ruler()
            return Pile(halign, [o for o in self.objects() if isinstance(o, Line)])
        if rec == MATRIX:
            if opt & 0x08:
                self.nudge()
            self.byte()  # valign
            self.byte()  # h_just
            self.byte()  # v_just
            rows = self.byte()
            cols = self.byte()
            self.i += ((rows + 1) * 2 + 7) // 8   # row partition lines
            self.i += ((cols + 1) * 2 + 7) // 8   # column partition lines
            cells = [o for o in self.objects() if isinstance(o, (Line, Pile, Matrix))]  # a cell may be a PILE
            return Matrix(rows, cols, cells)
        if rec == EMBELL:
            if opt & 0x08:
                self.nudge()
            kind = self.byte()  # embellishment type
            if not v5:
                # Equation Editor 3 writes one more byte after the type (always 0 in the
                # 38.211/36.101 data); without skipping it the enclosing LINE ends early.
                self.byte()
            return kind
        if rec == RULER:
            self.ruler(tagged=False)
            return None
        if rec == FONT:
            if v5:  # FONT_STYLE_DEF: font def index + char style
                self.byte()
                self.byte()
            else:
                self.byte()
                self.byte()
                self.cstr()
            return None
        if rec == SIZE:
            lsize = self.byte()
            if lsize == 101:
                self.word()
            elif lsize == 100:
                self.byte()
                self.word()
            else:
                self.byte()
            return None
        if FULL <= rec <= SUBSYM:
            return None
        if v5 and rec == COLOR:
            self.byte()
            return None
        if v5 and rec == COLOR_DEF:
            self.i += 2 * (4 if opt & 0x01 else 3)
            if opt & 0x04:
                self.cstr()
            return None
        if v5 and rec == FONT_DEF:
            self.byte()
            self.cstr()
            return None
        if v5 and rec == EQN_PREFS:
            self.dimensions()   # sizes
            self.dimensions()   # spaces
            n = self.byte()     # styles
            for _ in range(n):
                if self.byte():
                    self.byte()
            return None
        if v5 and rec == ENCODING_DEF:
            self.cstr()
            return None
        raise MtefError(f"v{self.v} record {rec}")

    def ruler(self, tagged=True):
        if tagged and self.v >= 5:
            pass
        if tagged:
            rec, _ = self.tag()
            if rec != RULER:
                raise MtefError(f"v{self.v} ruler expected")
        n = self.byte()
        self.i += 3 * n

    def dimensions(self):
        count = self.byte()
        nibbles = []
        done = 0
        while done < count:
            b = self.byte()
            for nib in (b >> 4, b & 0x0F):
                nibbles.append(nib)
            # a dimension = unit nibble + value nibbles + 0xF terminator
            done = 0
            start = True
            for nib in nibbles:
                if start:
                    start = False
                    continue
                if nib == 0x0F:
                    done += 1
                    start = True
        return count


def parse(data):
    """Equation Native stream bytes -> (version, [top-level objects])."""
    if len(data) < 8:
        raise MtefError("short stream")
    cb = struct.unpack_from("<H", data, 0)[0]
    mtef = data[cb:]
    if not mtef:
        raise MtefError("empty")
    version = mtef[0]
    if version == 3:
        r = Reader(mtef, 3)
        r.i = 5
    elif version == 5:
        r = Reader(mtef, 5)
        r.i = 5
        r.cstr()      # application key
        r.byte()      # equation options
    else:
        raise MtefError(f"MTEF version {version}")
    objs = []
    while not r.eof():
        rec, opt = r.tag()
        if rec == END:
            break
        obj = r.record(rec, opt)
        if obj is not None:
            objs.append(obj)
    return version, objs


def read_equation_native(blob):
    """Compound-file bytes -> 'Equation Native' stream bytes."""
    if olefile is None:
        raise MtefError("olefile not installed")
    try:
        ole = olefile.OleFileIO(io.BytesIO(blob))
    except OSError as e:
        raise MtefError("not a compound file") from e
    try:
        if not ole.exists("Equation Native"):
            raise MtefError("no Equation Native stream")
        return ole.openstream("Equation Native").read()
    finally:
        ole.close()


# ---------------------------------------------------------------------------
# LaTeX rendering
# ---------------------------------------------------------------------------
# typefaces (value - 128)
FN_TEXT, FN_FUNCTION, FN_VARIABLE, FN_LCGREEK, FN_UCGREEK, FN_SYMBOL, FN_VECTOR, FN_NUMBER = range(1, 9)
FN_MTEXTRA, FN_SPACE, FN_EXPAND, FN_MARKER = 11, 24, 22, 23

# MathType private-use code points seen in Equation Editor / MathType data
MT_PRIVATE = {
    0xEB01: "", 0xEB02: r"\,", 0xEB04: r"\:", 0xEB05: r"\;", 0xEB08: r"\quad ", 0xEF04: r"\,",
    0xEF01: "", 0xEF02: r"\,", 0xEF03: r"\:", 0xEF05: r"\;", 0xEF06: r"\quad ", 0xEF07: r"\qquad ",
    0xEF08: r"\,", 0xEB00: "", 0xEF00: "", 0xE900: "",
}
EMBELL_CMD = {
    2: r"\dot", 3: r"\ddot", 4: r"\dddot", 5: "'", 6: "''", 8: r"\tilde", 9: r"\hat",
    11: r"\vec", 12: r"\overleftarrow", 13: r"\overleftrightarrow", 14: r"\vec", 15: r"\overleftarrow",
    17: r"\bar", 18: "'''", 10: r"\not", 24: r"\ddddot",
    19: r"\overset{\frown}", 20: r"\overset{\smile}",
}
FENCE_CHARS = {
    "(": "(", ")": ")", "[": "[", "]": "]", "{": r"\{", "}": r"\}", "|": "|", "‖": r"\|",
    "⟨": r"\langle", "⟩": r"\rangle", "〈": r"\langle", "〉": r"\rangle", "⌊": r"\lfloor",
    "⌋": r"\rfloor", "⌈": r"\lceil", "⌉": r"\rceil", "⟦": "[", "⟧": "]",
}
# default fences per selector when the CHAR records are absent
V3_FENCES = {0: ("⟨", "⟩"), 1: ("(", ")"), 2: ("{", "}"), 3: ("[", "]"), 4: ("|", "|"), 5: ("‖", "‖"),
             6: ("⌊", "⌋"), 7: ("⌈", "⌉"), 8: ("[", "["), 9: ("]", "]"), 10: ("]", "["),
             11: ("[", ")"), 12: ("(", "]")}
V5_FENCES = {0: ("⟨", "⟩"), 1: ("(", ")"), 2: ("{", "}"), 3: ("[", "]"), 4: ("|", "|"), 5: ("‖", "‖"),
             6: ("⌊", "⌋"), 7: ("⌈", "⌉"), 8: ("⟦", "⟧"), 9: ("(", ")")}
BIG_OPS = {"∑": r"\sum", "∏": r"\prod", "∐": r"\coprod", "∪": r"\bigcup", "∩": r"\bigcap",
           "⋃": r"\bigcup", "⋂": r"\bigcap", "∫": r"\int", "∬": r"\iint", "∭": r"\iiint", "∮": r"\oint",
           "⨁": r"\bigoplus", "⨂": r"\bigotimes"}


def _b(s):
    return "{" + s + "}"


class Renderer:
    def __init__(self, version):
        self.v = version

    # -- objects ------------------------------------------------------------
    def objs(self, items):
        out = []
        run = []  # consecutive chars: [(typeface, text)]

        def flush():
            if run:
                out.append(self.chars(run))
                run.clear()
        for it in items:
            if isinstance(it, Char):
                run.append(it)
                continue
            flush()
            out.append(self.obj(it))
        flush()
        return "".join(out)

    def obj(self, it):
        if isinstance(it, Line):
            return "" if it.null else self.objs(it.items)
        if isinstance(it, Tmpl):
            return self.tmpl(it)
        if isinstance(it, Pile):
            lines = [self.obj(ln) for ln in it.lines]
            if not any(ln.strip() for ln in lines):
                return ""  # empty pile: nothing to show
            if len(lines) == 1:
                return lines[0]
            return r"\begin{matrix}" + r" \\ ".join(lines) + r"\end{matrix}"
        if isinstance(it, Matrix):
            rows = []
            cells = [self.obj(c) for c in it.cells]
            if not any(c.strip() for c in cells):
                return ""  # empty matrix
            for r in range(it.rows):
                rows.append(" & ".join(cells[r * it.cols:(r + 1) * it.cols]))
            return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"
        if isinstance(it, Char):
            return self.chars([it])
        if isinstance(it, int):
            return ""
        raise MtefError("object")

    def char_text(self, c):
        code = c.code
        if code is None:
            raise MtefError("char without code")
        if code in MT_PRIVATE:
            return MT_PRIVATE[code], True
        if 0xE000 <= code <= 0xF8FF:
            raise MtefError(f"private char U+{code:04X}")
        ch = chr(code)
        if c.typeface == FN_SPACE:
            return r"\,", True
        return ch, False

    def chars(self, run):
        """Render consecutive CHAR records, grouping text/function/vector typefaces."""
        out = []
        i = 0
        while i < len(run):
            c = run[i]
            tf = c.typeface
            if tf in (FN_TEXT, FN_FUNCTION, FN_VECTOR) and not c.embells:
                j = i
                buf = []
                while j < len(run) and run[j].typeface == tf and not run[j].embells:
                    t, raw = self.char_text(run[j])
                    if raw or (tf != FN_TEXT and not t.isalnum()):
                        break  # punctuation in function/vector typeface stays plain math
                    buf.append(t)
                    j += 1
                if buf:
                    text = "".join(buf)
                    if tf == FN_TEXT:
                        out.append(r"\text{" + "".join(ESCAPE_TEXT.get(ch, ch) for ch in text) + "}")
                    elif tf == FN_FUNCTION:
                        out.append(r"\mathrm{" + self.math_text(text) + "}")
                    else:
                        out.append(r"\mathbf{" + self.math_text(text) + "}")
                    i = j
                    continue
            t, raw = self.char_text(c)
            s = t if raw else self.math_text(t)
            for e in c.embells:
                cmd = EMBELL_CMD.get(e)
                if cmd is None:
                    raise MtefError(f"embell {e}")
                if cmd.startswith("\\"):
                    s = cmd + _b(s)
                else:
                    s = s + cmd
            out.append(s)
            i += 1
        return "".join(out)

    @staticmethod
    def math_text(text):
        out = []
        for ch in text:
            if ch in ESCAPE_MATH:
                out.append(ESCAPE_MATH[ch])
            elif ch in GREEK:
                out.append(GREEK[ch] + " ")
            elif ch in SYMBOLS:
                cmd = SYMBOLS[ch]
                out.append(cmd + " " if cmd.startswith("\\") and cmd[-1].isalpha() else cmd)
            elif ch == "−":
                out.append("-")
            else:
                out.append(ch)
        return "".join(out)

    # -- templates ------------------------------------------------------------
    def slots(self, t):
        """Template sub-objects split into slots (LINE/PILE/MATRIX) and CHAR records."""
        slots = [x for x in t.items if isinstance(x, (Line, Pile, Matrix))]
        chars = [x for x in t.items if isinstance(x, Char)]
        return slots, chars

    def s(self, slots, i):
        return self.obj(slots[i]) if i < len(slots) else ""

    def fence(self, t, defaults):
        slots, chars = self.slots(t)
        left, right = defaults.get(t.selector, ("(", ")"))
        if self.v >= 5:
            has_l, has_r = bool(t.variation & 0x1), bool(t.variation & 0x2)
            if not (t.variation & 0x3):
                has_l = has_r = True
        else:
            # v3 variation: 0 both, 1 left only, 2 right only
            has_l, has_r = t.variation in (0, 1), t.variation in (0, 2)
        # fence CHAR records give the actual delimiters; expanding-font glyphs
        # (typeface fnEXPAND, private code points) are ignored in favour of the selector default
        texts = [chr(c.code) for c in chars
                 if c.code is not None and chr(c.code) in FENCE_CHARS and c.typeface != FN_EXPAND]
        if len(texts) == len(chars) and texts:
            if has_l and has_r and len(texts) >= 2:
                left, right = texts[0], texts[1]
            elif has_l and texts:
                left = texts[0]
            elif has_r and texts:
                right = texts[-1]
        lt = FENCE_CHARS.get(left, ".") if has_l else "."
        rt = FENCE_CHARS.get(right, ".") if has_r else "."
        return r"\left" + lt + " " + self.s(slots, 0) + r" \right" + rt

    def bigop(self, t, default, lower_i=1, upper_i=2, main_i=0):
        slots, chars = self.slots(t)
        op = default
        if chars:
            ch = self.char_text(chars[-1])[0]
            op = BIG_OPS.get(ch, self.math_text(ch))
        lower, upper = self.s(slots, lower_i), self.s(slots, upper_i)
        s = op
        if lower.strip():
            s += "_" + _b(lower)
        if upper.strip():
            s += "^" + _b(upper)
        main = self.s(slots, main_i)
        return s + (_b(main) if main.strip() else "")

    def tmpl(self, t):
        return self.tmpl_v5(t) if self.v >= 5 else self.tmpl_v3(t)

    def scripts(self, slots, sub_i, sup_i, has_sub=True, has_sup=True):
        sub = self.s(slots, sub_i) if has_sub else ""
        sup = self.s(slots, sup_i) if has_sup else ""
        out = ""
        if sub.strip():
            out += "_" + _b(sub)
        if sup.strip():
            out += "^" + _b(sup)
        return out  # both scripts empty: nothing (no stray "{}")

    def tmpl_v3(self, t):
        sel, var = t.selector, t.variation
        slots, chars = self.slots(t)
        if sel <= 12:
            return self.fence(t, V3_FENCES)
        if sel == 13:   # tmROOT: 0 sqrt, 1 nth root  (slots: radicand, index)
            if var == 1 and self.s(slots, 1).strip():
                return r"\sqrt[" + self.s(slots, 1) + "]" + _b(self.s(slots, 0))
            return r"\sqrt" + _b(self.s(slots, 0))
        if sel == 14:   # tmFRACT
            return r"\frac" + _b(self.s(slots, 0)) + _b(self.s(slots, 1))
        if sel == 15:   # tmSCRIPT: 0 sup, 1 sub, 2 sub+sup  (slots: sub, sup)
            return self.scripts(slots, 0, 1)
        if sel in (16, 17):  # tmUBAR / tmOBAR
            cmd = r"\underline" if sel == 16 else r"\overline"
            return cmd + _b(self.s(slots, 0))
        if sel in (18, 19, 20):  # arrows with text above / below
            cmd = {18: r"\xleftarrow", 19: r"\xrightarrow", 20: r"\xleftrightarrow"}[sel]
            return cmd + _b(self.s(slots, 0))
        if 21 <= sel <= 26:  # integrals
            n = (sel - 21) % 3
            return self.bigop(t, [r"\int", r"\iint", r"\iiint"][n])
        if sel in (27, 28):  # horizontal braces (main, label)
            if sel == 27:
                return r"\overbrace" + _b(self.s(slots, 0)) + "^" + _b(self.s(slots, 1))
            return r"\underbrace" + _b(self.s(slots, 0)) + "_" + _b(self.s(slots, 1))
        if 29 <= sel <= 38:
            default = {29: r"\sum", 30: r"\sum", 31: r"\prod", 32: r"\prod", 33: r"\coprod",
                       34: r"\coprod", 35: r"\bigcup", 36: r"\bigcup", 37: r"\bigcap", 38: r"\bigcap"}[sel]
            return self.bigop(t, default)
        if sel == 39:   # tmLIM (main, lower, upper)
            main = self.s(slots, 0)
            lo, up = self.s(slots, 1), self.s(slots, 2)
            s = r"\mathop{" + main + "}"
            if lo.strip():
                s += r"\limits_" + _b(lo)
            if up.strip():
                s += "^" + _b(up)
            return s
        if sel == 41:   # tmSLFRACT
            return _b(self.s(slots, 0)) + "/" + _b(self.s(slots, 1))
        if sel in (42, 43):  # tmINTOP / tmSUMOP: generic big operators
            return self.bigop(t, r"\int" if sel == 42 else r"\sum")
        if sel == 44:   # tmLSCRIPT (left scripts)
            return "{}" + self.scripts(slots, 0, 1)
        if sel == 45:   # tmDIRAC
            return r"\left\langle " + self.s(slots, 0) + r" \middle| " + self.s(slots, 1) + r" \right\rangle"
        if sel in (46, 47):  # arrow under / over
            cmd = r"\underrightarrow" if sel == 46 else r"\overrightarrow"
            return cmd + _b(self.s(slots, 0))
        if sel == 48:   # tmOARC
            return r"\overset{\frown}" + _b(self.s(slots, 0))
        raise MtefError(f"v3 tmpl {sel}")

    def tmpl_v5(self, t):
        sel, var = t.selector, t.variation
        slots, chars = self.slots(t)
        if sel <= 9:
            return self.fence(t, V5_FENCES)
        if sel == 10:   # tmROOT: 0 sqrt, 1 nth root  (slots: radicand, index)
            if var & 1 and self.s(slots, 1).strip():
                return r"\sqrt[" + self.s(slots, 1) + "]" + _b(self.s(slots, 0))
            return r"\sqrt" + _b(self.s(slots, 0))
        if sel == 11:   # tmFRACT; 0x0002 slash variants
            if var & 0x6:
                return _b(self.s(slots, 0)) + "/" + _b(self.s(slots, 1))
            return r"\frac" + _b(self.s(slots, 0)) + _b(self.s(slots, 1))
        if sel in (12, 13):  # tmUBAR / tmOBAR
            cmd = r"\underline" if sel == 12 else r"\overline"
            return cmd + _b(self.s(slots, 0))
        if sel == 14:   # tmARROW
            return r"\xrightarrow" + _b(self.s(slots, 0))
        if sel == 15:   # tmINTEG
            n = 1 + (1 if var & 0x2 else 0) + (1 if var & 0x4 else 0)
            default = [r"\int", r"\iint", r"\iiint"][min(n, 3) - 1]
            if var & 0x8:
                default = r"\oint"
            return self.bigop(t, default)
        if 16 <= sel <= 22:
            default = {16: r"\sum", 17: r"\prod", 18: r"\coprod", 19: r"\bigcup", 20: r"\bigcap",
                       21: r"\int", 22: r"\sum"}[sel]
            return self.bigop(t, default)
        if sel == 23:   # tmLIM (main, lower, upper)
            main = self.s(slots, 0)
            lo, up = self.s(slots, 1), self.s(slots, 2)
            s = r"\mathop{" + main + "}"
            if lo.strip():
                s += r"\limits_" + _b(lo)
            if up.strip():
                s += "^" + _b(up)
            return s
        if sel in (24, 25):  # tmHBRACE / tmHBRACK (main, label); variation 1 = upper
            cmd = (r"\overbrace" if var & 1 else r"\underbrace") if sel == 24 else (
                r"\overbracket" if var & 1 else r"\underbracket")
            mark = "^" if var & 1 else "_"
            return cmd + _b(self.s(slots, 0)) + mark + _b(self.s(slots, 1))
        if sel in (27, 28, 29):  # tmSUB / tmSUP / tmSUBSUP (slots: sub, sup)
            return self.scripts(slots, 0, 1, sel != 28, sel != 27)
        if sel == 30:   # tmDIRAC
            return r"\left\langle " + self.s(slots, 0) + r" \middle| " + self.s(slots, 1) + r" \right\rangle"
        if sel == 31:   # tmVEC
            return r"\overrightarrow" + _b(self.s(slots, 0))
        if sel == 32:
            return r"\widetilde" + _b(self.s(slots, 0))
        if sel == 33:
            return r"\widehat" + _b(self.s(slots, 0))
        if sel == 34:
            return r"\overset{\frown}" + _b(self.s(slots, 0))
        if sel in (35, 36):  # tmJSTATUS / tmSTRIKE
            return self.s(slots, 0)
        if sel == 37:
            return r"\boxed" + _b(self.s(slots, 0))
        raise MtefError(f"v5 tmpl {sel}")


def to_latex(stream):
    """Equation Native stream -> LaTeX (raises MtefError)."""
    version, objs = parse(stream)
    r = Renderer(version)
    lines = [r.obj(o) for o in objs if isinstance(o, (Line, Pile, Matrix, Tmpl, Char))]
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        raise MtefError("empty equation")
    s = lines[0] if len(lines) == 1 else r"\begin{gathered}" + r" \\ ".join(lines) + r"\end{gathered}"
    s = " ".join(s.split())
    from .omml import CMD_SPACE_RE, strip_empty
    s = strip_empty(CMD_SPACE_RE.sub(r"\1", s).strip())
    if not s:
        raise MtefError("empty equation")
    return s

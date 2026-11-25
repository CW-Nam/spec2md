"""OMML (Office Math, ``m:oMath``) -> LaTeX.

Covers the elements listed in the 38.211 format report (sSub, d, sSubSup, m,
f, acc, sSup, rad, nary, func, limLow, ...) plus the remaining OMML elements
(sPre, limUpp, eqArr, groupChr, bar, box, borderBox, phant). An element that
cannot be converted makes the whole equation ``[equation]`` and is reported
through ``unhandled``.
"""
import re
from collections import Counter

from .ns import M, W, local
from .symbols import font_kind, map_char

GREEK = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\varepsilon",
    "ϵ": r"\epsilon", "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta", "ϑ": r"\vartheta",
    "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu", "ξ": r"\xi",
    "ο": "o", "π": r"\pi", "ϖ": r"\varpi", "ρ": r"\rho", "ϱ": r"\varrho", "σ": r"\sigma",
    "ς": r"\varsigma", "τ": r"\tau", "υ": r"\upsilon", "φ": r"\varphi", "ϕ": r"\phi",
    "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda", "Ξ": r"\Xi", "Π": r"\Pi",
    "Σ": r"\Sigma", "Υ": r"\Upsilon", "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N",
    "Ο": "O", "Ρ": "P", "Τ": "T", "Χ": "X",
}
SYMBOLS = {
    "×": r"\times", "÷": r"\div", "·": r"\cdot", "∙": r"\cdot", "⋅": r"\cdot", "•": r"\bullet",
    "…": r"\ldots", "⋯": r"\cdots", "⋮": r"\vdots", "⋱": r"\ddots", "∈": r"\in", "∉": r"\notin",
    "∋": r"\ni", "≤": r"\le", "≥": r"\ge", "≠": r"\ne", "≈": r"\approx", "≡": r"\equiv",
    "≅": r"\cong", "∼": r"\sim", "∝": r"\propto", "±": r"\pm", "∓": r"\mp", "∞": r"\infty",
    "∆": r"\Delta", "∂": r"\partial", "∇": r"\nabla", "∑": r"\sum", "∏": r"\prod", "∫": r"\int",
    "√": r"\surd", "∀": r"\forall", "∃": r"\exists", "∅": r"\emptyset", "∩": r"\cap",
    "∪": r"\cup", "⊂": r"\subset", "⊃": r"\supset", "⊆": r"\subseteq", "⊇": r"\supseteq",
    "⊕": r"\oplus", "⊗": r"\otimes", "∘": r"\circ", "°": r"^{\circ}", "¬": r"\neg",
    "∧": r"\wedge", "∨": r"\vee", "→": r"\rightarrow", "←": r"\leftarrow", "↔": r"\leftrightarrow",
    "⇒": r"\Rightarrow", "⇐": r"\Leftarrow", "⇔": r"\Leftrightarrow", "↑": r"\uparrow",
    "↓": r"\downarrow", "⌊": r"\lfloor", "⌋": r"\rfloor", "⌈": r"\lceil", "⌉": r"\rceil",
    "〈": r"\langle", "〉": r"\rangle", "⟨": r"\langle", "⟩": r"\rangle", "‖": r"\|",
    "−": "-", "∗": "*", "′": "'", "″": "''", "‾": r"\overline{}", "ℓ": r"\ell", "ℜ": r"\Re",
    "ℑ": r"\Im", "ℵ": r"\aleph", "∠": r"\angle", "⊥": r"\perp", "∥": r"\parallel",
    "∖": r"\setminus", "≪": r"\ll", "≫": r"\gg", "≜": r"\triangleq", "≔": ":=",
    " ": " ", " ": r"\,", " ": r"\ ", " ": r"\quad", "​": "",
}
ESCAPE_MATH = {"\\": r"\backslash ", "{": r"\{", "}": r"\}", "#": r"\#", "$": r"\$", "%": r"\%",
               "&": r"\&", "_": r"\_", "^": r"\hat{}", "~": r"\sim ", "|": r"\vert "}
ESCAPE_TEXT = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "#": r"\#", "$": r"\$",
               "%": r"\%", "&": r"\&", "_": r"\_", "^": r"\^{}", "~": r"\~{}"}
ACCENTS = {"̂": r"\hat", "̃": r"\tilde", "̅": r"\bar", "̄": r"\bar",
           "¯": r"\bar", "̇": r"\dot", "̈": r"\ddot", "⃗": r"\vec",
           "̆": r"\breve", "̌": r"\check", "́": r"\acute", "̀": r"\grave",
           "⃖": r"\overleftarrow", "→": r"\vec", "~": r"\tilde", "^": r"\hat"}
NARY = {"∑": r"\sum", "∏": r"\prod", "∐": r"\coprod", "∫": r"\int", "∬": r"\iint",
        "∭": r"\iiint", "∮": r"\oint", "⋃": r"\bigcup", "⋂": r"\bigcap", "⋁": r"\bigvee",
        "⋀": r"\bigwedge", "⨁": r"\bigoplus", "⨂": r"\bigotimes", "⨀": r"\bigodot"}
DELIMS = {"(": "(", ")": ")", "[": "[", "]": "]", "{": r"\{", "}": r"\}", "|": "|",
          "‖": r"\|", "⌊": r"\lfloor", "⌋": r"\rfloor", "⌈": r"\lceil", "⌉": r"\rceil",
          "〈": r"\langle", "〉": r"\rangle", "⟨": r"\langle", "⟩": r"\rangle", "⟦": "[[",
          "⟧": "]]", "/": "/", "\\": r"\backslash", "": "."}
STYLE_CMD = {"p": r"\mathrm", "b": r"\mathbf", "bi": r"\boldsymbol"}
SCRIPT_CMD = {"script": r"\mathcal", "double-struck": r"\mathbb", "fraktur": r"\mathfrak",
              "sans-serif": r"\mathsf", "monospace": r"\mathtt"}

CMD_SPACE_RE = re.compile(r"(\\[A-Za-z]+) (?![A-Za-z])")
BREAK = "\x00BR\x00"
ALIGN = "\x00AL\x00"
IGNORED = {"ctrlPr", "argPr", "rPr", "sSubPr", "sSupPr", "sSubSupPr", "sPrePr", "dPr", "mPr",
           "fPr", "accPr", "radPr", "naryPr", "funcPr", "limLowPr", "limUppPr", "eqArrPr",
           "groupChrPr", "barPr", "boxPr", "borderBoxPr", "phantPr", "mcs", "oMathParaPr"}


class Unconvertible(Exception):
    pass


def _val(el, path, default=None):
    """Value of m:val on a property child such as 'dPr/begChr'."""
    node = el
    for part in path.split("/"):
        if node is None:
            return default
        node = node.find(M + part)
    if node is None:
        return default
    v = node.get(M + "val")
    return default if v is None else v


def _on(el, path):
    """Boolean OMML property (present without val, or val=1/on/true)."""
    node = el
    for part in path.split("/"):
        if node is None:
            return False
        node = node.find(M + part)
    if node is None:
        return False
    v = node.get(M + "val")
    return v is None or v.lower() in ("1", "on", "true")


def _brace(s):
    return "{" + s + "}"


EMPTY_ENV_RE = re.compile(r"\\begin\{(matrix|gathered|aligned|array)\}\s*\\end\{\1\}")
TRAILING_EMPTY_RE = re.compile(r"(?:\s*\{\s*\})+\s*$")


def strip_empty(s):
    """Drop content-free LaTeX: empty matrix/gathered/aligned environments and trailing '{}'.

    A '{}' inside the expression (e.g. the empty base of '{}_{a}^{b}') is kept.
    """
    prev = None
    while prev != s:
        prev = s
        s = EMPTY_ENV_RE.sub("", s)
        s = TRAILING_EMPTY_RE.sub("", s).strip()
    return s


class OmmlConverter:
    def __init__(self):
        self.unhandled = Counter()

    def convert(self, omath):
        """m:oMath element -> LaTeX string (no $ delimiters)."""
        try:
            s = self._children(omath)
        except Unconvertible as e:
            self.unhandled[str(e)] += 1
            return "[equation]"
        return self._finish(s)

    # -- helpers -------------------------------------------------------
    def _finish(self, s):
        s = " ".join(s.split())
        s = CMD_SPACE_RE.sub(r"\1", s)  # "\mu }" -> "\mu}": a space after a command only matters before a letter
        while s.startswith(BREAK) or s.endswith(BREAK) or s != s.strip():
            s = s.strip()
            if s.startswith(BREAK):
                s = s[len(BREAK):]
            if s.endswith(BREAK):
                s = s[:-len(BREAK)]
        if BREAK in s:
            s = s.replace(BREAK, r" \\ ").replace(ALIGN, "& ")
            s = r"\begin{aligned}" + s.strip() + r"\end{aligned}"
        else:
            s = s.replace(ALIGN, "")
        return strip_empty(s.strip())

    def _children(self, el):
        return "".join(self._conv(c) for c in el)

    def _arg(self, el, name):
        c = el.find(M + name)
        return "" if c is None else self._children(c)

    def _text(self, text, nor, sty, scr, font=None):
        kind = font_kind(font)
        out = []
        if nor:
            for ch in text:
                if kind:
                    ch = map_char(ord(ch), kind) or ch
                out.append(ESCAPE_TEXT.get(ch, ch))
            return r"\text{" + "".join(out) + "}"
        for ch in text:
            if kind or "" <= ch <= "":
                ch = map_char(ord(ch), kind or "symbol") or ch
            if ch in ESCAPE_MATH:
                out.append(ESCAPE_MATH[ch])
            elif ch in GREEK:
                out.append(GREEK[ch] + " ")
            elif ch in SYMBOLS:
                cmd = SYMBOLS[ch]
                out.append(cmd + " " if cmd.startswith("\\") and cmd[-1].isalpha() else cmd)
            else:
                out.append(ch)
        s = "".join(out)
        cmd = SCRIPT_CMD.get(scr) if scr else None
        if cmd is None and sty in STYLE_CMD and any(c.isalnum() for c in text):
            if sty == "p" and len(text.strip()) <= 1 and not text.strip().isalpha():
                cmd = None
            else:
                cmd = STYLE_CMD[sty]
        return cmd + "{" + s.strip() + "}" if cmd and s.strip() else s

    # -- element dispatch ----------------------------------------------
    def _conv(self, el):
        tag = el.tag
        if not isinstance(tag, str):
            return ""
        if tag.startswith(M):
            name = tag[len(M):]
            if name in IGNORED:
                return ""
            fn = getattr(self, "_m_" + name, None)
            if fn is None:
                raise Unconvertible("m:" + name)
            return fn(el)
        if tag.startswith(W):
            name = tag[len(W):]
            if name == "r":
                return self._w_r(el)
            if name in ("ins", "moveTo", "smartTag", "customXml", "hyperlink"):
                return self._children(el)
            if name == "sdt":
                c = el.find(W + "sdtContent")
                return "" if c is None else self._children(c)
            if name in ("del", "moveFrom", "bookmarkStart", "bookmarkEnd", "proofErr", "rPr",
                        "permStart", "permEnd", "commentRangeStart", "commentRangeEnd"):
                return ""
            raise Unconvertible("w:" + name)
        return ""

    def _w_r(self, el):
        """A plain Word run inside an equation (rare): text as \\text{}."""
        out = []
        for c in el:
            if c.tag == W + "t" and c.text:
                out.append(r"\text{" +"".join(ESCAPE_TEXT.get(ch, ch) for ch in c.text) + "}")
            elif c.tag in (W + "br", W + "cr"):
                out.append(BREAK)
        return "".join(out)

    def _m_oMath(self, el):
        return self._children(el)

    def _m_oMathPara(self, el):
        return r" \\ ".join(self._children(c) for c in el.findall(M + "oMath"))

    def _m_r(self, el):
        rpr = el.find(M + "rPr")
        nor = _on(rpr, "nor") if rpr is not None else False
        sty = _val(rpr, "sty") if rpr is not None else None
        scr = _val(rpr, "scr") if rpr is not None else None
        aln = rpr is not None and rpr.find(M + "aln") is not None
        font = None
        wrpr = el.find(W + "rPr")
        if wrpr is not None:
            rf = wrpr.find(W + "rFonts")
            if rf is not None:
                font = rf.get(W + "ascii") or rf.get(W + "hAnsi")
        out = [ALIGN] if aln else []
        buf = []

        def flush():
            if buf:
                out.append(self._text("".join(buf), nor, sty, scr, font))
                buf.clear()
        for c in el:
            t = c.tag
            if t in (M + "t", W + "t"):
                buf.append(c.text or "")
            elif t in (W + "br", W + "cr"):
                flush()
                out.append(BREAK)
            elif t == W + "tab":
                buf.append(" ")
            elif t == W + "sym":
                ch = c.get(W + "char") or ""
                try:
                    mapped = map_char(int(ch, 16), font_kind(c.get(W + "font")) or "symbol")
                except ValueError:
                    mapped = None
                if mapped:
                    buf.append(mapped)
                else:
                    self.unhandled["w:sym " + ch] += 1
            elif t == W + "noBreakHyphen":
                buf.append("-")
        flush()
        return "".join(out)

    def _m_e(self, el):
        return self._children(el)

    _m_sub = _m_sup = _m_num = _m_den = _m_deg = _m_lim = _m_fName = _m_e

    def _m_sSub(self, el):
        return _brace(self._arg(el, "e")) + "_" + _brace(self._arg(el, "sub"))

    def _m_sSup(self, el):
        return _brace(self._arg(el, "e")) + "^" + _brace(self._arg(el, "sup"))

    def _m_sSubSup(self, el):
        return (_brace(self._arg(el, "e")) + "_" + _brace(self._arg(el, "sub"))
                + "^" + _brace(self._arg(el, "sup")))

    def _m_sPre(self, el):
        return ("{}_" + _brace(self._arg(el, "sub")) + "^" + _brace(self._arg(el, "sup"))
                + _brace(self._arg(el, "e")))

    def _m_f(self, el):
        typ = _val(el, "fPr/type", "bar")
        num, den = self._arg(el, "num"), self._arg(el, "den")
        if typ == "lin":
            return _brace(num) + "/" + _brace(den)
        if typ == "skw":
            return "{}^{" + num + "}/_{" + den + "}"
        if typ == "noBar":
            return r"\genfrac{}{}{0pt}{}" + _brace(num) + _brace(den)
        return r"\frac" + _brace(num) + _brace(den)

    def _matrix(self, m, env):
        rows = []
        for mr in m.findall(M + "mr"):
            rows.append(" & ".join(self._children(e) for e in mr.findall(M + "e")))
        return r"\begin{" + env + "}" + r" \\ ".join(rows) + r"\end{" + env + "}"

    def _m_m(self, el):
        return self._matrix(el, "matrix")

    def _m_d(self, el):
        dpr = el.find(M + "dPr")
        beg = _val(dpr, "begChr", "(") if dpr is not None else "("
        end = _val(dpr, "endChr", ")") if dpr is not None else ")"
        sep = _val(dpr, "sepChr", "|") if dpr is not None else "|"
        es = el.findall(M + "e")
        if len(es) == 1:
            inner = [c for c in es[0] if isinstance(c.tag, str) and local(c.tag) not in IGNORED]
            if len(inner) == 1 and inner[0].tag == M + "m":
                env = {("[", "]"): "bmatrix", ("(", ")"): "pmatrix", ("|", "|"): "vmatrix",
                       ("‖", "‖"): "Vmatrix", ("{", "}"): "Bmatrix"}.get((beg, end))
                if env:
                    return self._matrix(inner[0], env)
                if beg == "{" and end == "":
                    return self._matrix(inner[0], "cases")
        body = (" " + self._sep(sep) + " ").join(self._children(e) for e in es)
        return r"\left" + self._delim(beg) + " " + body + r" \right" + self._delim(end)

    def _sep(self, ch):
        return {"|": r"\vert", "‖": r"\|", "": ""}.get(ch, ch)

    def _delim(self, ch):
        d = DELIMS.get(ch)
        if d is None:
            self.unhandled["m:d delimiter " + ch] += 1
            return "."
        return d

    def _m_acc(self, el):
        ch = _val(el, "accPr/chr", "̂")
        e = self._arg(el, "e")
        cmd = ACCENTS.get(ch)
        if cmd:
            return cmd + _brace(e)
        return r"\overset" + _brace(self._text(ch, False, None, None)) + _brace(e)

    def _m_bar(self, el):
        pos = _val(el, "barPr/pos", "bot")
        return (r"\overline" if pos == "top" else r"\underline") + _brace(self._arg(el, "e"))

    def _m_rad(self, el):
        deg = self._arg(el, "deg")
        e = self._arg(el, "e")
        if _on(el, "radPr/degHide") or not deg.strip():
            return r"\sqrt" + _brace(e)
        return r"\sqrt[" + deg + "]" + _brace(e)

    def _m_nary(self, el):
        ch = _val(el, "naryPr/chr", "∫")
        cmd = NARY.get(ch)
        if cmd is None:
            cmd = self._text(ch, False, None, None)
        loc = _val(el, "naryPr/limLoc", "undOvr" if ch != "∫" else "subSup")
        s = cmd + (r"\limits" if loc == "undOvr" and cmd.startswith("\\") else "")
        if not _on(el, "naryPr/subHide"):
            sub = self._arg(el, "sub")
            if sub.strip():
                s += "_" + _brace(sub)
        if not _on(el, "naryPr/supHide"):
            sup = self._arg(el, "sup")
            if sup.strip():
                s += "^" + _brace(sup)
        return s + _brace(self._arg(el, "e"))

    def _m_func(self, el):
        return self._arg(el, "fName") + " " + _brace(self._arg(el, "e"))

    def _m_limLow(self, el):
        return r"\underset" + _brace(self._arg(el, "lim")) + _brace(self._arg(el, "e"))

    def _m_limUpp(self, el):
        return r"\overset" + _brace(self._arg(el, "lim")) + _brace(self._arg(el, "e"))

    def _m_eqArr(self, el):
        rows = [self._children(e) for e in el.findall(M + "e")]
        body = r" \\ ".join(r.replace(ALIGN, "& ") for r in rows)
        return r"\begin{aligned}" + body + r"\end{aligned}"

    def _m_groupChr(self, el):
        ch = _val(el, "groupChrPr/chr", "⏟")
        pos = _val(el, "groupChrPr/pos", "bot")
        e = self._arg(el, "e")
        if ch == "⏟":
            return r"\underbrace" + _brace(e)
        if ch == "⏞":
            return r"\overbrace" + _brace(e)
        sym = self._text(ch, False, None, None)
        return (r"\overset" if pos == "top" else r"\underset") + _brace(sym) + _brace(e)

    def _m_box(self, el):
        return _brace(self._arg(el, "e"))

    def _m_borderBox(self, el):
        return r"\boxed" + _brace(self._arg(el, "e"))

    def _m_phant(self, el):
        if _val(el, "phantPr/show", "1") in ("0", "off", "false"):
            return r"\phantom" + _brace(self._arg(el, "e"))
        return _brace(self._arg(el, "e"))

"""OMML -> LaTeX for the element set found in TS 38.211 (and the rest of OMML)."""
import pytest
from lxml import etree

from docx_builder import NS
from spec2md.omml import OmmlConverter


def r(t, rpr=""):
    return f"<m:r>{'<m:rPr>' + rpr + '</m:rPr>' if rpr else ''}<m:t>{t}</m:t></m:r>"


STY_P = '<m:sty m:val="p"/>'


def e(x):
    return f"<m:e>{x}</m:e>"


def conv(inner):
    om = etree.fromstring(f"<m:oMath {NS}>{inner}</m:oMath>")
    c = OmmlConverter()
    out = c.convert(om)
    return out, c.unhandled


CASES = [
    (r("x"), "x"),
    (f"<m:sSub>{e(r('N'))}<m:sub>{r('RB', '<m:nor/>')}</m:sub></m:sSub>", r"{N}_{\text{RB}}"),
    (f"<m:sSup>{e(r('2'))}<m:sup>{r('μ')}</m:sup></m:sSup>", r"{2}^{\mu}"),
    (f"<m:sSubSup>{e(r('N'))}<m:sub>{r('sc')}</m:sub><m:sup>{r('RB')}</m:sup></m:sSubSup>",
     r"{N}_{sc}^{RB}"),
    (f"<m:sPre><m:sub>{r('a')}</m:sub><m:sup>{r('b')}</m:sup>{e(r('X'))}</m:sPre>", r"{}_{a}^{b}{X}"),
    (f"<m:f><m:num>{r('a')}</m:num><m:den>{r('b')}</m:den></m:f>", r"\frac{a}{b}"),
    (f'<m:f><m:fPr><m:type m:val="lin"/></m:fPr><m:num>{r("a")}</m:num><m:den>{r("b")}</m:den></m:f>',
     "{a}/{b}"),
    (f"<m:d>{e(r('i'))}</m:d>", r"\left( i \right)"),
    (f'<m:d><m:dPr><m:begChr m:val="⌊"/><m:endChr m:val="⌋"/></m:dPr>{e(r("x"))}</m:d>',
     r"\left\lfloor x \right\rfloor"),
    (f'<m:d><m:dPr><m:begChr m:val="{{"/><m:endChr m:val=""/></m:dPr>{e(r("x"))}</m:d>',
     r"\left\{ x \right."),
    (f'<m:d><m:dPr><m:sepChr m:val=","/></m:dPr>{e(r("a"))}{e(r("b"))}</m:d>', r"\left( a , b \right)"),
    (f'<m:d><m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr>'
     f"<m:e><m:m><m:mr>{e(r('1'))}{e(r('0'))}</m:mr><m:mr>{e(r('0'))}{e(r('1'))}</m:mr></m:m></m:e></m:d>",
     r"\begin{bmatrix}1 & 0 \\ 0 & 1\end{bmatrix}"),
    (f'<m:d><m:dPr><m:begChr m:val="{{"/><m:endChr m:val=""/></m:dPr>'
     f"<m:e><m:m><m:mr>{e(r('0'))}{e(r('if', '<m:nor/>'))}</m:mr></m:m></m:e></m:d>",
     r"\begin{cases}0 & \text{if}\end{cases}"),
    (f"<m:m><m:mr>{e(r('a'))}</m:mr></m:m>", r"\begin{matrix}a\end{matrix}"),
    (f'<m:acc><m:accPr><m:chr m:val="̅"/></m:accPr>{e(r("s"))}</m:acc>', r"\bar{s}"),
    (f'<m:acc><m:accPr><m:chr m:val="̃"/></m:accPr>{e(r("b"))}</m:acc>', r"\tilde{b}"),
    (f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>{e(r("2"))}</m:rad>', r"\sqrt{2}"),
    (f"<m:rad><m:deg>{r('3')}</m:deg>{e(r('x'))}</m:rad>", r"\sqrt[3]{x}"),
    (f'<m:nary><m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="undOvr"/></m:naryPr><m:sub>{r("k=0")}</m:sub>'
     f"<m:sup>{r('K')}</m:sup>{e(r('a'))}</m:nary>", r"\sum\limits_{k=0}^{K}{a}"),
    (f'<m:nary><m:naryPr><m:chr m:val="∏"/><m:limLoc m:val="subSup"/><m:supHide m:val="1"/></m:naryPr>'
     f"<m:sub>{r('i')}</m:sub><m:sup/>{e(r('x'))}</m:nary>", r"\prod_{i}{x}"),
    (f"<m:func><m:fName>{r('mod', STY_P)}</m:fName>{e(r('x'))}</m:func>",
     r"\mathrm{mod} {x}"),
    (f"<m:limLow>{e(r('min', STY_P))}<m:lim>{r('i')}</m:lim></m:limLow>",
     r"\underset{i}{\mathrm{min}}"),
    (f"<m:limUpp>{e(r('x'))}<m:lim>{r('n')}</m:lim></m:limUpp>", r"\overset{n}{x}"),
    (f"<m:eqArr>{e(r('a'))}{e(r('b'))}</m:eqArr>", r"\begin{aligned}a \\ b\end{aligned}"),
    (f"<m:groupChr>{e(r('x'))}</m:groupChr>", r"\underbrace{x}"),
    (f'<m:bar><m:barPr><m:pos m:val="top"/></m:barPr>{e(r("x"))}</m:bar>', r"\overline{x}"),
    (f"<m:borderBox>{e(r('x'))}</m:borderBox>", r"\boxed{x}"),
    (f"<m:box>{e(r('x'))}</m:box>", "{x}"),
    (f"<m:phant>{e(r('x'))}</m:phant>", "{x}"),
    (r("v", '<m:sty m:val="bi"/>'), r"\boldsymbol{v}"),
    (r("C", '<m:scr m:val="script"/>'), r"\mathcal{C}"),
    (r("a×b≤c∈Δ…"), r"a\times b\le c\in\Delta\ldots"),
    (r("{x}_%"), r"\{x\}\_\%"),
    (r("a&lt;b"), "a<b"),
]


@pytest.mark.parametrize("xml,expected", CASES)
def test_omml(xml, expected):
    out, unhandled = conv(xml)
    assert " ".join(out.split()) == " ".join(expected.split())
    assert not unhandled


def test_line_breaks_become_aligned():
    out, _ = conv(r("a") + '<m:r><m:rPr><m:aln/></m:rPr><m:t>=b</m:t></m:r><m:r><w:br/></m:r>'
                  + '<m:r><m:rPr><m:aln/></m:rPr><m:t>=c</m:t></m:r><m:r><w:br/></m:r>')
    assert out == r"\begin{aligned}a& =b \\ & =c\end{aligned}"


def test_unknown_element_gives_placeholder():
    out, unhandled = conv("<m:unknownThing/>")
    assert out == "[equation]" and unhandled == {"m:unknownThing": 1}

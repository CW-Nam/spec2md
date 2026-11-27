"""Heading interpretation must match the reference implementation in inspect_docx.py."""
import pytest
from lxml import etree

from docx_builder import NS, p
from spec2md import headings as H

TEXTS = [
    "Foreword", "\n1\tScope", "5.3.5\tRRC reconfiguration", "4.3A\tApplicability", "9.4.1a\tX",
    "5.3.5.13b1\tY", "B.2.3B.4A\tZ", "F.5.F\tW", "6.3.3.1.\tMinimum requirement",
    "8.4.1.2.3 Minimum requirement", "10.4 FDD", "A.1\tGeneral",
    "Annex A (normative):\nMeasurement channels", "Annex J (informative): Change history",
    "Annex AB (normative):\tTitle", "–\tRRCReconfiguration", "-\tSIB1", "5.2.2.3.3a\tRequest",
    "Generation of rZC,m(n)", "7.4.1.6.4.2\tmapping from  to", "5.1.1\tπ/2-BPSK", "Contents",
    "5.1.2\tVoid", "12\tVoid", "A\tAnnex without word",
    "5. 2.2.4.2.3\tX", "5.\tScope", "5. 2 things\tx",
]


@pytest.mark.parametrize("text,expected", [
    ("5. 2.2.4.2.3\tX", ("5.2.2.4.2.3", "X")),
    ("5.\tScope", ("5", "Scope")),
    ("5. 2 things\tx", ("5", "2 things\tx")),
    ("10.1. 38A.1\tIntroduction", ("10.1.38A.1", "Introduction")),
    ("A.6. 11.3.1.3\tTest requirements", ("A.6.11.3.1.3", "Test requirements")),
    ("A. 1.2\tX", (None, "A. 1.2\tX")),  # lone annex letter: not merged (unchanged)
])
def test_split_number_typo(inspect_mod, text, expected):
    assert H.parse_clause(text) == expected == inspect_mod.parse_clause(text)


@pytest.mark.parametrize("text", TEXTS)
def test_parse_clause_matches_reference(inspect_mod, text):
    assert H.parse_clause(text) == inspect_mod.parse_clause(text)
    clause, _ = H.parse_clause(text)
    assert H.clause_parent(clause) == inspect_mod.clause_parent(clause)
    for lvl in (1, 3, 8):
        assert H.clause_level(clause, lvl) == inspect_mod.clause_level(clause, lvl)
    assert H.norm_heading(text) == inspect_mod.norm_heading(text)


def _el(xml):
    return etree.fromstring(f"<w:body {NS}>{xml}</w:body>")[0]


STYLES = {"Heading1": ("heading 1", 1), "H6": ("H6", None), "Normal": ("Normal", None),
          "TT": ("TT", 1), "B1": ("B1", None)}


@pytest.mark.parametrize("xml", [
    p("Heading1", "1\tScope"),
    p("H6", "8.1.2.12.1.1\tApplicability"),
    p("Normal", "8.13.2.3\tTitle", ppr='<w:outlineLvl w:val="3"/>'),
    p("Normal", "body", ppr='<w:outlineLvl w:val="9"/>'),
    p("B1", "1>\titem"),
    p("TT", "Contents"),
    p(None, "no style"),
])
def test_para_style_and_text_match_reference(inspect_mod, xml):
    el = _el(xml)
    assert H.para_style(el, STYLES) == inspect_mod.para_style(el, STYLES)
    assert H.heading_text(el) == inspect_mod.para_text(el)


def test_heading_object():
    h = H.Heading("Annex A (normative):\nMeasurement channels", "heading 8", 8, "x.docx")
    assert (h.clause, h.title, h.level, h.key) == ("A", "Measurement channels", 1, "A")
    assert h.display == "Annex A (normative): Measurement channels"
    h = H.Heading("A.1\tGeneral", "heading 1", 1, "x.docx")
    assert (h.level, h.display) == (2, "A.1 General")
    h = H.Heading("–\tRF-Parameters", "heading 4", 4, "x.docx")
    assert (h.clause, h.key, h.title, h.level) == (None, "rf-parameters", "RF-Parameters", 4)
    h = H.Heading("6.3.3.1.\tMinimum requirement", "heading 5", 5, "x.docx")
    assert (h.clause, h.level, h.display) == ("6.3.3.1", 4, "6.3.3.1 Minimum requirement")


def test_slugify_matches_checker():
    import importlib.util
    from conftest import CHECK
    spec = importlib.util.spec_from_file_location("check_output", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for t in ["RRCReconfiguration", "Foreword", "UE (User Equipment)", "  -x-  ", "π/2-BPSK"]:
        assert H.slugify(t) == mod.slugify(t)


@pytest.mark.parametrize("text,expected", [
    # 38306-j40: 부속서 하위 조항 번호 뒤에 콜론
    ("A.1:\tTDD/FDD differentiation of capabilities in TDD-FDD CA",
     ("A.1", "TDD/FDD differentiation of capabilities in TDD-FDD CA")),
    ("A.5:\tGeneral differentiation", ("A.5", "General differentiation")),
    ("Annex A (normative):\tTitle", ("A", "Title")),
    ("NOTE:\tnot a heading number", (None, "NOTE:\tnot a heading number")),
])
def test_colon_after_number(inspect_mod, text, expected):
    assert H.parse_clause(text) == expected == inspect_mod.parse_clause(text)


@pytest.mark.parametrize("name,level", [("Header 6", 6), ("Header 7", 7), ("header", None)])
def test_header_n_style_is_heading(inspect_mod, name, level):
    # 38101-5-j60: "8.1.3.4.2.1 Derivation of Noc values …"가 사용자 정의 스타일 "Header 6"(outlineLvl 없음)이다.
    # 쪽 머리글 스타일 "header"(번호 없음)는 제목이 아니다.
    styles = {"Hdr": (name, None)}
    el = _el(p("Hdr", "8.1.3.4.2.1\tDerivation of Noc values"))
    assert H.para_style(el, styles) == (name, level) == inspect_mod.para_style(el, styles)

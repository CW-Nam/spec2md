"""End-to-end conversion of a small synthetic spec (output-contract.md sections 2-5)."""
import os
import subprocess
import sys

import pytest

from conftest import CHECK, INSPECT
from docx_builder import PNG, build, cell, cover, drawing, ole, p, row, run, table

BR = "<w:r><w:br/></w:r>"
NBH = "<w:r><w:noBreakHyphen/></w:r>"
INLINE_MATH = ('<m:oMath><m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr>'
               '<m:t>RB</m:t></m:r></m:sub></m:sSub></m:oMath>')
DISPLAY_MATH = ('<m:oMathPara><m:oMath><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t>'
                '</m:r></m:den></m:f></m:oMath></m:oMathPara>')


def sample_body():
    merged = table(
        3,
        row(cell(p("TAH", "A"), tcpr='<w:gridSpan w:val="2"/>'), cell(p("TAH", "B"))),
        row(cell(p("TAL", "C"), tcpr='<w:vMerge w:val="restart"/>'), cell(p("TAL", "D")),
            cell(p("TAL", "x<y & z"))),
        row(cell(p("TAL"), tcpr="<w:vMerge/>"), cell(p("TAL", "F")), cell(p("TAL", "G"))),
        row(cell(p("TAL", "H")), cell(p("TAL", "I", drawing("rIdImg"))), trpr='<w:gridBefore w:val="1"/>'),
    )
    simple = table(
        2,
        row(cell(p("TAH", "Field")), cell(p("TAH", "Description"))),
        row(cell(p("TAL", "a|b")), cell(p("TAL", "line 1"), p("TAL", "line 2"))),
    )
    return "".join([
        cover("18.1.0", "38.999"),
        p("Heading1", "Foreword"),
        p("Normal", "This is the foreword."),
        p("Heading1", BR, "1\tScope"),
        p("Normal", "Scope text with K", run("AMF", '<w:vertAlign w:val="subscript"/>'), " and 2",
          run("24", '<w:vertAlign w:val="superscript"/>'), " and 2", run("8", '<w:rStyle w:val="SupChar"/>'),
          "."),
        p("Normal", "hidden", run("SECRET", "<w:vanish/>"), " end", "<w:del><w:r><w:delText>gone</w:delText></w:r></w:del>",
          "<w:ins>", run(" inserted"), "</w:ins>"),
        p("Normal", '<w:hyperlink r:id="x">', run("linked text"), "</w:hyperlink>",
          " non", NBH, "specific ", '<w:r><w:sym w:font="Symbol" w:char="F061"/></w:r>',
          run("", '<w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/>')),
        p("Heading1", "5\tProcedures"),
        p("Heading2", "5.1\tGeneral"),
        p("Heading3", "5.1.1\tInitiation"),
        p("B1", "1>\tif the condition holds:"),
        p("B2", "2>\tdo the thing;"),
        p("B7", "7>\tdeep item"),
        p("NO", "NOTE:\tThis is a note."),
        p("EX", "RRC\tRadio Resource Control"),
        p("EW", "5G-GUTI"),
        p("Normal", "The value ", INLINE_MATH, " is used."),
        p("EQ", "\t", DISPLAY_MATH),
        p("TH", "Table 5.1.1-1: Merged"),
        merged,
        p("TH", "Table 5.1.1-2: Simple"),
        simple,
        p("TH", drawing("rIdImg")),
        p("TF", "Figure 5.1.1-1: A figure"),
        p("Normal", "Equation object ", ole("rIdEq", "Equation.3"), " here."),
        p("Heading4", "5.1.1.1\tDeeper clause"),
        p("Normal", "Deeper text."),
        p("Heading4", "5.1.1.2a\tLetter suffix"),
        p("Normal", "Suffix text."),
        p("Heading3", "5.1.2\tVoid"),
        p("Heading2", "5.2\tMessages"),
        p("Heading3", "–\tRRCSetup"),
        p("TH", "RRCSetup message"),
        p("PL", "-- ASN1START"),
        p("PL", "RRCSetup ::= SEQUENCE {"),
        p("PL", "\tfield\tINTEGER"),
        p("PL"),
        p("PL", "}"),
        p("PL", "-- ASN1STOP"),
        p("Weird", "Unknown style text"),
        p("Heading8", "Annex A (normative):", BR, "Measurement channels"),
        p("Heading1", "A.1\tGeneral"),
        p("Normal", "Annex text."),
        p("Heading8", "Annex B (informative):", BR, "Change history:"),
        table(1, row(cell(p("TAL", "2026-01")), cell(p("TAL", "CR0001")))),
        p("Normal", "History text."),
        p("Heading1", "B.1	Old versions"),
        p("Normal", "Old history."),
    ])


@pytest.fixture
def sample(tmp_path):
    media = {"rIdImg": ("image1.png", PNG), "rIdEq": ("image2.wmf", b"WMF")}
    return build(tmp_path / "38999-i10.docx", sample_body(), media)


def test_manifest_and_metadata(sample, convert):
    out, conv = convert(sample, split_depth=3)
    m = out.manifest
    assert m["spec"] == "TS 38.999" and m["spec_number"] == "38.999"
    assert m["version"] == "18.1.0" and m["release"] == "Rel-18"
    assert m["source_files"] == ["38999-i10.docx"]
    assert m["split_depth"] == 3
    assert m["skipped"] == ["cover", "contents", "change history"]
    keys = [c["clause"] for c in m["clauses"]]
    assert keys == ["foreword", "1", "5", "5.1", "5.1.1", "5.1.2", "5.2", "rrcsetup", "A", "A.1"]
    assert [c["order"] for c in m["clauses"]] == list(range(1, 11))
    e = out.entry("5.1.1")
    assert e["level"] == 3 and e["parent"] == "5.1" and e["tables"] == 2
    assert e["figures"] == 2 and e["equations"] == 3 and e["code_blocks"] == 0
    assert e["file"] == "clauses/0005_5.1.1_initiation.md"
    assert out.entry("5")["file"] is None          # heading with no own content
    assert out.entry("5.1.2")["file"] is None      # Void
    ie = out.entry("rrcsetup")
    assert ie["title"] == "RRCSetup" and ie["parent"] == "5.2" and ie["code_blocks"] == 1
    assert ie["file"] == "clauses/0008_rrcsetup.md"
    assert out.entry("A")["level"] == 1 and out.entry("A")["title"] == "Measurement channels"
    assert out.entry("A.1")["level"] == 2 and out.entry("A.1")["parent"] == "A"
    assert conv.summary["unhandled_styles"] == {"Weird Style": 1}


def test_front_matter(sample, convert):
    out, _ = convert(sample)
    text = out.text("A.1")
    fm = text.split("\n---\n", 1)[0]
    assert fm.splitlines() == [
        "---",
        'spec: "TS 38.999"',
        'spec_number: "38.999"',
        'version: "18.1.0"',
        'release: "Rel-18"',
        'clause: "A.1"',
        'title: "General"',
        "level: 2",
        'parent: "A"',
        'path: ["Annex A (normative): Measurement channels", "A.1 General"]',
        'source_file: "38999-i10.docx"',
    ]
    assert "\r" not in text and not text.startswith("﻿")


def test_inline_formatting(sample, convert):
    out, _ = convert(sample)
    body = out.body("1")
    assert body.startswith("# 1 Scope\n")
    assert "K<sub>AMF</sub>" in body and "2<sup>24</sup>" in body and "2<sup>8</sup>" in body
    assert "hidden end inserted" in body and "SECRET" not in body and "gone" not in body
    assert "linked text non-specific αβ" in body


def test_lists_notes_definitions(sample, convert):
    body = convert(sample)[0].body("5.1.1")
    assert "\n1> if the condition holds:\n" in body
    assert "\n  2> do the thing;\n" in body
    assert "\n            7> deep item\n" in body
    assert "\n> NOTE: This is a note.\n" in body
    assert "\n- **RRC**: Radio Resource Control\n" in body
    assert "\n- **5G-GUTI**\n" in body


def test_math(sample, convert):
    body = convert(sample)[0].body("5.1.1")
    assert r"The value ${N}_{\text{RB}}$ is used." in body
    assert "\n$$\n\\frac{a}{b}\n$$\n" in body
    assert "Equation object ![equation](../media/image2.wmf) here." in body


def test_tables_and_captions(sample, convert):
    out, _ = convert(sample)
    body = out.body("5.1.1")
    assert "**Table 5.1.1-1: Merged**\n\n<table>\n" in body
    assert '<tr><th colspan="2">A</th><th>B</th></tr>' in body
    assert '<tr><td rowspan="2">C</td><td>D</td><td>x&lt;y &amp; z</td></tr>' in body
    assert "<tr><td>F</td><td>G</td></tr>" in body
    assert '<tr><td></td><td>H</td><td>I<img src="../media/image1.png" alt="Figure"></td></tr>' in body
    assert ("**Table 5.1.1-2: Simple**\n\n| Field | Description |\n| --- | --- |\n"
            "| a\\|b | line 1<br>line 2 |") in body
    # empty-text TH holding a figure -> the figure only; TF caption in place
    assert "\n![Figure](../media/image1.png)\n\n*Figure 5.1.1-1: A figure*\n" in body
    assert os.path.isfile(os.path.join(out.path, "media", "image1.png"))
    assert sorted(os.listdir(os.path.join(out.path, "media"))) == ["image1.png", "image2.wmf"]


def test_deeper_headings_inside_file(sample, convert):
    body = convert(sample, split_depth=3)[0].body("5.1.1")
    assert "\n## 5.1.1.1 Deeper clause\n\nDeeper text.\n" in body
    assert "\n## 5.1.1.2a Letter suffix\n" in body


def test_asn1_block(sample, convert):
    body = convert(sample)[0].body("rrcsetup")
    assert ("**RRCSetup message**\n\n```asn1\n-- ASN1START\nRRCSetup ::= SEQUENCE {\n\tfield\tINTEGER\n\n}\n"
            "-- ASN1STOP\n```") in body


def test_split_depth_4(sample, convert):
    out, _ = convert(sample, split_depth=4)
    keys = [c["clause"] for c in out.clauses]
    assert "5.1.1.1" in keys and "5.1.1.2a" in keys
    assert out.entry("5.1.1.2a")["parent"] == "5.1.1"
    assert "auto_split" not in out.entry("5.1.1.1")


def test_max_chars_auto_split(sample, convert):
    out, _ = convert(sample, split_depth=3, max_chars=300)
    keys = [c["clause"] for c in out.clauses]
    assert keys.index("5.1.1") < keys.index("5.1.1.1") < keys.index("5.1.1.2a") < keys.index("5.1.2")
    assert out.entry("5.1.1.1")["auto_split"] is True and out.entry("5.1.1.1")["level"] == 4
    assert "5.1.1.1 Deeper" not in out.body("5.1.1")


def test_deterministic(sample, tmp_path):
    from spec2md.convert import SpecConverter

    def snapshot(root):
        SpecConverter([str(sample)], str(root), quiet=True).run()
        files = {}
        for d, _, fs in os.walk(root):
            for f in fs:
                p = os.path.join(d, f)
                files[os.path.relpath(p, root)] = open(p, "rb").read()
        return files
    assert snapshot(tmp_path / "a") == snapshot(tmp_path / "b")


def test_reference_scripts_agree(sample, convert, tmp_path):
    """inspect_docx.py outline == our manifest, and check_output.py passes."""
    out, _ = convert(sample, split_depth=3)
    ij = tmp_path / "inspect.json"
    subprocess.run([sys.executable, INSPECT, str(sample), "--json", str(ij)], check=True,
                   capture_output=True)
    r = subprocess.run([sys.executable, CHECK, "--inspect", str(ij), "--out", out.path],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "errors=0" in r.stdout
    assert "tables: source 3 vs manifest 2" in r.stdout  # change history table not counted


def test_python_docx_opens_fixture(sample):
    import docx
    d = docx.Document(str(sample))
    assert any(par.style.name.lower() == "heading 1" for par in d.paragraphs)

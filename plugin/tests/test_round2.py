"""Round 2 fixes: drawings in captions, math spacing, auto-numbered paragraphs, B lists in cells."""
import pytest

from docx_builder import PNG, build, cell, drawing, p, row, run, table

WPS = 'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
WPG = 'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"'


def textbox_shape(inner):
    return f'<wps:wsp {WPS}><wps:txbx><w:txbxContent>{inner}</w:txbxContent></wps:txbx></wps:wsp>'


def group_with_images(rid):
    """mc:AlternateContent: a group of two text boxes that each hold the same picture, plus an
    empty shape; the VML fallback repeats everything."""
    inline_pic = drawing(rid)
    group = (f'<wpg:wgp {WPG}>{textbox_shape(p(None, inline_pic))}{textbox_shape(p(None, inline_pic))}'
             f'<wps:wsp {WPS}/></wpg:wgp>')
    choice = (f'<w:drawing><wp:anchor><a:graphic><a:graphicData>{group}</a:graphicData></a:graphic>'
              f'</wp:anchor></w:drawing>')
    fallback = (f'<w:pict><v:group><v:shape><v:textbox><w:txbxContent>{p(None, inline_pic)}</w:txbxContent>'
                f'</v:textbox></v:shape><v:shape><v:imagedata r:id="{rid}"/></v:shape></v:group></w:pict>')
    return (f'<w:r><mc:AlternateContent><mc:Choice Requires="wpg">{choice}</mc:Choice>'
            f'<mc:Fallback>{fallback}</mc:Fallback></mc:AlternateContent></w:r>')


def textbox_drawing(text):
    shape = textbox_shape(p(None, text))
    return (f'<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wp:anchor><a:graphic>'
            f'<a:graphicData>{shape}</a:graphicData></a:graphic></wp:anchor></w:drawing></mc:Choice>'
            f'<mc:Fallback><w:pict><v:shape><v:textbox><w:txbxContent>{p(None, text)}</w:txbxContent>'
            f'</v:textbox></v:shape></w:pict></mc:Fallback></mc:AlternateContent></w:r>')


EMPTY_SHAPE = ('<w:r><w:drawing><wp:anchor><a:graphic><a:graphicData>'
               f'<wps:wsp {WPS}/></a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>')


def om(t):
    return f'<m:oMath><m:r><m:t xml:space="preserve">{t}</m:t></m:r></m:oMath>'


def numpr(num, ilvl=0):
    return f'<w:numPr><w:ilvl w:val="{ilvl}"/><w:numId w:val="{num}"/></w:numPr>'


@pytest.fixture
def out(tmp_path, convert):
    body = "".join([
        p("Heading1", "1\tCaptions"),
        p("TH", group_with_images("rId5")),
        p("TF", "Figure 1-1: Grouped picture"),
        p("TH", EMPTY_SHAPE, "Table A.4-3a: Void"),
        p("TH", textbox_drawing("Box text")),
        p("TF", "Figure 1-2: Text box figure"),
        p("Normal", "Before", textbox_drawing("Inner"), "after."),
        p("Heading1", "2\tMath"),
        p("Normal", "values ", om("a"), om("b"), " and ", om("c"), "."),
        p("Normal", "for antenna port", om(" p "), "and layer", om(" v"), " only."),
        table(1, row(cell(p("TAL", "cell ", om("x"), om("y"))))),
        p("Heading1", "3\tNumbering"),
        p("Normal", "first level", ppr=numpr(1)),
        p("Normal", "second level", ppr=numpr(1, 1)),
        p("Normal", "numbering removed", ppr=numpr(0)),
        p("ListNumber", "from style"),
        p("B1", "bulleted B1", ppr=numpr(2)),
        table(1, row(cell(p("TAL", "numbered cell", ppr=numpr(1)), p("B1", "1>\tfirst"),
                          p("B2", "2>\tsecond")))),
    ])
    path = build(tmp_path / "39996-i00.docx", body, {"rId5": ("image1.png", PNG)})
    return convert(path)[0]


def test_figure_only_caption_is_not_bold_and_not_duplicated(out):
    body = out.body("1")
    assert "\n\n![Figure](../media/image1.png)\n\n*Figure 1-1: Grouped picture*\n" in body
    assert body.count("image1.png") == 1
    assert "**!" not in body and "**[" not in body and "[drawing]**" not in body


def test_placeholder_and_caption_text_on_separate_lines(out):
    body = out.body("1")
    assert "\n\n[drawing]\n\n**Table A.4-3a: Void**\n" in body
    assert "\n\n[drawing: Box text]\n\n*Figure 1-2: Text box figure*\n" in body
    assert body.count("Box text") == 1  # mc:Fallback not read
    assert "\n\nBefore\n[drawing: Inner]\nafter.\n" in body


def test_adjacent_math_and_edge_spaces(out):
    body = out.body("2")
    assert "values $a$ $b$ and $c$." in body
    assert "for antenna port $p$ and layer $v$ only." in body
    assert "| cell $x$ $y$ |" in body


def test_auto_numbered_paragraphs(out):
    body = out.body("3")
    assert "\n- first level\n" in body
    assert "\n  - second level\n" in body
    assert "\nnumbering removed\n" in body
    assert "\n- from style\n" in body
    assert "\n- bulleted B1\n" in body


def test_b_lists_in_table_cell_keep_markers(out):
    assert "| - numbered cell<br>1> first<br>2> second |" in out.body("3")


# --- Round 4: glued inline math, empty LaTeX groups -------------------------
def test_alnum_glued_to_math_gets_one_space(tmp_path, convert):
    body = "".join([
        p("Heading1", "1\tGlue"),
        p("Normal", "where", om("n=0"), "is used and", om("x"), ", not", om("y"), "."),
        p("Normal", "K", run("AMF", '<w:vertAlign w:val="subscript"/>'), om("z"), "end"),
        table(1, row(cell(p("TAL", "length", om("M"), "symbols")))),
    ])
    out = convert(build(tmp_path / "39994-i00.docx", body))[0]
    text = out.body("1")
    assert "where $n=0$ is used and $x$, not $y$." in text
    assert "K<sub>AMF</sub> $z$ end" in text
    assert "| length $M$ symbols |" in text


def test_empty_groups_are_dropped():
    from lxml import etree
    from docx_builder import NS
    from spec2md.omml import OmmlConverter, strip_empty
    assert strip_empty(r"x\begin{matrix}\end{matrix}") == "x"
    assert strip_empty(r"\left( a \right){}") == r"\left( a \right)"
    assert strip_empty(r"{}_{a}^{b}{X}") == r"{}_{a}^{b}{X}"
    om_xml = (f"<m:oMath {NS}><m:r><m:t>max</m:t></m:r><m:m><m:mr><m:e/></m:mr></m:m>"
              f"<m:box><m:e/></m:box></m:oMath>")
    assert OmmlConverter().convert(etree.fromstring(om_xml)) == "max"

import os

from raw_builder import make_spec
from spec2md.link_index import CorpusIndex, Target, build_corpus_index
from spec2md.link_refs import find_refs
from spec2md.link_render import Backlink, href, render

FILE = "clauses/0003_4.2_t.md"
PREFIX = "../../../raw/38213-j50/media/"

BODY = (
    "see Table 4.2-1 for details, and Table 4.2-9 is unknown.\n\n"
    "**Table 4.2-1: Foo $x$**\n\n"
    "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
    "<table><tr><td>see Table 4.2-1<br>$a<b$</td></tr></table>\n\n"
    "![Figure](../media/image1.png)\n\n"
    '<img src="../media/image2.emf">\n'
)


def _setup(tmp_path):
    make_spec(tmp_path, "38213-j50", "38.213", "19.0.0", [
        {"clause": "4.2", "title": "T", "level": 2, "parent": None, "file": FILE, "body": BODY},
    ])
    corpus = build_corpus_index(str(tmp_path))
    spec = corpus.specs["38213-j50"]
    with open(os.path.join(str(tmp_path), "38213-j50", *FILE.split("/")), encoding="utf-8") as f:
        text = f.read()
    return text, spec, corpus


def _render(tmp_path, backlinks=()):
    text, spec, corpus = _setup(tmp_path)
    refs = find_refs(text, spec, corpus)
    return render(text, refs, spec, FILE, PREFIX, list(backlinks))


def test_markdown_link_and_anchor(tmp_path):
    out = _render(tmp_path)
    assert '<a id="table-4.2-1"></a>\n**Table 4.2-1: Foo $x$**' in out
    assert "see [Table 4.2-1](0003_4.2_t.md#table-4.2-1) for" in out
    assert out.count('<a id="table-4.2-1"></a>') == 1


def test_cross_spec_href():
    assert href("38213-j50", "clauses/a.md", "38214-j50",
                Target("clauses/b.md", "clause-5.1.2", 9)) == "../../38214-j50/clauses/b.md#clause-5.1.2"
    assert href("38213-j50", "clauses/a.md", "38213-j50",
                Target("clauses/0123_8.1_x.md", "table-8.1-2", 9)) == "0123_8.1_x.md#table-8.1-2"
    assert href("38213-j50", "clauses/a.md", "38213-j50",
                Target("clauses/b.md", None, 1)) == "b.md"


def test_html_cell_uses_anchor_tag(tmp_path):
    out = _render(tmp_path)
    assert '<td>see <a href="0003_4.2_t.md#table-4.2-1">Table 4.2-1</a><br>$a<b$</td>' in out


def test_unresolved_not_linked(tmp_path):
    out = _render(tmp_path)
    assert "and Table 4.2-9 is unknown." in out
    assert "[Table 4.2-9]" not in out and "4.2-9)" not in out


def test_media_rewrite(tmp_path):
    out = _render(tmp_path)
    assert "![Figure](../../../raw/38213-j50/media/image1.png)" in out
    assert 'src="../../../raw/38213-j50/media/image2.emf"' in out
    assert "../media/" not in out


def test_backlinks_section(tmp_path):
    bl = [Backlink("38321-j40", "38.321", "clauses/0123_5.17_x.md", "5.17",
                   "Table 8.1-2", "table-4.2-1")]
    out = _render(tmp_path, bl)
    assert out.endswith(
        "<!-- spec2md:backlinks -->\n## Referenced by\n\n"
        "- [TS 38.321 5.17](../../38321-j40/clauses/0123_5.17_x.md) — Table 8.1-2\n")


def test_backlinks_sorted_and_deduped(tmp_path):
    a = Backlink("38321-j40", "38.321", "clauses/b.md", "5.1", "Table 2-1", "x")
    b = Backlink("38213-j50", "38.213", "clauses/z.md", "9.1", "Table 1-1", "x")
    c = Backlink("38213-j50", "38.213", "clauses/z.md", "9.1", "Table 1-1", "x")
    d = Backlink("38213-j50", "38.213", "clauses/z.md", "9.1", "Table 1-1", "y")
    out = _render(tmp_path, [a, b, c, d])
    tail = out.split("## Referenced by\n\n")[1].split("\n")
    assert tail == [
        "- [TS 38.213 9.1](z.md) — Table 1-1",
        "- [TS 38.213 9.1](z.md) — Table 1-1",
        "- [TS 38.321 5.1](../../38321-j40/clauses/b.md) — Table 2-1",
        "",
    ]


def test_no_backlinks_no_section_and_deterministic(tmp_path):
    out = _render(tmp_path)
    assert "spec2md:backlinks" not in out
    assert out == _render(tmp_path)
    assert "\\" not in out.replace("\\n", "")


def test_multiple_anchors_one_line_each_sorted(tmp_path):
    text = "x\n**Table 1-1: A**\n"
    from spec2md.link_index import SpecIndex
    spec = SpecIndex("c", "1.1", "1.0.0", "Rel-1")
    spec.tables["1-1"] = Target("f.md", "table-1-1", 2)
    spec.clauses["1"] = Target("f.md", "clause-1", 2)
    spec.tables["9-9"] = Target("other.md", "table-9-9", 2)
    out = render(text, [], spec, "f.md", "m/", [])
    assert out == 'x\n<a id="clause-1"></a>\n<a id="table-1-1"></a>\n**Table 1-1: A**\n'

import pytest

from raw_builder import make_spec
from spec2md.link_index import Target, anchor_id, build_corpus_index, build_spec_index

REFS = (
    'Intro.\n\n- **[5]**: 3GPP TS 38.211: "NR; Physical channels".\n\n'
    '- **[6]**: 3GPP TS 38.214: "NR; Physical layer procedures for data".\n\n'
    '- **[7]**: 3GPP TR 21.905: "Vocabulary".\n'
)
BODY_42 = (
    "Text.\n\n**Table 4.2-1: Foo $x$**\n\n| a | b |\n| - | - |\n\n"
    "*Figure 4.2-1: Bar*\n\n## 4.2.1 Sub\n\nMore.\n"
)
BODY_81 = "**Table 8.1-2: A**\n\n| a |\n| - |\n\n**Table 8.1-2: A**\n\n| a |\n"


def _clauses():
    return [
        dict(clause="2", title="References", level=1, parent=None, file="clauses/0001_2_references.md", body=REFS),
        dict(clause="4", title="Four", level=1, parent=None, file=None, body=""),
        dict(clause="4.2", title="T", level=2, parent="4", file="clauses/0003_4.2_t.md", body=BODY_42),
        dict(clause="8.1", title="U", level=2, parent="8", file="clauses/0004_8.1_u.md", body=BODY_81),
    ]


@pytest.fixture
def idx(tmp_path):
    return build_spec_index(make_spec(tmp_path, "38213-j50", "38.213", "19.5.0", _clauses()))


def test_tables_figures_subclauses(idx):
    t = idx.tables["4.2-1"]
    assert (t.file, t.anchor) == ("clauses/0003_4.2_t.md", "table-4.2-1")
    assert idx.figures["4.2-1"].anchor == "figure-4.2-1"
    assert idx.clauses["4.2.1"].anchor == "clause-4.2.1"
    assert idx.clauses["4.2"].anchor is None


def test_fileless_clause_points_to_first_descendant(idx):
    assert idx.clauses["4"] == Target("clauses/0003_4.2_t.md", None, 1)


def test_duplicate_caption_is_ambiguous(idx):
    assert idx.tables["8.1-2"].ambiguous
    assert not idx.tables["4.2-1"].ambiguous


def test_references(idx):
    assert idx.references["6"] == "38.214"
    assert idx.references["7"] == "21.905"


def test_metadata_and_lines(idx):
    assert (idx.code, idx.spec_number, idx.version, idx.release) == ("38213-j50", "38.213", "19.5.0", "Rel-19")
    assert idx.files == ["clauses/0001_2_references.md", "clauses/0003_4.2_t.md", "clauses/0004_8.1_u.md"]
    t = idx.tables["4.2-1"]
    assert t.line > 1


def test_line_points_at_caption(tmp_path):
    d = make_spec(tmp_path, "38213-j50", "38.213", "19.5.0", _clauses())
    idx = build_spec_index(d)
    text = open(d + "/" + idx.tables["4.2-1"].file, encoding="utf-8").read().split("\n")
    assert text[idx.tables["4.2-1"].line - 1].startswith("**Table 4.2-1")
    assert text[idx.clauses["4.2.1"].line - 1].startswith("## 4.2.1 ")


def test_corpus_prefers_highest_version(tmp_path):
    make_spec(tmp_path, "38214-j40", "38.214", "19.4.0", _clauses())
    make_spec(tmp_path, "38214-j50", "38.214", "19.5.0", _clauses())
    (tmp_path / "not_a_spec").mkdir()
    c = build_corpus_index(str(tmp_path))
    assert c.by_number["38.214"] == "38214-j50"
    assert set(c.specs) == {"38214-j40", "38214-j50"}


def test_anchor_id():
    assert anchor_id("table", "8.1-2") == "table-8.1-2"

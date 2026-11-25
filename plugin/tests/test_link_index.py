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


# --- Task 9: real-corpus index gaps ---------------------------------------------

def test_fileless_clause_with_unnumbered_children(tmp_path):
    # 36331-j40: "6.3.2 Radio resource control information elements" has no body; its children are
    # IE headings ("AntennaInfo" ...) whose clause key is the IE name and whose parent is "6.3.2".
    d = make_spec(tmp_path, "36331-j40", "36.331", "19.4.0", [
        dict(clause="6.3", title="RRC information elements", level=2, parent="6", file=None, body=""),
        dict(clause="6.3.1", title="System information blocks", level=3, parent="6.3", file=None, body=""),
        dict(clause="systeminformationblocktype2", title="SystemInformationBlockType2", level=4,
             parent="6.3.1", file="clauses/0602_systeminformationblocktype2.md", body="x\n"),
        dict(clause="6.3.2", title="Radio resource control information elements", level=3, parent="6.3",
             file=None, body=""),
        dict(clause="antennainfo", title="AntennaInfo", level=4, parent="6.3.2",
             file="clauses/0663_antennainfo.md", body="x\n"),
        dict(clause="6.3.9", title="Empty", level=3, parent="6.3", file=None, body=""),
    ])
    idx = build_spec_index(d)
    assert idx.clauses["6.3.2"] == Target("clauses/0663_antennainfo.md", None, 1)
    assert idx.clauses["6.3"] == Target("clauses/0602_systeminformationblocktype2.md", None, 1)
    assert "6.3.9" not in idx.clauses


def test_caption_number_variants(tmp_path):
    body = (
        # 36212-j30: base table and its continuation tables "-2E-1", "-2E-2"
        "**Table 5.2.2.6.2-2E: Fields for channel quality information feedback**\n\n| a |\n| - |\n\n"
        "**Table 5.2.2.6.2-2E-1: Fields for channel quality information feedback**\n\n| a |\n| - |\n\n"
        # 36101-j60: "1a" and "1aa"
        "**Table 7.3.1-1a: R**\n\n| a |\n| - |\n\n**Table 7.3.1-1aa: R8**\n\n| a |\n| - |\n\n"
        # 36213-j50: "**Table 7.2.2-1 H: Joint encoding ...**" next to a real "**Table 7.2.2-1H: ...**":
        # the spaced form is not indexed (neither as 7.2.2-1 nor as 7.2.2-1H)
        "**Table 7.2.2-1: CQI and PMI Feedback Types**\n\n| a |\n| - |\n\n"
        "**Table 7.2.2-1 H: Joint encoding of RI**\n\n| a |\n| - |\n\n"
        "**Table 7.2.2-1H: PUCCH mode 1-1 codebook subsampling**\n\n| a |\n| - |\n"
    )
    d = make_spec(tmp_path, "36212-j30", "36.212", "19.3.0", [
        dict(clause="5.2", title="T", level=2, parent="5", file="clauses/0001_5.2_t.md", body=body)])
    idx = build_spec_index(d)
    for k in ["5.2.2.6.2-2E", "5.2.2.6.2-2E-1", "7.3.1-1a", "7.3.1-1aa", "7.2.2-1", "7.2.2-1H"]:
        assert k in idx.tables and not idx.tables[k].ambiguous, k
    assert idx.tables["7.2.2-1H"].line > idx.tables["7.2.2-1"].line + 4


def test_fileless_clause_followed_by_unnumbered_sibling(tmp_path):
    # 36331-j40: "6.7.3.2 NB-IoT Radio resource control information elements" (level 4, no body) is
    # followed by IE headings that the converter put at the same level under parent 6.7.3.
    d = make_spec(tmp_path, "36331-j40", "36.331", "19.4.0", [
        dict(clause="6.7.3", title="NB-IoT information elements", level=3, parent="6.7", file=None, body=""),
        dict(clause="6.7.3.2", title="NB-IoT Radio resource control information elements", level=4,
             parent="6.7.3", file=None, body=""),
        dict(clause="carrierconfigdedicated-nb", title="CarrierConfigDedicated-NB", level=4, parent="6.7.3",
             file="clauses/1046_carrierconfigdedicated-nb.md", body="x\n"),
        dict(clause="6.7.4", title="Empty", level=3, parent="6.7", file=None, body=""),
        dict(clause="6.7.5", title="Next", level=3, parent="6.7", file="clauses/1100_6.7.5_next.md", body="x\n"),
    ])
    idx = build_spec_index(d)
    assert idx.clauses["6.7.3.2"] == Target("clauses/1046_carrierconfigdedicated-nb.md", None, 1)
    assert "6.7.4" not in idx.clauses    # a numbered sibling is not a child

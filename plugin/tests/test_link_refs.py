import pytest

from raw_builder import make_spec
from spec2md.link_index import build_corpus_index
from spec2md.link_refs import Ref, find_refs, protected_spans

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
BODY_5121 = "**Table 5.1.2.1-2: X**\n\n| a |\n| - |\n"


def _clauses_213():
    return [
        dict(clause="2", title="References", level=1, parent=None, file="clauses/0001_2_references.md", body=REFS),
        dict(clause="4", title="Four", level=1, parent=None, file=None, body=""),
        dict(clause="4.2", title="T", level=2, parent="4", file="clauses/0003_4.2_t.md", body=BODY_42),
        dict(clause="8.1", title="U", level=2, parent="8", file="clauses/0004_8.1_u.md", body=BODY_81),
        dict(clause="9", title="Nine", level=1, parent=None, file=None, body=""),
        dict(clause="B", title="Annex B", level=1, parent=None, file="clauses/0006_b_annex-b.md", body="Text.\n"),
    ]


def _clauses_214():
    return [
        dict(clause="2", title="References", level=1, parent=None, file="clauses/0001_2_references.md", body=""),
        dict(clause="5.1.2", title="R", level=3, parent="5.1", file="clauses/0002_5.1.2_r.md", body=""),
        dict(clause="5.1.2.1", title="S", level=4, parent="5.1.2", file="clauses/0003_5.1.2.1_s.md", body=BODY_5121),
        dict(clause="9.1.5", title="V", level=3, parent="9.1", file="clauses/0004_9.1.5_v.md", body=""),
    ]


@pytest.fixture
def c(tmp_path):
    make_spec(tmp_path, "38213-j50", "38.213", "19.5.0", _clauses_213())
    make_spec(tmp_path, "38214-j50", "38.214", "19.5.0", _clauses_214())
    return build_corpus_index(str(tmp_path))


def find(c, s):
    return find_refs(s, c.specs["38213-j50"], c)


def ids(refs):
    return [(r.kind, r.target_id, r.target_spec_number, r.status) for r in refs]


# --- brief tests ---------------------------------------------------------------

def test_same_spec_table(c):
    assert ids(find(c, "see Table 4.2-1 for")) == [("table", "4.2-1", "38.213", "resolved")]


def test_list_and_elided(c):
    assert [r.text for r in find(c, "Tables 4.2-1 and 4.2-2")] == ["Tables 4.2-1", "4.2-2"]
    assert find(c, "Tables 4.2-1 and 4.2-2")[1].status == "missing_target"
    assert [r.target_id for r in find(c, "Table 4.2-1 and 8.1-2")] == ["4.2-1", "8.1-2"]


def test_range_ends_only(c):
    assert [r.target_id for r in find(c, "Tables 4.2-1 to 4.2-9")] == ["4.2-1", "4.2-9"]


def test_cross_spec_forms(c):
    for s in ["clause 5.1.2 of [6]", "clause 5.1.2 in TS 38.214 [6]", "TS 38.214 [6], clause 5.1.2",
              "[6], clause 5.1.2", "clause 5.1.2 of TS 38.214", "[6, TS 38.214], clause 5.1.2"]:
        assert ids(find(c, s)) == [("clause", "5.1.2", "38.214", "resolved")], s


def test_number_shapes(c):
    assert find(c, "in TS 38.214 [6] clause 9.1.5.")[0].target_id == "9.1.5"
    assert [r.target_id for r in find(c, "Table 5.2.2.2.1a-5, Table A.2-1, clause 4.3A")] == [
        "5.2.2.2.1a-5", "A.2-1", "4.3A"]


def test_missing_spec(c):
    assert ids(find(c, "clause 9.1 of TS 36.133"))[0][3] == "missing_spec"


def test_ambiguous(c):
    assert find(c, "Table 8.1-2")[0].status == "ambiguous"


def test_protected(c):
    for s in ["```text\nTable 4.2-1\n```", "$Table 4.2-1$", "**Table 4.2-1: caption**", "## 4.2 Table 4.2-1",
              '<img alt="Table 4.2-1">']:
        assert find(c, s) == [], s


def test_annex(c):
    assert ids(find(c, "see Annex B"))[0][:2] == ("clause", "B")


# --- extra tests ---------------------------------------------------------------

def test_ref_fields_and_positions(c):
    s = "Line one.\nsee Table 4.2-1 and clause 5.1.2 of [6]."
    refs = find(c, s)
    assert [s[r.start:r.end] for r in refs] == [r.text for r in refs] == ["Table 4.2-1", "clause 5.1.2"]
    assert [r.line for r in refs] == [2, 2]
    t = refs[0]
    assert t.target_code == "38213-j50" and t.target is c.specs["38213-j50"].tables["4.2-1"]
    x = refs[1]
    assert x.target_code == "38214-j50" and x.target == c.specs["38214-j50"].clauses["5.1.2"]
    assert isinstance(t, Ref)


def test_sorted_by_start(c):
    refs = find(c, "clause 9.1.5 of [6], Table 4.2-1, Figure 4.2-1 and Annex B")
    assert [r.start for r in refs] == sorted(r.start for r in refs)
    assert ids(refs) == [
        ("clause", "9.1.5", "38.214", "resolved"),
        ("table", "4.2-1", "38.213", "resolved"),
        ("figure", "4.2-1", "38.213", "resolved"),
        ("clause", "B", "38.213", "resolved"),
    ]


def test_list_designator_applies_to_all_items(c):
    assert ids(find(c, "clauses 5.1.2 and 9.1.5 of [6]")) == [
        ("clause", "5.1.2", "38.214", "resolved"), ("clause", "9.1.5", "38.214", "resolved")]
    assert ids(find(c, "[6], Tables 5.1.2.1-2, 5.1.2.1-3 or 5.1.2.1-4")) == [
        ("table", "5.1.2.1-2", "38.214", "resolved"),
        ("table", "5.1.2.1-3", "38.214", "missing_target"),
        ("table", "5.1.2.1-4", "38.214", "missing_target")]


def test_comma_without_conjunction_is_not_list(c):
    assert [r.text for r in find(c, "in clause 4.2, 4 symbols")] == ["clause 4.2"]
    assert [r.text for r in find(c, "Table 4.2-1, 8.1-2")] == ["Table 4.2-1"]


def test_designated_list_tail_kept_and_resolved_in_target_spec(c):
    assert ids(find(c, "Tables 4.2-1, 4.2-2 of [6]")) == [
        ("table", "4.2-1", "38.214", "missing_target"), ("table", "4.2-2", "38.214", "missing_target")]
    assert [r.target_spec_number for r in find(c, "Tables 4.2-1, 4.2-2 of [6]")] == ["38.214", "38.214"]
    refs = find(c, "clause 4.2 and 6 of [6]")
    assert [(r.text, r.target_spec_number) for r in refs] == [("clause 4.2", "38.214"), ("6", "38.214")]
    assert ids(find(c, "clauses 5.1.2, 9.1.5 in TS 38.214")) == [
        ("clause", "5.1.2", "38.214", "resolved"), ("clause", "9.1.5", "38.214", "resolved")]


def test_comma_tail_without_designator_still_not_list(c):
    refs = find(c, "Tables 4.2-1, 4.2-2 for x")
    assert [(r.text, r.target_spec_number) for r in refs] == [("Tables 4.2-1", "38.213")]


def test_singular_clause_elision_needs_dot(c):
    assert [r.text for r in find(c, "clause 4.2 and 6 PRBs")] == ["clause 4.2"]
    assert [r.text for r in find(c, "clauses 4 and 9")] == ["clauses 4", "9"]


def test_missing_and_fileless_clauses(c):
    # clause 4 has no file but a file-bearing descendant; clause 9 has neither.
    assert ids(find(c, "clause 4 and clause 9")) == [
        ("clause", "4", "38.213", "resolved"), ("clause", "9", "38.213", "missing_target")]
    r = find(c, "Figure 9.9-1")[0]
    assert (r.status, r.target, r.target_code) == ("missing_target", None, "38213-j50")


def test_missing_spec_fields(c):
    r = find(c, "clause 9.1 of TS 36.133")[0]
    assert (r.target_spec_number, r.target_code, r.target) == ("36.133", None, None)
    r = find(c, "clause 9.1 of [99]")[0]
    assert r.status == "missing_spec" and r.target_code is None


def test_ambiguous_has_no_target(c):
    r = find(c, "Table 8.1-2")[0]
    assert r.target is None and r.target_code == "38213-j50"


def test_trailing_punctuation_and_spacing(c):
    assert [r.target_id for r in find(c, "see clause 4.2, and Table 4.2-1.")] == ["4.2", "4.2-1"]
    assert ids(find(c, "Table 4.2-1")) == [("table", "4.2-1", "38.213", "resolved")]
    assert find(c, "Table 4.2-1abc") == []


def test_subclause_and_section(c):
    assert [r.target_id for r in find(c, "subclause 4.2 and section 8.1")] == ["4.2", "8.1"]
    assert find(c, "the clause is") == [] and find(c, "section The") == []


def test_protected_spans_shapes():
    fm = '---\nclause: "Table 4.2-1"\n---\n'
    s = fm + "a $$\nTable 4.2-1\n$$ b <td>x</td> $y$\n"
    spans = protected_spans(s)
    assert spans[0] == (0, len(fm))
    covered = lambda i: any(a <= i < b for a, b in spans)
    assert covered(s.index("Table 4.2-1", len(fm)))
    assert covered(s.index("<td>")) and covered(s.index("$y$"))
    assert not covered(s.index("a $$")) and not covered(s.index(" b "))
    assert spans == sorted(spans)


def test_front_matter_and_math_in_html(c):
    s = '---\ntitle: "Table 4.2-1"\n---\n# 4.2 T\n\n<td>see Table 4.2-1<br>$a<b$</td>\n'
    refs = find(c, s)
    assert [(r.text, r.line) for r in refs] == [("Table 4.2-1", 6)]
    assert s[refs[0].start:refs[0].end] == "Table 4.2-1"


def test_unclosed_fence_protects_rest(c):
    assert find(c, "```\nTable 4.2-1\n") == []

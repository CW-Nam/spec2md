import pytest

from raw_builder import make_spec
from spec2md.link_index import build_corpus_index
from spec2md.link_refs import Ref, find_refs, protected_spans

REFS = (
    'Intro.\n\n- **[5]**: 3GPP TS 38.211: "NR; Physical channels".\n\n'
    '- **[6]**: 3GPP TS 38.214: "NR; Physical layer procedures for data".\n\n'
    '- **[7]**: 3GPP TR 21.905: "Vocabulary".\n'
)
BODY_42 = (
    "Text.\n\n**Table 4.2-1: Foo $x$**\n\n| a | b |\n| - | - |\n\n"
    "*Figure 4.2-1: Bar*\n\n## 4.2.1 Sub\n\nMore.\n"
)
BODY_81 = "**Table 8.1-2: A**\n\n| a |\n| - |\n\n**Table 8.1-2: A**\n\n| a |\n"
BODY_5121 = "**Table 5.1.2.1-2: X**\n\n| a |\n| - |\n"
BODY_61 = ("**Table 6.1.2.1.1-2: X**\n\n| a |\n| - |\n\n**Table 6.1.2.1.1-3: Y**\n\n| a |\n| - |\n\n"
           "**Table 6.1.2.1.1-4: Z**\n\n| a |\n| - |\n")


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
        dict(clause="6.1", title="W", level=2, parent="6", file="clauses/0005_6.1_w.md", body=BODY_61),
        dict(clause="6.2.1", title="X", level=3, parent="6.2", file="clauses/0006_6.2.1_x.md", body=""),
        dict(clause="7", title="Y", level=1, parent=None, file="clauses/0007_7_y.md", body=""),
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


# --- Task 9: real-corpus sentences ------------------------------------------------
# Wrong-link class: the text names another document that the old designator pattern
# missed, so the number was resolved inside the current spec.

def test_designator_variants_resolve_in_named_spec(c):
    # 38212-j40: "as defined in clause 7 of [6, TS38.214]."
    assert ids(find(c, "as defined in clause 7 of [6, TS38.214]. If"))[0] == (
        "clause", "7", "38.214", "resolved")
    # 38211-j50: "configured as described in clause 8.1 of [5 TS 38.213]."
    assert ids(find(c, "as described in clause 6.1 of [5 TS 38.214]. The"))[0] == (
        "clause", "6.1", "38.214", "resolved")
    # 38212-j40 / 38213-j50: "[6. TS 38.214]", "[6, 38.213]", "[TS 38.211]"
    for s in ["clause 6.2.1 of [6. TS 38.214]", "clause 6.2.1 of [6, 38.214]",
              "clause 6.2.1 of [TS 38.214].", "clause 6.2.1 of 3GPP TS 38.214 [6].",
              "clause 6.2.1 of 3GPP TS 38.214 [6].", "clause 6.2.1 in TS38.214"]:
        assert ids(find(c, s)) == [("clause", "6.2.1", "38.214", "resolved")], s


def test_designator_variants_naming_specs_outside_corpus(c):
    cases = {
        # 24301-j80
        "as specified in the clause 6.2.2 of 3GPP TS 23.161 [34].": "23.161",
        # 36211-j30
        "the number of codeblocks as defined in clause 5.1.2 of [36.212]": "36.212",
        # 36101-j60 (HTML cell)
        "modulated according to clause 5 of TS36.211</td></tr>": "36.211",
        # 36133-j60
        "modes are specified in section 7.1 in 3GPP TS 36.213.<br>N/A": "36.213",
        "according to clause 5.3.3.19 in [TS 36.331], with": "36.331",
        # 38106-j60
        "described in clause 7.7.3 in TR 38.901 [29].": "38.901",
    }
    for s, spec in cases.items():
        assert [(r.kind, r.target_spec_number, r.status) for r in find(c, s)] == [
            ("clause", spec, "missing_spec")], s


def test_dotless_spec_number(c):
    # 36133-j60 change history: "CR on item title of table in clause 8.1.2.4.5.1 in TS36133 in Rel-13"
    assert ids(find(c, "CR on item title of table in clause 4.2 in TS38213 in Rel-13")) == [
        ("clause", "4.2", "38.213", "resolved")]
    assert ids(find(c, "Correction of clause 5.1.2 in TS38214 |")) == [
        ("clause", "5.1.2", "38.214", "resolved")]


def test_other_document_guard_never_resolves_locally(c):
    cases = [
        # 24008-j50, 24501-j80, 36300-j20
        "Time stamp format as defined in clause 4.2 of IETF RFC 5905 [169].",
        "timer specified in clause 4.2 of IETF RFC 3748 [34] to infinite value.",
        # 24501-j80
        "MAC address as defined in clause 4.2 of IEEE Std 802 [43].",
        "as specified in clause 4.2 of ITU-T Recommendation X.690",
        "as defined in clause 4.2 of ETSI TS 102 221 [5]",
        "see clause 4.2 of ISO/IEC 8859-1",
        "see clause 4.2 of ANSI T1.106",
        # 38101-1-j70 typo: "of TS 3801-2"
        "refer to clause 4.2 of TS 3801-2 for",
        "refer to clause 4.2 of the 3GPP Release 15",
        "clause 4.2 in [X, Y]",
    ]
    for s in cases:
        r = find(c, s)
        assert [(x.text, x.status, x.target_spec_number, x.target) for x in r] == [
            ("clause 4.2", "missing_spec", "", None)], s
    # a list before the other-document designator is kept and none of it resolves
    assert [(x.text, x.status) for x in find(c, "clauses 4.2 and 4 of IETF RFC 3748")] == [
        ("clauses 4.2", "missing_spec"), ("4", "missing_spec")]
    # own-spec designators still resolve locally
    assert ids(find(c, "Table 4.2-1 of TS 38.213.")) == [("table", "4.2-1", "38.213", "resolved")]
    assert ids(find(c, "Table 4.2-1 of 3GPP TS 38.213 [x]")) == [("table", "4.2-1", "38.213", "resolved")]


# Repeated keyword lists: "Table X, Table Y and Table Z of [2]" share the designator.

def test_repeated_keyword_list_shares_trailing_designator(c):
    # 38213-j50 (exact): "one of the entries from table 6.1.2.1.1-2 or table 6.1.2.1.1-3 in [6, TS 38.214], if"
    assert ids(find(c, "- one of the entries from table 6.1.2.1.1-2 or table 6.1.2.1.1-3 in [6, TS 38.214], if")) == [
        ("table", "6.1.2.1.1-2", "38.214", "resolved"), ("table", "6.1.2.1.1-3", "38.214", "resolved")]
    # 36212-j30: "used in Table 5.3.3A.2-2, Table 5.3.3A.2-3, Table 5.3.3A.2-4 and Table 5.3.3A.2-5 of [2]."
    refs = find(c, "used in Table 6.1.2.1.1-2, Table 6.1.2.1.1-3, Table 6.1.2.1.1-4 and Table 5.1.2.1-2 of [6].")
    assert [(r.text, r.target_spec_number, r.status) for r in refs] == [
        ("Table 6.1.2.1.1-2", "38.214", "resolved"), ("Table 6.1.2.1.1-3", "38.214", "resolved"),
        ("Table 6.1.2.1.1-4", "38.214", "resolved"), ("Table 5.1.2.1-2", "38.214", "resolved")]
    # 38214-j50: "according to clause 9, clause 11.1 and clause 11.2A of [6, TS 38.213]"
    assert ids(find(c, "according to clause 4.2, clause 5.1.2 and clause 9.1.5 of [6, TS 38.214] or")) == [
        ("clause", "4.2", "38.214", "missing_target"), ("clause", "5.1.2", "38.214", "resolved"),
        ("clause", "9.1.5", "38.214", "resolved")]
    # other-document designator after the chain: nothing resolves locally
    assert [r.status for r in find(c, "clause 4.2 and clause 4 of IETF RFC 3748")] == [
        "missing_spec", "missing_spec"]


def test_repeated_keyword_list_not_shared_across_groups_or_kinds(c):
    # 38213-j50: "determined from clauses 9, 9.2.5 and 9.2.6 or clause 6.1 of [6, TS 38.214]"
    assert ids(find(c, "determined from clauses 4, 4.2 and 8.1 or clause 6.1 of [6, TS 38.214].")) == [
        ("clause", "4", "38.213", "resolved"), ("clause", "4.2", "38.213", "resolved"),
        ("clause", "8.1", "38.213", "resolved"),
        ("clause", "6.1", "38.214", "resolved")]
    # 38212-j40: "according to Table 7.3.1.1.2-37 and Clause 6.2.1 of [6, TS 38.214], where"
    assert ids(find(c, "according to Table 4.2-1 and clause 6.2.1 of [6, TS 38.214], where")) == [
        ("table", "4.2-1", "38.213", "resolved"), ("clause", "6.2.1", "38.214", "resolved")]
    # no designator at all: each item stays in the current spec
    assert ids(find(c, "see Table 4.2-1 and Table 8.1-2.")) == [
        ("table", "4.2-1", "38.213", "resolved"), ("table", "8.1-2", "38.213", "ambiguous")]


def test_prefix_designator_carries_over_repeated_keyword(c):
    # 38331-j40: "(see TS 38.214 [19], clause 6.1.2 and clause 6.3)."
    assert ids(find(c, "(see TS 38.214 [19], clause 5.1.2 and clause 9.1.5)")) == [
        ("clause", "5.1.2", "38.214", "resolved"), ("clause", "9.1.5", "38.214", "resolved")]
    # 36331-j40: "TS 36.213 [23], Table 7.1.6-1 and Table 7.1.7.2.7-1. Value 0"
    assert ids(find(c, "TS 38.214 [23], Table 5.1.2.1-2 and Table 6.1.2.1.1-2. Value 0")) == [
        ("table", "5.1.2.1-2", "38.214", "resolved"), ("table", "6.1.2.1.1-2", "38.214", "resolved")]
    # a trailing designator after the chain wins over the prefix
    assert ids(find(c, "TS 38.214 [6], clause 5.1.2 and clause 4.2 of the present document")) == [
        ("clause", "5.1.2", "38.214", "resolved"), ("clause", "4.2", "38.213", "resolved")]


def test_present_document_is_own_spec(c):
    # 24008-j50: "... as specified in clause 10 of the present document"
    assert ids(find(c, "[6], clause 4.2 of the present document")) == [("clause", "4.2", "38.213", "resolved")]
    assert ids(find(c, "Table 4.2-1 in this specification")) == [("table", "4.2-1", "38.213", "resolved")]


def test_clause_and_annex_chain_share_designator(c):
    # 24501-j80: "due to reasons specified in clause 4.4.6 or Annex C in 3GPP TS 23.122 [5], then"
    assert [(r.text, r.target_spec_number, r.status) for r in find(
        c, "due to reasons specified in clause 4.4.6 or Annex C in 3GPP TS 23.122 [5], then")] == [
        ("clause 4.4.6", "23.122", "missing_spec"), ("Annex C", "23.122", "missing_spec")]


def test_slash_list(c):
    # 38101-5-j60: "as described in Annex A.5.1.1/A.5.2.1 in TS 38.101-1 [5])"
    assert [(r.text, r.target_spec_number) for r in find(c, "described in Annex A.5.1.1/A.5.2.1 in TS 38.101-1 [5])")] == [
        ("Annex A.5.1.1", "38.101-1"), ("A.5.2.1", "38.101-1")]
    assert [r.text for r in find(c, "see clause 4.2/8.1 for")] == ["clause 4.2", "8.1"]
    # 38212-j40: "Table 7.3.1.1.2-28/29/30/31 of [5]" -- partial numbers are not references
    assert [(r.text, r.target_spec_number) for r in find(c, "Table 4.2-1/2/3 of [6]")] == [("Table 4.2-1", "38.214")]


def test_capitalised_and_lowercase_keyword_variants(c):
    # 38212-j40: "RI in CSI part 1 according to Clause 5.2.2.2.1 in [6, TS38.214] of all"
    assert ids(find(c, "RI in CSI part 1 according to Clause 5.1.2 in [6, TS38.214] of all")) == [
        ("clause", "5.1.2", "38.214", "resolved")]
    # 38212-j40: "according to Table 7.3.1.1.2-37 and Clause 6.2.1 of [6, TS 38.214], where"
    assert ids(find(c, "according to Table 4.2-1 and Clause 6.2.1 of [6, TS 38.214], where")) == [
        ("table", "4.2-1", "38.213", "resolved"), ("clause", "6.2.1", "38.214", "resolved")]
    assert [(r.text, r.kind, r.target_id) for r in find(
        c, "Section 4.2 and Subclause 8.1, figure 4.2-1, Clauses 4 and 9, Annexes B and C, annex B.")] == [
        ("Section 4.2", "clause", "4.2"), ("Subclause 8.1", "clause", "8.1"),
        ("figure 4.2-1", "figure", "4.2-1"), ("Clauses 4", "clause", "4"), ("9", "clause", "9"),
        ("Annexes B", "clause", "B"), ("C", "clause", "C"), ("annex B", "clause", "B")]
    assert find(c, "Clause The") == [] and find(c, "annexed 4.2") == []


def test_caption_number_suffix_shapes(c):
    # 36212-j30: "Table 5.2.2.6.2-2E-1"; 36101-j60: "Table 7.3.1-1aa"
    assert [(r.text, r.target_id) for r in find(c, "see Table 5.2.2.6.2-2E-1 and Table 7.3.1-1aa.")] == [
        ("Table 5.2.2.6.2-2E-1", "5.2.2.6.2-2E-1"), ("Table 7.3.1-1aa", "7.3.1-1aa")]
    # a number that runs on into another dotted number is not a caption number
    assert find(c, "Tables 4.2-1-4.2 x") == []


def test_from_designator(c):
    # 38101-5-j60: "Additional parameters are specified in Table A.3.1-1 and Table A.3.2.1-1 from TS 38.101-1 [5]."
    assert [(r.text, r.target_spec_number, r.status) for r in find(
        c, "Note 1: Additional parameters are specified in Table A.3.1-1 and Table A.3.2.1-1 from TS 38.101-1 [5].")] == [
        ("Table A.3.1-1", "38.101-1", "missing_spec"), ("Table A.3.2.1-1", "38.101-1", "missing_spec")]


def test_prefix_with_space_before_comma(c):
    # 36133-j60: "Defined in TS 36.304 , subclause 5.2.4.7 for E-UTRAN"
    assert ids(find(c, "Defined in TS 38.214 , subclause 5.1.2 for E-UTRAN")) == [
        ("clause", "5.1.2", "38.214", "resolved")]


def test_prefix_carries_to_adjacent_reference(c):
    # 36133-j60: "| As specified in TS 36.211 clause 4.2 Table 4.2-2 |"
    assert ids(find(c, "| As specified in TS 38.214 clause 5.1.2 Table 5.1.2.1-2 |")) == [
        ("clause", "5.1.2", "38.214", "resolved"), ("table", "5.1.2.1-2", "38.214", "resolved")]
    # not across other words
    assert ids(find(c, "TS 38.214 clause 5.1.2 and then Table 4.2-1")) == [
        ("clause", "5.1.2", "38.214", "resolved"), ("table", "4.2-1", "38.213", "resolved")]


def test_defined_in_designator(c):
    # 38101-5-j60: "MCS Index is based on MCS table 6.1.4.1-1 defined in TS 38.214 [14]."
    assert ids(find(c, "NOTE 2: MCS Index is based on MCS table 6.1.2.1.1-2 defined in TS 38.214 [14].")) == [
        ("table", "6.1.2.1.1-2", "38.214", "resolved")]
    assert ids(find(c, "see clause 5.1.2 as specified in [6].")) == [("clause", "5.1.2", "38.214", "resolved")]
    assert [r.status for r in find(c, "the clause 4.2 defined in IETF RFC 5905")] == ["missing_spec"]


def test_bracket_designator_right_after_number(c):
    # 38214-j50: "based on the values defined in Clause 5.4.2.1 [5, TS 38.212]"
    assert [(r.target_spec_number, r.status) for r in find(
        c, "based on the values defined in Clause 5.4.2.1 [5, TS 38.212]")] == [("38.212", "missing_spec")]
    # 38101-5-j60: "OCNG Pattern as described in Annex A.5.2.1 [15] and" ([15] is not in this spec's list)
    assert [(r.target_spec_number, r.status) for r in find(c, "as described in Annex A.5.2.1 [15] and")] == [
        ("", "missing_spec")]
    assert ids(find(c, "clause 5.1.2 [6]")) == [("clause", "5.1.2", "38.214", "resolved")]
    assert ids(find(c, "Table 4.2-1 [dB]")) == [("table", "4.2-1", "38.213", "resolved")]


def test_space_before_list_comma(c):
    # 38101-3-j70: "specified in clause 6.2.2, 6.2A.2 , and 6.2D.2 of TS 38.101-2 [3] apply."
    assert [(r.text, r.target_spec_number) for r in find(
        c, "specified in clause 6.2.2, 6.2A.2 , and 6.2D.2 of TS 38.101-2 [3] apply.")] == [
        ("clause 6.2.2", "38.101-2"), ("6.2A.2", "38.101-2"), ("6.2D.2", "38.101-2")]


def test_annex_list_keeps_document_designator_after_dotless_item(c):
    refs = find(c, "as specified in Annexes A.2.2.2, A3.2 and A.3.3 in TS 38.101-1 [5]")
    assert [(r.text, r.target_id, r.target_spec_number) for r in refs] == [
        ("Annexes A.2.2.2", "A.2.2.2", "38.101-1"),
        ("A3.2", "A3.2", "38.101-1"),
        ("A.3.3", "A.3.3", "38.101-1"),
    ]


def test_bracketed_document_before_clause(c):
    assert ids(find(c, "Shared Risk is defined in [ETR 273 Part 1 sub-part 2 clause 6.5].")) == [
        ("clause", "6.5", "", "missing_spec"),
    ]
    assert ids(find(c, "the UE decodes [5, Section 10] 5 subframes containing PMCH transmissions")) == [
        ("clause", "10", "38.211", "missing_spec"),
    ]
    assert ids(find(c, "as defined in TS 38.214 [5, Section 5.1.2].")) == [
        ("clause", "5.1.2", "38.214", "resolved"),
    ]


def test_clause_range_and_annex_share_designator(c):
    refs = find(c, "as captured in clause 4.3 to 4.6 and Annex A.2.2 of TR  36.792[30].")
    assert [(r.target_id, r.target_spec_number, r.status) for r in refs] == [
        ("4.3", "36.792", "missing_spec"),
        ("4.6", "36.792", "missing_spec"),
        ("A.2.2", "36.792", "missing_spec"),
    ]


def test_other_document_number_without_space(c):
    for s in ("clause 4 of RFC3550 applies.", "clause 4 of IEEE802.11 applies.",
              "see [RFC3550 clause 4]."):
        assert ids(find(c, s)) == [("clause", "4", "", "missing_spec")], s


def test_bracket_cite_beats_designator_with_other_reference(c):
    assert ids(find(c, "see TS 38.214 [6], [5, clause 4].")) == [
        ("clause", "4", "38.211", "missing_spec"),
    ]


def test_bracket_designator_applies_to_every_item_inside(c):
    assert ids(find(c, "see [5, clause 5.1 and clause 5.2].")) == [
        ("clause", "5.1", "38.211", "missing_spec"),
        ("clause", "5.2", "38.211", "missing_spec"),
    ]
    assert ids(find(c, "see [5, clause 5.1, Table 5.1-1].")) == [
        ("clause", "5.1", "38.211", "missing_spec"),
        ("table", "5.1-1", "38.211", "missing_spec"),
    ]
    assert ids(find(c, "see [IEEE 802.11, clause 4 and clause 9].")) == [
        ("clause", "4", "", "missing_spec"),
        ("clause", "9", "", "missing_spec"),
    ]


def test_bracket_cite_without_space_after_comma(c):
    assert ids(find(c, "see [5,clause 4].")) == [("clause", "4", "38.211", "missing_spec")]


def test_case_only_difference_resolves_when_unique(tmp_path):
    # 24.501: 제목은 "5.3.19A", 본문은 "subclause 5.3.19a". 36.300: "7.3b-3A"(EPS)와 "7.3b-3a"(5GS)는
    # 다른 그림이라 정확히 같은 번호만 연결하고, 대소문자만 다른 후보가 둘이면 해석하지 않는다.
    make_spec(tmp_path, "24501-j80", "24.501", "19.8.0", [
        dict(clause="5.3.19A", title="Specific requirements for UE configured to use timer T3245", level=3,
             parent="5.3", file="clauses/0001_5.3.19A_s.md", body="x\n"),
        dict(clause="7.3b", title="EDT", level=2, parent="7", file="clauses/0002_7.3b_e.md",
             body="*Figure: 7.3b-3A: MO-EDT EPS*\n\n*Figure: 7.3b-3a: MO-EDT 5GS*\n"),
    ])
    c = build_corpus_index(str(tmp_path))
    spec = c.specs["24501-j80"]
    refs = find_refs("see subclause 5.3.19a, figure 7.3b-3A, figure 7.3b-3a and figure 7.3B-3A.", spec, c)
    assert [(r.target_id, r.status, r.target and r.target.anchor) for r in refs] == [
        ("5.3.19a", "resolved", None),
        ("7.3b-3A", "resolved", "figure-7.3b-3A"),
        ("7.3b-3a", "resolved", "figure-7.3b-3a"),
        ("7.3B-3A", "missing_target", None),
    ]


def test_designator_forms_from_corpus(c):
    # 실제 원문의 다른 규격 지시: "of" 없이 TS가 바로 붙음(36101, 36133), "ofTS"(36321),
    # TS 없는 규격 번호(36133, 38101-1, 38101-3), 괄호 안 쉼표 뒤 지시(36321)
    cases = [
        ("Note 3: As per Table 4.2-2 TS 36.211 [4]. Note 4", [("table", "4.2-2", "36.211")]),
        ("defined in clause 10.2.6 TS 36.211 [16], on non-anchor carrier", [("clause", "10.2.6", "36.211")]),
        ("within the RA Response window defined in clause 5.1.4 TS 36.321.", [("clause", "5.1.4", "36.321")]),
        ("(see clause 5.1.1.2 ofTS 36.213 [2]);", [("clause", "5.1.1.2", "36.213")]),
        ("an accuracy as specified in table 6.3.5.2.1-1 of 36.101[5].", [("table", "6.3.5.2.1-1", "36.101")]),
        ("MPR as defined in clause 6.2B.2.1 of 38.101-3 v15.5.0 |", [("clause", "6.2B.2.1", "38.101-3")]),
        ("(From Table 5.3.5-1 of 38.101-1)", [("table", "5.3.5-1", "38.101-1")]),
        ("as defined in clause 6.2.1 or 6.2A1.1 of 38.101-1 [2]; in case",
         [("clause", "6.2.1", "38.101-1"), ("clause", "6.2A1.1", "38.101-1")]),
        ("in clause 8.2.1.2.14 of 38.133 [15] and clause 7.32.2.12 of 36.133 [16] respectively.",
         [("clause", "8.2.1.2.14", "38.133"), ("clause", "7.32.2.12", "36.133")]),
        ("is not applicable (clause 4.2.7.9, TS 38.306 [22]), the UE may",
         [("clause", "4.2.7.9", "38.306")]),
    ]
    for s, want in cases:
        assert [r[:3] for r in ids(find(c, s))] == want, s


def test_designator_forms_keep_own_spec(c):
    # 쉼표 뒤 지시가 다음 참조의 앞쪽 지시이면(36104) 앞 참조는 현재 규격이다. 숫자 값은 규격 번호가 아니다.
    assert [r[:3] for r in ids(find(c, "as specified in clause 4.2, TS 25.104 [6] clause 5.2 and"))] == [
        ("clause", "4.2", "38.213"), ("clause", "5.2", "25.104")]
    assert [r[:3] for r in ids(find(c, "see Table 4.2-1 of 10.000 MHz"))] == [("table", "4.2-1", "38.213")]


DUP_SAME_FILE = (
    # 36101-j60 8.13.2: 원문이 두 하위 조항의 표에 같은 번호 8.13.2.1.1-2를 썼다(두 번째는 8.13.2.1.2-2의 오타)
    "## 8.13.2.1.1 CA\n\nresults in Table 8.13.2.1.1-2.\n\n**Table 8.13.2.1.1-2: For CA**\n\n| a |\n| - |\n\n"
    "## 8.13.2.1.2 DC\n\nresults in Table 8.13.2.1.1-2.\n\n**Table 8.13.2.1.1-2: For DC**\n\n| a |\n| - |\n"
)


def test_ambiguous_resolved_by_same_section(tmp_path):
    make_spec(tmp_path, "36101-j60", "36.101", "19.6.0", [
        dict(clause="8.13.2", title="FDD", level=3, parent="8.13", file="clauses/0001_8.13.2_f.md",
             body=DUP_SAME_FILE),
        dict(clause="8.14", title="Other", level=2, parent="8", file="clauses/0002_8.14_o.md",
             body="see Table 8.13.2.1.1-2.\n"),
    ])
    c = build_corpus_index(str(tmp_path))
    spec = c.specs["36101-j60"]
    f1, f2 = "clauses/0001_8.13.2_f.md", "clauses/0002_8.14_o.md"
    text = (tmp_path / "36101-j60" / f1).read_text(encoding="utf-8")
    refs = find_refs(text, spec, c, f1)
    assert [(r.status, r.target.anchor) for r in refs] == [
        ("resolved", "table-8.13.2.1.1-2"), ("resolved", "table-8.13.2.1.1-2~2")]
    lines = text.split("\n")
    assert [lines[r.target.line - 1] for r in refs] == [
        "**Table 8.13.2.1.1-2: For CA**", "**Table 8.13.2.1.1-2: For DC**"]
    # 다른 조항에서는 어느 표인지 알 수 없다
    assert find_refs("see Table 8.13.2.1.1-2.\n", spec, c, f2)[0].status == "ambiguous"
    assert find_refs("see Table 8.13.2.1.1-2.\n", spec, c)[0].status == "ambiguous"


def test_void_status(tmp_path):
    make_spec(tmp_path, "36104-j20", "36.104", "19.2.0", [
        dict(clause="5.2", title="Void", level=2, parent="5", file=None, body=""),
        dict(clause="5.5", title="Operating bands", level=2, parent="5", file="clauses/0001_5.5_o.md",
             body="**Table\xa05.5-2: Void**\n"),
    ])
    c = build_corpus_index(str(tmp_path))
    refs = find_refs("see clause 5.2, Table 5.5-2 and Table 5.5-9.", c.specs["36104-j20"], c)
    assert [(r.target_id, r.status, r.target and r.target.anchor) for r in refs] == [
        ("5.2", "void", None), ("5.5-2", "void", "table-5.5-2"), ("5.5-9", "missing_target", None)]

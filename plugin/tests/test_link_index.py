import os

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


def test_duplicate_heading_clause_is_ambiguous(tmp_path):
    body_a = "## 8.17.3 FDD\n\ntext\n"
    body_b = "## 8.17.3 TDD\n\ntext\n\n## 8.17.4 Only\n"
    d = make_spec(tmp_path, "36133-j50", "36.133", "19.5.0", [
        dict(clause="8.17", title="A", level=2, parent="8", file="clauses/0001_8.17_a.md", body=body_a),
        dict(clause="8.18", title="B", level=2, parent="8", file="clauses/0002_8.18_b.md", body=body_b),
    ])
    idx = build_spec_index(d)
    assert idx.clauses["8.17.3"].ambiguous
    assert not idx.clauses["8.17.4"].ambiguous
    assert not idx.clauses["8.17"].ambiguous


def test_caption_forms_from_corpus(tmp_path):
    # 실제 원문의 캡션 표기들 (NBSP, 굵게 쓴 Figure, 기울임 Table, "Table:", 복수형, 붙여 쓴 번호,
    # "Fig.", 인용, 번호 안 공백, 콜론 없는 단독 문단)
    lines = [
        "*Figure\xa010.5.5.35-1/3GPP\xa0TS\xa024.008: DCN-ID information element*",           # 24008
        "**Table\xa010.5.5.35-1/3GPP\xa0TS\xa024.008: DCN-ID information element**",           # 24008
        "**Figure B.3.1-1: Doppler shift trajectory ($f_{d}$<!-- ole-equation: ../media/x.wmf -->**",  # 38101-4
        "*Table 11.2-1: UE performance requirements for RRC procedures for UEs other than NB-IoT UEs*",  # 36331
        "**Table: 5.3.3-2: Minimum guardband (kHz) of SCS 240 kHz SS/PBCH block in FR2-1**",  # 38101-2
        "**Table: 8.2.16.1-1 Test parameters with enhanced performance requirements**",       # 38104
        "*Figure: 7.3b-3A: MO-EDT for User Plane CIoT EPS Optimisations*",                    # 36300
        "**Tables 7.7E.1A-2: Spurious response for intra-band contiguous SL CA UE**",         # 38101-1
        "**Table5.2.3.1.16-4: Minimum performance for target UE with Rank 2**",               # 38101-4
        "**TableA.14.1.1.8.1-2: General test parameters for HD-FDD intra frequency**",        # 36133
        "*Fig. 4.7.2-1: Protocol stack for the support of F1-U protocol*",                    # 38300
        "> Table C.3.1-1a: Downlink Physical Channels transmitted during a connection (TDD Band 46)",  # 36101
        "**Table A.5.2.3.1 -1: General test parameters for E-UTRAN FDD-GSM handover**",       # 36133
        "**Table A.5.2.8.1 - 2: Cell specific parameters for cell # 1**",                     # 36133
        "**Table A. 14.2.1.1.2-2: General test parameters for E-UTRAN HD-FDD**",              # 36133
        "**Table 8.13.1.2. 1-3: Minimum performance (FRC) based on single carrier performance**",  # 36101
        "**Table A.9.6.1.1.-2: E-UTRAN FDD Cell specific test parameters for GSM Carrier RSSI**",  # 36133
        "Table 9.7.2.1-2 Minimum requirement (FDD and half-duplex FDD)",                      # 36101
        "Figure A.7.3.1.1-1 SNR variation for out-of-sync testing",                           # 36133
        # 캡션이 아닌 본문 문장
        "Table 5.2.3.3.1-4I shows the fields and the corresponding bit widths.",              # 36212
        "Table 6.1-8 is used. Otherwise see Table 6.1-7",
    ]
    body = "\n\n".join(lines) + "\n"
    d = make_spec(tmp_path, "36101-j60", "36.101", "19.6.0", [
        dict(clause="5.2", title="T", level=2, parent="5", file="clauses/0001_5.2_t.md", body=body)])
    idx = build_spec_index(d)
    assert sorted(idx.tables) == sorted([
        "10.5.5.35-1", "11.2-1", "5.3.3-2", "8.2.16.1-1", "7.7E.1A-2",
        "5.2.3.1.16-4", "A.14.1.1.8.1-2", "C.3.1-1a", "A.5.2.3.1-1", "A.5.2.8.1-2",
        "A.14.2.1.1.2-2", "8.13.1.2.1-3", "A.9.6.1.1-2", "9.7.2.1-2"])
    assert sorted(idx.figures) == sorted(["10.5.5.35-1", "B.3.1-1", "7.3b-3A", "4.7.2-1", "A.7.3.1.1-1"])
    assert idx.tables["A.5.2.3.1-1"].anchor == "table-A.5.2.3.1-1"


def test_fileless_clause_followed_by_letter_suffixed_clause(tmp_path):
    # 24008-j50: "4.3.2 Authentication procedure"에는 본문이 없고 내용이 바로 뒤 4.3.2a, 4.3.2b로 이어진다.
    # 바로 뒤가 아닌 글자 접미 조항(4.4 뒤의 4.4a)은 쓰지 않는다.
    d = make_spec(tmp_path, "24008-j50", "24.008", "19.5.0", [
        dict(clause="4.3.2", title="Authentication procedure", level=3, parent="4.3", file=None, body=""),
        dict(clause="4.3.2a", title="Authentication procedure used for a UMTS authentication challenge",
             level=3, parent="4.3", file="clauses/0001_4.3.2a_a.md", body="x\n"),
        dict(clause="4.4", title="Empty", level=2, parent="4", file=None, body=""),
        dict(clause="4.3.3", title="Other", level=3, parent="4.3", file="clauses/0002_4.3.3_o.md", body="x\n"),
        dict(clause="4.4a", title="Later", level=2, parent="4", file="clauses/0003_4.4a_l.md", body="x\n"),
    ])
    idx = build_spec_index(d)
    assert idx.clauses["4.3.2"] == Target("clauses/0001_4.3.2a_a.md", None, 1)
    assert "4.4" not in idx.clauses


def test_void_targets(tmp_path):
    # 36331-j40: "5.3.5.7 Void"(본문 없음) 바로 뒤에 5.3.5.7a가 와도 Void 조항을 그 파일로 잇지 않는다.
    # 36104-j20: "**Table 5.5-2: Void**", 38101-2-j50: "(Void)" 제목
    d = make_spec(tmp_path, "36331-j40", "36.331", "19.4.0", [
        dict(clause="5.3.5.7", title="Void", level=4, parent="5.3.5", file=None, body=""),
        dict(clause="5.3.5.7a", title="T307 expiry (SCG change failure)", level=4, parent="5.3.5",
             file="clauses/0001_5.3.5.7a_t.md",
             body="**Table\xa05.5-2: Void**\n\n**Table 5.5-3: Real**\n\n#### 5.3.5.7a.1 (Void)\n\n#### 5.3.5.7a.2 Real\n"),
        dict(clause="6.6.3", title="(Void)", level=3, parent="6.6", file=None, body=""),
    ])
    idx = build_spec_index(d)
    assert "5.3.5.7" not in idx.clauses and "6.6.3" not in idx.clauses
    assert "5.5-2" not in idx.tables and "5.5-3" in idx.tables
    assert "5.3.5.7a.1" not in idx.clauses and "5.3.5.7a.2" in idx.clauses
    assert {k: set(v) for k, v in idx.voids.items()} == {
        "clause": {"5.3.5.7", "6.6.3", "5.3.5.7a.1"}, "table": {"5.5-2"}, "figure": set()}
    # Void 제목·캡션 줄은 위치가 있고, 본문 없는 Void 조항은 위치가 없다
    assert idx.voids["table"]["5.5-2"].anchor == "table-5.5-2"
    assert idx.voids["clause"]["5.3.5.7a.1"].anchor == "clause-5.3.5.7a.1"
    assert idx.voids["clause"]["5.3.5.7"] is None


def test_caption_written_as_heading(tmp_path):
    # 36106-j10: 원문이 캡션 문단에 제목 수준을 줘서 "# Table 6.1-1: …"이 파일 제목이 됐다.
    # 38101-3-j70의 "# Table 5.5A.1.2-1b"(콜론·제목 없음)는 표 묶음 제목이고 진짜 캡션은 본문에 따로 있다.
    d = make_spec(tmp_path, "36106-j10", "36.106", "19.1.0", [
        dict(clause="table-6-1-1-repeater-output-power-normal-conditions",
             title="Table 6.1-1: Repeater output power; normal conditions", level=1, parent=None,
             file="clauses/0024_table-6-1-1.md", body="| a |\n| - |\n"),
        dict(clause="table-5-5a-1-2-1b", title="Table 5.5A.1.2-1b", level=5, parent=None,
             file="clauses/0057_table-5-5a-1-2-1b.md", body="**Table 5.5A.1.2-1b: Bands**\n"),
    ])
    for rel, title in [("clauses/0024_table-6-1-1.md", "Table 6.1-1: Repeater output power; normal conditions"),
                       ("clauses/0057_table-5-5a-1-2-1b.md", "Table 5.5A.1.2-1b")]:
        path = os.path.join(d, *rel.split("/"))
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        # 변환기는 번호 없는 제목을 "# 제목"으로 쓴다
        lines = [f"# {title}" if ln.startswith("# ") else ln for ln in lines]
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
    idx = build_spec_index(d)
    t = idx.tables["6.1-1"]
    assert (t.file, t.anchor, t.ambiguous) == ("clauses/0024_table-6-1-1.md", "table-6.1-1", False)
    assert not idx.tables["5.5A.1.2-1b"].ambiguous

"""Multi-part specs, batch grouping and the topics command (output-contract.md sections 1, 6)."""
import json
import os

from docx_builder import PNG, build, cover, drawing, p, table, row, cell
from spec2md.cli import group_dir, main
from spec2md.reader import part_sort_key, split_name, version_from_code


def make_parts(d):
    build(d / "39999-i10_cover.docx", cover("18.1.0", "39.999"))
    build(d / "39999-i10_s00-04.docx", "".join([
        p("Heading1", "Foreword"), p("Normal", "Fw."),
        p("Heading1", "4\tGeneral"), p("Heading2", "4.1\tPart one"),
        p("Normal", "First part.", drawing("rId9")),
    ]), {"rId9": ("image1.png", PNG)})
    build(d / "39999-i10_s05-XX.docx", "".join([
        p("Normal", "Continued from part one.", drawing("rId9")),
        table(1, row(cell(p("TAL", "cell")))),
        p("Heading1", "5\tSecond"), p("Normal", "Second part."),
    ]), {"rId9": ("image1.png", PNG + b"different")})
    return sorted(d.glob("*.docx"), key=lambda x: x.name, reverse=True)  # order must not matter


def test_split_name_and_version():
    assert split_name("specs/36101-j60_s08-XX.docx") == ("36101-j60", "s08-XX")
    assert split_name("38101-1-j70_0_cover.docx") == ("38101-1-j70", "0_cover")
    assert split_name("38331-j40.docx") == ("38331-j40", None)
    assert version_from_code("38331-i10") == ("38.331", "18.1.0")
    assert version_from_code("38101-1-j70") == ("38.101-1", "19.7.0")


def test_part_sort_numeric_prefix():
    names = [f"38133-j60_{i}_s{i}.docx" for i in range(22)]
    assert sorted(reversed(names), key=part_sort_key) == names  # 0, 1, 2, ..., 10, ..., 21
    plain = ["36101-j60_cover.docx", "36101-j60_s00-07.docx", "36101-j60_s08-XX.docx",
             "36101-j60_sAnnexes.docx", "36211-j30_s00-s05.docx", "38101-1-j70_0_cover.docx",
             "38101-1-j70_7_sAnnexes.docx", "38101-3-j70_cover.docx", "38331-j40.docx"]
    assert sorted(reversed(plain), key=part_sort_key) == sorted(plain)


def test_multipart(tmp_path, convert):
    parts = make_parts(tmp_path)
    out, _ = convert(parts)
    m = out.manifest
    assert os.path.basename(out.path) == "39999-i10"
    assert m["source_files"] == ["39999-i10_cover.docx", "39999-i10_s00-04.docx", "39999-i10_s05-XX.docx"]
    assert m["version"] == "18.1.0" and m["spec"] == "TS 39.999"
    assert m["skipped"] == ["cover: cover", "cover: contents"]
    assert [c["order"] for c in m["clauses"]] == [1, 2, 3, 4]
    assert out.entry("4.1")["source_file"] == "39999-i10_s00-04.docx"
    assert out.entry("5")["source_file"] == "39999-i10_s05-XX.docx"
    body = out.body("4.1")
    assert "![Figure](../media/s00-04_image1.png)" in body
    assert "Continued from part one.![Figure](../media/s05-XX_image1.png)" in body
    assert out.entry("4.1")["tables"] == 1 and out.entry("4.1")["figures"] == 2
    assert 'source_file: "39999-i10_s05-XX.docx"' in out.text("5")
    media = sorted(os.listdir(os.path.join(out.path, "media")))
    assert media == ["s00-04_image1.png", "s05-XX_image1.png"]


def test_batch_groups_and_converts(tmp_path, capsys):
    specs = tmp_path / "specs"
    specs.mkdir()
    make_parts(specs)
    build(specs / "39998-i00.docx", p("Heading1", "1\tScope") + p("Normal", "x"))
    (specs / "~$39998-i00.docx").write_bytes(b"lock")
    groups = group_dir(str(specs))
    assert list(groups) == ["39998-i00", "39999-i10"]
    assert [os.path.basename(x) for x in groups["39999-i10"]] == [
        "39999-i10_cover.docx", "39999-i10_s00-04.docx", "39999-i10_s05-XX.docx"]
    rc = main(["batch", str(specs), "-o", str(tmp_path / "raw"), "--depth", "39998-i00=4"])
    assert rc == 0
    man = json.load(open(tmp_path / "raw" / "39998-i00" / "manifest.json", encoding="utf-8"))
    assert man["split_depth"] == 4


def test_batch_continues_after_failure(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "39997-i00.docx").write_bytes(b"not a zip")
    build(specs / "39998-i00.docx", p("Heading1", "1\tScope") + p("Normal", "x"))
    rc = main(["batch", str(specs), "-o", str(tmp_path / "raw")])
    assert rc == 1
    assert (tmp_path / "raw" / "39998-i00" / "manifest.json").exists()


def test_topics(tmp_path, convert):
    parts = make_parts(tmp_path)
    out, _ = convert(parts)
    os.makedirs(os.path.join(out.path, "topics"))
    with open(os.path.join(out.path, "topics", "topics.json"), "w", encoding="utf-8") as f:
        json.dump({"spec": "TS 39.999", "version": "18.1.0", "topics": [
            {"id": "general", "title": "General", "summary": "s", "clauses": ["4.1", "5"], "related": []}],
            "uncategorized": []}, f)
    assert main(["topics", out.path]) == 0
    text = open(os.path.join(out.path, "topics", "general.md"), encoding="utf-8").read()
    assert text.startswith('---\nspec: "TS 39.999"\nversion: "18.1.0"\ntopic: "general"\n')
    assert "<!-- source: clauses/0003_4.1_part-one.md -->\n\n# 4.1 Part one" in text
    assert text.index("# 4.1 Part one") < text.index("# 5 Second")

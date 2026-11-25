"""check_links.py(독립 링크 검사기) 테스트: spec2md link 출력 -> 검사기를 서브프로세스로 실행."""
import json
import os
import subprocess
import sys

from raw_builder import make_spec
from spec2md.link import run_link

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "skills", "spec-linking", "scripts", "check_links.py")
F13 = "clauses/0001_10.1_x.md"
F14 = "clauses/0001_5.1.2_y.md"


def _build(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_spec(raw, "38213-j50", "38.213", "19.0.0", [
        {"clause": "2", "title": "References", "level": 1, "parent": None,
         "file": "clauses/0000_2_r.md",
         "body": "**[6]**: 3GPP TS 38.214: \"NR; Physical layer procedures for data\"\n"},
        {"clause": "10.1", "title": "X", "level": 2, "parent": None, "file": F13,
         "body": "See clause 5.1.2 of [6] and Table 10.1-1 here, clause 10.1 and Table 99.9-9.\n\n"
                 "**Table 10.1-1: T**\n\n"
                 "<table><tr><td>see clause 5.1.2 of [6]</td></tr></table>\n\n"
                 "![i](../media/image1.png)\n"
                 "<img src=\"../media/image1.png\">\n"},
    ])
    make_spec(raw, "38214-j50", "38.214", "19.0.0", [
        {"clause": "5.1.2", "title": "Y", "level": 3, "parent": None, "file": F14,
         "body": "Resource allocation text.\n"},
    ])
    os.makedirs(raw / "38213-j50" / "media")
    (raw / "38213-j50" / "media" / "image1.png").write_bytes(b"png")
    out = tmp_path / "linked"
    run_link(str(raw), str(out))
    return raw, out


def _run(tmp_path, out, raw, *extra):
    return subprocess.run(
        [sys.executable, "-I", SCRIPT, str(out), "--raw", str(raw), *extra],
        cwd=str(tmp_path), capture_output=True, text=True, encoding="utf-8")


def _rw(path, fn):
    with open(path, encoding="utf-8", newline="") as f:
        s = f.read()
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(fn(s))


def test_clean_output_passes(tmp_path):
    raw, out = _build(tmp_path)
    # the fixture really exercises links, table links, backlinks and media rewriting
    t13 = (out / "38213-j50" / F13).read_text(encoding="utf-8")
    assert "<a href=" in t13 and "](../../38214-j50/" in t13 and "<a id=\"table-10.1-1\">" in t13
    assert "spec2md:backlinks" in (out / "38214-j50" / F14).read_text(encoding="utf-8")
    jp = tmp_path / "rep.json"
    r = _run(tmp_path, out, raw, "--json", str(jp))
    assert r.returncode == 0, r.stdout + r.stderr
    rep = json.loads(jp.read_text(encoding="utf-8"))
    assert rep["errors"] == [] and rep["summary"]["files"] == 3
    assert rep["specs"]["38213-j50"]["status"]["resolved"] >= 3
    assert any(m["target_id"] == "99.9-9" and m["count"] == 1 for m in rep["missing_target"])
    assert "WARN" in r.stdout and "missing_target" in r.stdout


def test_json_is_deterministic_format(tmp_path):
    raw, out = _build(tmp_path)
    jp = tmp_path / "rep.json"
    _run(tmp_path, out, raw, "--json", str(jp))
    s = jp.read_text(encoding="utf-8")
    assert s == json.dumps(json.loads(s), sort_keys=True, ensure_ascii=False, indent=1) + "\n"
    assert "\\" not in s.replace("\n", "")


def test_broken_anchor(tmp_path):
    raw, out = _build(tmp_path)
    _rw(out / "38213-j50" / F13, lambda s: s.replace('<a id="table-10.1-1"></a>\n', ""))
    r = _run(tmp_path, out, raw)
    assert r.returncode == 1 and "broken anchor" in r.stdout


def test_body_changed(tmp_path):
    raw, out = _build(tmp_path)
    _rw(out / "38214-j50" / F14, lambda s: s.replace("Resource", "Resourse"))
    r = _run(tmp_path, out, raw)
    assert r.returncode == 1 and "differs from raw" in r.stdout


def test_file_missing(tmp_path):
    raw, out = _build(tmp_path)
    os.remove(out / "38214-j50" / F14)
    r = _run(tmp_path, out, raw)
    assert r.returncode == 1 and "missing" in r.stdout


def test_broken_file_link(tmp_path):
    raw, out = _build(tmp_path)
    _rw(out / "38213-j50" / F13, lambda s: s.replace("0001_5.1.2_y.md", "nope.md", 1))
    r = _run(tmp_path, out, raw)
    assert r.returncode == 1 and "broken link" in r.stdout


def test_backlinks_section_edit_detected_or_reversed(tmp_path):
    raw, out = _build(tmp_path)
    # extra text after the backlinks marker is cut with the section; text before it is not
    _rw(out / "38214-j50" / F14, lambda s: s.replace("Resource allocation", "Resource  allocation"))
    assert _run(tmp_path, out, raw).returncode == 1


def test_real_markdown_link_in_raw_is_kept(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    make_spec(raw, "38213-j50", "38.213", "19.0.0", [
        {"clause": "5", "title": "A", "level": 1, "parent": None, "file": "clauses/0001_5_a.md",
         "body": "See [the site](https://example.com/a) and [doc](notes.txt) here.\n"},
    ])
    out = tmp_path / "linked"
    run_link(str(raw), str(out))
    r = _run(tmp_path, out, raw)
    assert r.returncode == 0, r.stdout


def test_bad_input_exit_2(tmp_path):
    r = _run(tmp_path, tmp_path / "nope", tmp_path / "nope2")
    assert r.returncode == 2

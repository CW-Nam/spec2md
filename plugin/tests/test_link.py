import glob
import hashlib
import json
import os
import re

import pytest

from raw_builder import make_spec
from spec2md.cli import main
from spec2md.link import LinkStats, run_link

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
         "body": "See clause 5.1.2 of [6] and Table 10.1-1 here and clause 10.1.\n\n"
                 "**Table 10.1-1: T**\n\n"
                 "<table><tr><td>see clause 5.1.2 of [6]</td></tr></table>\n\n"
                 "![i](../media/image1.png)\n"},
    ])
    make_spec(raw, "38214-j50", "38.214", "19.0.0", [
        {"clause": "5.1.2", "title": "Y", "level": 3, "parent": None, "file": F14,
         "body": "Resource allocation text.\n"},
    ])
    os.makedirs(raw / "38213-j50" / "media")
    (raw / "38213-j50" / "media" / "image1.png").write_bytes(b"png")
    return str(raw), str(tmp_path / "out")


def _snap(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def test_end_to_end(tmp_path):
    raw, out = _build(tmp_path)
    stats = run_link(raw, out)
    assert isinstance(stats, LinkStats)
    assert stats.specs == 2 and stats.files == 3
    assert stats.refs["resolved"] >= 3
    assert os.path.exists(f"{out}/index.json") and os.path.exists(f"{out}/38213-j50/refs.json")
    text = _read(f"{out}/38214-j50/{F14}")
    assert "## Referenced by" in text and "TS 38.213 10.1" in text
    t13 = _read(f"{out}/38213-j50/{F13}")
    assert "](../../38214-j50/clauses/0001_5.1.2_y.md)" in t13
    assert '<a href="../../38214-j50/clauses/0001_5.1.2_y.md">' in t13
    assert "](../../../raw/38213-j50/media/image1.png)" in t13
    # self reference linked, but no self backlink
    assert "](0001_10.1_x.md#table-10.1-1)" in t13 and "[clause 10.1](0001_10.1_x.md)" in t13
    assert "## Referenced by" not in t13
    idx = json.loads(_read(f"{out}/index.json"))
    assert idx["38214-j50"]["spec_number"] == "38.214"
    assert idx["38214-j50"]["clauses"]["5.1.2"]["file"] == F14
    man = json.loads(_read(f"{out}/38213-j50/manifest.json"))
    assert man["link"]["refs"]["resolved"] >= 3 and man["spec_number"] == "38.213"
    refs = json.loads(_read(f"{out}/38213-j50/refs.json"))
    assert refs["spec"] == "38213-j50"
    r0 = [r for r in refs["refs"] if r["target_spec"] == "38.214"][0]
    assert r0["from_clause"] == "10.1" and r0["status"] == "resolved"
    assert r0["target_file"] == F14 and r0["anchor"] is None


def test_raw_untouched(tmp_path):
    raw, out = _build(tmp_path)
    before = _snap(raw)
    run_link(raw, out)
    assert _snap(raw) == before


def test_rerun_clears_stale_and_is_deterministic(tmp_path):
    raw, out = _build(tmp_path)
    run_link(raw, out)
    stale = f"{out}/38213-j50/clauses/9999_stale.md"
    open(stale, "w").close()
    run_link(raw, out)
    a = _snap(out)
    run_link(raw, out)
    assert not os.path.exists(stale) and _snap(out) == a


def test_no_backslashes_in_outputs(tmp_path):
    raw, out = _build(tmp_path)
    run_link(raw, out)
    for p in glob.glob(f"{out}/**/*.json", recursive=True):
        assert "\\" not in _read(p)
    mds = "".join(_read(p) for p in glob.glob(f"{out}/**/*.md", recursive=True))
    assert "\\" not in "".join(re.findall(r"\]\(([^)]*)\)", mds))
    assert "\\" not in "".join(re.findall(r'href="([^"]*)"', mds))


def test_only(tmp_path):
    raw, out = _build(tmp_path)
    stats = run_link(raw, out, only={"38213-j50"})
    assert not os.path.exists(f"{out}/38214-j50")
    assert os.path.exists(f"{out}/38213-j50/manifest.json") and stats.specs == 1
    assert "38214-j50" in json.loads(_read(f"{out}/index.json"))


def test_only_unknown_code(tmp_path):
    raw, out = _build(tmp_path)
    with pytest.raises(ValueError):
        run_link(raw, out, only={"nope"})


def test_output_format(tmp_path):
    raw, out = _build(tmp_path)
    run_link(raw, out)
    for p in glob.glob(f"{out}/**/*", recursive=True):
        if os.path.isfile(p):
            b = open(p, "rb").read()
            assert not b.startswith(b"\xef\xbb\xbf") and b"\r" not in b


def test_cli(tmp_path, capsys):
    raw, out = _build(tmp_path)
    assert main(["link", raw, "-o", out]) == 0
    err = capsys.readouterr().err
    assert "resolved" in err and "38213-j50" in err
    assert os.path.exists(f"{out}/index.json")


def test_cli_only(tmp_path):
    raw, out = _build(tmp_path)
    assert main(["link", raw, "-o", out, "--only", "38214-j50"]) == 0
    assert not os.path.exists(f"{out}/38213-j50")


@pytest.mark.parametrize("which", ["same", "parent", "inside_raw"])
def test_unsafe_out_refused(tmp_path, which):
    raw, _ = _build(tmp_path)
    out = {"same": raw, "parent": str(tmp_path), "inside_raw": os.path.join(raw, "x")}[which]
    before = _snap(raw)
    assert main(["link", raw, "-o", out]) == 2
    assert _snap(raw) == before
    with pytest.raises(ValueError):
        run_link(raw, out)

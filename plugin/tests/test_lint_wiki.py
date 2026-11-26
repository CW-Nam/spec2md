"""lint_wiki.py(위키 검사기) 테스트: 임시 폴더에 linked/ + wiki/를 만들고 CLI를 서브프로세스로 실행."""
import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "skills", "llm-wiki", "scripts", "lint_wiki.py")
SRC = "../../linked/38321-j40/clauses/a.md"


def fm(**over):
    d = {"type": "feature", "title": "T", "sources": '["linked/38321-j40/clauses/a.md"]',
         "specs": '["38.321 v19.0.0"]', "related": "[]", "updated": "2026-11-26"}
    d.update(over)
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in d.items() if v is not None) + "---\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build(tmp_path):
    write(tmp_path / "linked/38321-j40/clauses/a.md",
          '# 5.17 X\n\n<a id="table-7.1-1"></a>\n**Table 7.1-1: T**\n\n## 5.17.1 Sub part\n')
    w = tmp_path / "wiki"
    write(w / "SCHEMA.md", "# Schema\n\n[bad](nowhere.md)\n")
    write(w / "index.md", "# Index\n\n- [A](features/a.md) - a\n- [B](concepts/b.md) - b\n")
    write(w / "log.md", "# Log\n\n## [2026-11-26] ingest | 38.321 beam\n\n## [2026-11-27] lint | ok\n")
    write(w / "features/a.md", fm() + f"\nText [t]({SRC}#table-7.1-1) and [b](../concepts/b.md).\n")
    write(w / "concepts/b.md", fm(type="concept") +
          f"\nText [s]({SRC}#5171-sub-part) and [a](../features/a.md).\n")
    return w


def run(w, *extra):
    p = subprocess.run([sys.executable, SCRIPT, str(w), *extra], capture_output=True,
                       text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def test_good_wiki(tmp_path):
    rc, out = run(build(tmp_path))
    assert rc == 0, out
    assert "ERROR" not in out and "WARN" not in out


def test_broken_anchor(tmp_path):
    w = build(tmp_path)
    p = w / "features/a.md"
    p.write_text(p.read_text(encoding="utf-8").replace("table-7.1-1", "table-7.1-9"),
                 encoding="utf-8", newline="\n")
    rc, out = run(w)
    assert rc == 1 and "broken link" in out and "features/a.md" in out


def test_broken_file(tmp_path):
    w = build(tmp_path)
    write(w / "features/a.md", fm() + "\n[x](missing.md) [b](../concepts/b.md)\n")
    rc, out = run(w)
    assert rc == 1 and "broken link" in out


def test_missing_key(tmp_path):
    w = build(tmp_path)
    write(w / "features/a.md", fm(sources=None) + "\n[b](../concepts/b.md)\n")
    rc, out = run(w)
    assert rc == 1 and "missing front matter key: sources" in out


def test_empty_sources_and_bad_type(tmp_path):
    w = build(tmp_path)
    write(w / "features/a.md", fm(sources="[]", type="blog") + "\n[b](../concepts/b.md)\n")
    rc, out = run(w)
    assert rc == 1 and "empty sources" in out and "bad type" in out


def test_unparseable_sources_is_empty(tmp_path):
    w = build(tmp_path)
    write(w / "features/a.md", fm(sources="not json") + "\n[b](../concepts/b.md)\n")
    rc, out = run(w)
    assert rc == 1 and "empty sources" in out


def test_not_in_index(tmp_path):
    w = build(tmp_path)
    write(w / "concepts/c.md", fm(type="concept") + "\n[a](../features/a.md)\n")
    rc, out = run(w)
    assert rc == 1 and "not in index" in out and "concepts/c.md" in out


def test_bad_log_entry(tmp_path):
    w = build(tmp_path)
    with open(w / "log.md", "a", encoding="utf-8", newline="\n") as f:
        f.write("## [2026-11-28] reading | x\n")
    rc, out = run(w)
    assert rc == 1 and "bad log entry" in out


def test_orphans_only_warn(tmp_path):
    w = build(tmp_path)
    write(w / "features/a.md", fm() + f"\nText [t]({SRC}#table-7.1-1)\n")
    write(w / "concepts/b.md", fm(type="concept") + f"\nText [t]({SRC}#table-7.1-1)\n")
    rc, out = run(w)
    assert rc == 0 and "orphan" in out and "WARN" in out


def test_ignored_links(tmp_path):
    w = build(tmp_path)
    body = ("\n[b](../concepts/b.md)\n\n`[x](nope1.md)`\n\n```\n[y](nope2.md)\n```\n\n"
            "<!-- [z](nope3.md) -->\n\n[w](https://example.com/nope.md) [m](mailto:a@b.c)\n")
    write(w / "features/a.md", fm() + body)
    rc, out = run(w)
    assert rc == 0, out
    assert "broken" not in out


def test_local_anchor(tmp_path):
    w = build(tmp_path)
    write(w / "features/a.md", fm() + "\n# My Head\n\n[ok](#my-head) [b](../concepts/b.md) [bad](#nope)\n")
    rc, out = run(w)
    assert rc == 1 and out.count("broken link") == 1 and "#nope" in out


def test_many_paragraphs_without_source_warn(tmp_path):
    w = build(tmp_path)
    paras = "\n\n".join(f"Claim number {i}." for i in range(5))
    write(w / "features/a.md", fm() + "\n[b](../concepts/b.md)\n\n" + paras + "\n")
    rc, out = run(w)
    assert rc == 0 and "WARN" in out and "source" in out


def test_json_output(tmp_path):
    w = build(tmp_path)
    write(w / "concepts/c.md", fm(type="concept") + "\n[a](../features/a.md)\n")
    j = tmp_path / "out" / "r.json"
    rc, _ = run(w, "--json", str(j))
    first = j.read_bytes()
    rc2, _ = run(w, "--json", str(j))
    assert rc == rc2 == 1 and j.read_bytes() == first and b"\r" not in first
    rep = json.loads(first)
    assert set(rep) == {"summary", "errors", "warnings"}
    assert rep["summary"]["errors"] == len(rep["errors"]) >= 1
    assert {"kind", "where", "message"} <= set(rep["errors"][0])


def test_missing_dir(tmp_path):
    rc, out = run(tmp_path / "nope")
    assert rc == 2 and "not a directory" in out


def test_heading_slug_keeps_underscores_in_words(tmp_path):
    # GitHub keeps "_" inside words (ASN.1 field names) and drops emphasis/code markers.
    w = build(tmp_path)
    write(w / "features/a.md", fm() + "\n## ssb_PositionsInBurst and _emph_ `code` **bold**\n\n"
          "[ok](#ssb_positionsinburst-and-emph-code-bold) [b](../concepts/b.md)\n")
    rc, out = run(w)
    assert rc == 0, out


def _page(w, sources):
    write(w / "features/a.md", fm(sources=sources) + f"\nText [t]({SRC}#table-7.1-1) and [b](../concepts/b.md).\n")


def test_source_file_and_anchor_must_exist(tmp_path):
    w = build(tmp_path)
    _page(w, '["linked/38321-j40/clauses/a.md#table-7.1-1"]')
    rc, out = run(w)
    assert rc == 0, out
    _page(w, '["linked/38321-j40/clauses/nope.md"]')
    rc, out = run(w)
    assert rc == 1 and "sources" in out and "nope.md" in out
    _page(w, '["linked/38321-j40/clauses/a.md#table-9-9"]')
    rc, out = run(w)
    assert rc == 1 and "sources" in out and "table-9-9" in out

"""목적지 색인: raw 변환 결과에서 조항·표·그림의 위치(파일, 앵커, 줄)를 모은다."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

_NUM = r"[0-9A-Z][0-9A-Za-z.]*-\d+[A-Za-z]?"
_TABLE_RE = re.compile(rf"^\*\*Table ({_NUM})\s*:?")
_FIGURE_RE = re.compile(rf"^\*Figure ({_NUM})\s*:?")
_SUB_RE = re.compile(r"^#{2,6} ([0-9A-Z][0-9A-Za-z]*(?:\.[0-9A-Za-z]+)*)\.? ")
_REF_RE = re.compile(r"\*\*\[(\d+)\]\*\*: 3GPP T[SR] (\d{2}\.\d{3}(?:-\d+)?)")
_FENCE_RE = re.compile(r"^(```|~~~)")


@dataclass(frozen=True)
class Target:
    file: str
    anchor: str | None
    line: int
    ambiguous: bool = False


@dataclass
class SpecIndex:
    code: str
    spec_number: str
    version: str
    release: str
    clauses: dict[str, Target] = field(default_factory=dict)
    tables: dict[str, Target] = field(default_factory=dict)
    figures: dict[str, Target] = field(default_factory=dict)
    references: dict[str, str] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)


@dataclass
class CorpusIndex:
    specs: dict[str, SpecIndex] = field(default_factory=dict)
    by_number: dict[str, str] = field(default_factory=dict)


def anchor_id(kind: str, ident: str) -> str:
    return f"{kind}-{ident}"


def _add(store: dict[str, Target], key: str, target: Target) -> None:
    if key in store:
        old = store[key]
        store[key] = Target(old.file, old.anchor, old.line, True)
    else:
        store[key] = target


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(map(int, version.split(".")))


def build_spec_index(spec_dir: str) -> SpecIndex:
    with open(os.path.join(spec_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    idx = SpecIndex(
        code=os.path.basename(os.path.normpath(spec_dir)),
        spec_number=manifest.get("spec_number", ""),
        version=manifest.get("version", ""),
        release=manifest.get("release", ""),
    )
    entries = manifest.get("clauses", [])
    idx.files = [e["file"] for e in entries if e.get("file")]

    # 1) 매니페스트 조항 (파일이 있는 것)
    for e in entries:
        if e.get("file"):
            idx.clauses.setdefault(e["clause"], Target(e["file"], None, 1))

    # 2) 파일 본문 스캔
    for e in entries:
        rel = e.get("file")
        if not rel:
            continue
        path = os.path.join(spec_dir, *rel.split("/"))
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        start = 0
        if lines and lines[0] == "---":
            for i in range(1, len(lines)):
                if lines[i] == "---":
                    start = i + 1
                    break
        in_fence = False
        for n in range(start, len(lines)):
            line = lines[n]
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            lineno = n + 1
            m = _TABLE_RE.match(line)
            if m:
                _add(idx.tables, m.group(1), Target(rel, anchor_id("table", m.group(1)), lineno))
                continue
            m = _FIGURE_RE.match(line)
            if m:
                _add(idx.figures, m.group(1), Target(rel, anchor_id("figure", m.group(1)), lineno))
                continue
            m = _SUB_RE.match(line)
            if m:
                c = m.group(1)
                idx.clauses.setdefault(c, Target(rel, anchor_id("clause", c), lineno))
                continue
        if e["clause"] == "2":
            for m in _REF_RE.finditer("\n".join(lines[start:])):
                idx.references.setdefault(m.group(1), m.group(2))

    # 3) 본문 없는 조항 -> 첫 하위 조항 파일 맨 위
    for i, e in enumerate(entries):
        if e.get("file") or e["clause"] in idx.clauses:
            continue
        prefix = e["clause"] + "."
        for d in entries[i + 1:]:
            if d.get("file") and d["clause"].startswith(prefix):
                idx.clauses[e["clause"]] = Target(d["file"], None, 1)
                break
    return idx


def build_corpus_index(raw_root: str) -> CorpusIndex:
    corpus = CorpusIndex()
    for name in sorted(os.listdir(raw_root)):
        d = os.path.join(raw_root, name)
        if os.path.isfile(os.path.join(d, "manifest.json")):
            corpus.specs[name] = build_spec_index(d)
    for code, spec in corpus.specs.items():
        cur = corpus.by_number.get(spec.spec_number)
        if cur is None or _version_key(spec.version) > _version_key(corpus.specs[cur].version):
            corpus.by_number[spec.spec_number] = code
    return corpus

"""목적지 색인: raw 변환 결과에서 조항·표·그림의 위치(파일, 앵커, 줄)를 모은다."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

# 캡션 번호: 5.2-1, 7.3.1-1a, 7.3.1-1aa, 5.2.2.6.2-2E-1 (끝은 글자·숫자·하이픈이 아니어야 한다).
# "7.2.2-1 H:"처럼 번호 뒤에 공백과 글자 하나가 붙은 캡션은 번호가 불확실하므로 색인하지 않는다
# (36.213에는 진짜 "Table 7.2.2-1H"도 따로 있어 7.2.2-1H로 읽으면 중복이 된다).
_NUM = r"[0-9A-Z][0-9A-Za-z.]*-\d+[A-Za-z]{0,2}(?:-\d+[A-Za-z]{0,2})*(?![0-9A-Za-z\-])"
_NOT_SPLIT = r"(?! [A-Z]\s*:)"
_TABLE_RE = re.compile(rf"^\*\*Table ({_NUM}){_NOT_SPLIT}")
_FIGURE_RE = re.compile(rf"^\*Figure ({_NUM}){_NOT_SPLIT}")
_SUB_RE = re.compile(r"^#{2,6} ([0-9A-Z][0-9A-Za-z]*(?:\.[0-9A-Za-z]+)*)\.? ")
_REF_RE = re.compile(r"\*\*\[(\d+)\]\*\*: 3GPP T[SR] (\d{2}\.\d{3}(?:-\d+)?)")
_FENCE_RE = re.compile(r"^(```|~~~)")
_NUMBERED_RE = re.compile(r"^(?:\d+[A-Za-z]?|[A-Z])(?:\.[0-9A-Za-z]+)*$")


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

    manifest_keys = set(idx.clauses)

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
                if c not in manifest_keys:  # 매니페스트 조항이 우선, 제목끼리 중복이면 모호
                    _add(idx.clauses, c, Target(rel, anchor_id("clause", c), lineno))
                continue
        if e["clause"] == "2":
            for m in _REF_RE.finditer("\n".join(lines[start:])):
                idx.references.setdefault(m.group(1), m.group(2))

    # 3) 본문 없는 조항 -> 첫 하위 조항 파일 맨 위. 하위 조항은 번호 접두사나 parent 사슬로 찾는다
    #    (36.331 6.3.2 아래 정보 요소 제목처럼 번호 없는 하위 항목).
    parent_of: dict[str, str | None] = {}
    for e in entries:
        parent_of.setdefault(e["clause"], e.get("parent"))

    def descends(d: dict, clause: str) -> bool:
        p, seen = d.get("parent"), set()
        while p is not None and p not in seen:
            if p == clause:
                return True
            seen.add(p)
            p = parent_of.get(p)
        return False

    for i, e in enumerate(entries):
        if e.get("file") or e["clause"] in idx.clauses:
            continue
        prefix = e["clause"] + "."
        nxt = entries[i + 1] if i + 1 < len(entries) else None
        if (nxt is not None and nxt.get("file") and not _NUMBERED_RE.match(nxt["clause"])
                and nxt.get("level", 0) >= e.get("level", 0)):
            # 바로 뒤의 번호 없는 제목(같은 수준으로 변환된 정보 요소 제목)이 이 조항의 첫 내용이다
            idx.clauses[e["clause"]] = Target(nxt["file"], None, 1)
            continue
        for d in entries[i + 1:]:
            if d.get("file") and (d["clause"].startswith(prefix) or descends(d, e["clause"])):
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

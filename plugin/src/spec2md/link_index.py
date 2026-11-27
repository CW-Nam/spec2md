"""목적지 색인: raw 변환 결과에서 조항·표·그림의 위치(파일, 앵커, 줄)를 모은다."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, replace

# 캡션 번호: 5.2-1, 7.3.1-1a, 7.3.1-1aa, 5.2.2.6.2-2E-1 (끝은 글자·숫자·하이픈이 아니어야 한다).
# "7.2.2-1 H:"처럼 번호 뒤에 공백과 글자 하나가 붙은 캡션은 번호가 불확실하므로 색인하지 않는다
# (36.213에는 진짜 "Table 7.2.2-1H"도 따로 있어 7.2.2-1H로 읽으면 중복이 된다).
# 원문 캡션 번호에는 공백이나 하이픈 앞 점이 끼기도 한다("A.5.2.3.1 -1", "8.13.1.2. 1-3",
# "A.9.6.1.1.-2"). 색인 키에서는 뺀다.
_S = r"[^\S\n]?"
_NUM = (rf"[0-9A-Z][0-9A-Za-z]*(?:{_S}\.{_S}[0-9A-Za-z]+)*\.?{_S}-{_S}\d+[A-Za-z]{{0,2}}"
        r"(?:-\d+[A-Za-z]{0,2})*(?![0-9A-Za-z\-])")
_NOT_SPLIT = r"(?! [A-Z]\s*:)"
# 캡션 줄: [> ][*|**]Table|Tables|Figure|Figures|Fig.[:] 번호. 단어와 번호 사이에는 공백(NBSP 포함)이나
# 콜론이 오고, 붙여 쓰기도 한다("Table5.2.3.1.16-4", "TableA.14.1.1.8.1-2").
# 원문이 캡션 문단에 제목 수준을 주면 제목 줄이 된다("# Table 6.1-1: Repeater output power …", 36106).
# 제목 줄은 콜론이 있을 때만 캡션으로 본다("# Table 5.5A.1.2-1b"는 표 묶음 제목이고 캡션은 본문에 따로 있다).
_CAPTION_RE = re.compile(
    rf"^(?:(?P<head>#{{1,6}}[^\S\n]+)|>[^\S\n]*)?(?P<em>\*{{1,2}})?[^\S\n]*(?P<word>Tables?|Figures?|Fig\.)"
    rf"[^\S\n]*(?::[^\S\n]*)?(?P<num>{_NUM}){_NOT_SPLIT}(?P<colon>[^\S\n]*:)?(?P<rest>.*)")
# 꾸밈 없는 캡션이 콜론 없이 제목으로 이어지는 단독 문단("Table 9.7.2.1-2 Minimum requirement (FDD …)").
# 본문 문장("Table 5.2.3.3.1-4I shows …", "… is used.")과 가르려고 제목이 대문자나 괄호로 시작하고
# 문장 부호로 끝나지 않아야 한다.
_PLAIN_TITLE_RE = re.compile(r"[^\S\n]+[A-Z(].*(?<![.:;,])")


def caption_at(lines: list[str], i: int) -> tuple[str, str] | None:
    """lines[i]가 표·그림 캡션이면 (kind, 번호), 아니면 None."""
    m = _CAPTION_RE.match(lines[i])
    if m is None or m["head"] and not m["colon"]:
        return None
    if not (m["em"] or m["colon"]):
        alone = (i == 0 or not lines[i - 1].strip()) and (i + 1 >= len(lines) or not lines[i + 1].strip())
        if not (alone and m["word"] in ("Table", "Figure") and _PLAIN_TITLE_RE.fullmatch(m["rest"].rstrip())):
            return None
    kind = "table" if m["word"].startswith("T") else "figure"
    return kind, re.sub(r"\s", "", m["num"]).replace(".-", "-")


def _is_void(title: str) -> bool:
    """제목·캡션 제목이 Void뿐인가("Void", "(Void)", "void", "Void**")."""
    return re.fullmatch(r"[\s:(*]*void[\s).*]*", title, re.I) is not None


_SUB_RE = re.compile(r"^#{2,6} ([0-9A-Z][0-9A-Za-z]*(?:\.[0-9A-Za-z]+)*)\.? ")
_REF_RE = re.compile(r"\*\*\[(\d+)\]\*\*:[^\S\n]+3GPP[^\S\n]+T[SR][^\S\n]+(\d{2}\.\d{3}(?:-\d+)?)")
_FENCE_RE = re.compile(r"^(```|~~~)")
_NUMBERED_RE = re.compile(r"^(?:\d+[A-Za-z]?|[A-Z])(?:\.[0-9A-Za-z]+)*$")


@dataclass(frozen=True)
class Target:
    file: str
    anchor: str | None
    line: int
    ambiguous: bool = False
    section: str | None = None    # 파일 안에서 이 줄이 속한 하위 제목 번호(없으면 None)
    candidates: tuple["Target", ...] = ()    # 모호하면 같은 번호의 모든 위치(스캔 순서)


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
    # Void로 비어 있는 번호 -> 위치. "## N Void" 제목과 "Table N: Void" 캡션은 그 줄, 본문 없는 Void 조항은 None.
    voids: dict[str, dict[str, Target | None]] = field(
        default_factory=lambda: {"clause": {}, "table": {}, "figure": {}})
    _folded: dict[str, dict[str, Target]] = field(default_factory=dict, repr=False, compare=False)

    def folded(self, kind: str) -> dict[str, Target]:
        """소문자 번호 -> Target. 소문자로 같아지는 번호가 여럿이면 넣지 않는다."""
        if kind not in self._folded:
            store = {"table": self.tables, "figure": self.figures, "clause": self.clauses}[kind]
            groups: dict[str, list[Target]] = {}
            for k, t in store.items():
                groups.setdefault(k.lower(), []).append(t)
            self._folded[kind] = {k: v[0] for k, v in groups.items() if len(v) == 1}
        return self._folded[kind]


@dataclass
class CorpusIndex:
    specs: dict[str, SpecIndex] = field(default_factory=dict)
    by_number: dict[str, str] = field(default_factory=dict)


def anchor_id(kind: str, ident: str) -> str:
    return f"{kind}-{ident}"


def _add(store: dict[str, Target], key: str, target: Target) -> None:
    if key in store:
        old = store[key]
        store[key] = replace(old, ambiguous=True, candidates=(old.candidates or (old,)) + (target,))
    else:
        store[key] = target


def _number_duplicate_anchors(store: dict[str, Target]) -> None:
    """모호한 번호의 후보 가운데 같은 파일의 두 번째부터 앵커에 ~2, ~3 …을 붙인다(파일 안 id가 겹치지 않게)."""
    for key, t in store.items():
        if not t.candidates:
            continue
        seen: dict[str, int] = {}
        cands = []
        for c in t.candidates:
            seen[c.file] = seen.get(c.file, 0) + 1
            n = seen[c.file]
            cands.append(c if n == 1 or not c.anchor else replace(c, anchor=f"{c.anchor}~{n}"))
        store[key] = replace(t, candidates=tuple(cands))


def line_sections(lines: list[str]) -> list[str | None]:
    """줄마다 그 줄이 속한 하위 제목 번호(front matter·코드 펜스 밖의 '## N 제목'), 앞에 제목이 없으면 None."""
    out: list[str | None] = [None] * len(lines)
    start = 0
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                start = i + 1
                break
    cur, in_fence = None, False
    for n in range(start, len(lines)):
        line = lines[n]
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            m = _SUB_RE.match(line)
            if m and not caption_at(lines, n):
                cur = m.group(1)
        out[n] = cur
    return out


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
        secs = line_sections(lines)
        in_fence = False
        for n in range(start, len(lines)):
            line = lines[n]
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            lineno = n + 1
            cap = caption_at(lines, n)
            if cap:
                kind, ident = cap
                if _is_void(_CAPTION_RE.match(line)["rest"]):
                    idx.voids[kind].setdefault(ident, Target(rel, anchor_id(kind, ident), lineno, section=secs[n]))
                    continue
                store = idx.tables if kind == "table" else idx.figures
                _add(store, ident, Target(rel, anchor_id(kind, ident), lineno, section=secs[n]))
                continue
            m = _SUB_RE.match(line)
            if m:
                c = m.group(1)
                if c in manifest_keys:  # 매니페스트 조항이 우선, 제목끼리 중복이면 모호
                    continue
                if _is_void(line[m.end():]):
                    idx.voids["clause"].setdefault(c, Target(rel, anchor_id("clause", c), lineno, section=secs[n]))
                else:
                    _add(idx.clauses, c, Target(rel, anchor_id("clause", c), lineno, section=secs[n]))
                continue
        if e["clause"] == "2":
            for m in _REF_RE.finditer("\n".join(lines[start:])):
                idx.references.setdefault(m.group(1), m.group(2))

    for store in (idx.tables, idx.figures, idx.clauses):
        _number_duplicate_anchors(store)

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
        if _is_void(e.get("title", "")):
            idx.voids["clause"].setdefault(e["clause"], None)
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
        else:
            if (nxt is not None and nxt.get("file")
                    and re.fullmatch(re.escape(e["clause"]) + "[a-z]", nxt["clause"])):
                # 하위 조항이 없고 바로 뒤의 글자 접미 조항(24.008 4.3.2 -> 4.3.2a, 4.3.2b)이 내용일 때
                idx.clauses[e["clause"]] = Target(nxt["file"], None, 1)
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

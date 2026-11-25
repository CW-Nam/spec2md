"""참조 찾기와 해석: 본문의 표·그림·조항 참조를 찾아 목적지 색인으로 해석한다."""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

from .link_index import CorpusIndex, SpecIndex, Target

# 번호 모양. 각 부분이 점으로 시작하므로 나누는 방법이 하나뿐이라 되돌아가기가 폭주하지 않는다.
_HEAD_SEG = r"(?:\d+[A-Za-z]?|[A-Z])"
_CLAUSE_NUM = rf"{_HEAD_SEG}(?:\.[0-9A-Za-z]+)*"
_CAPTION_NUM = rf"{_CLAUSE_NUM}-\d+[A-Za-z]?"
_END = r"(?![0-9A-Za-z])"
_SP = r"[^\S\n]+"          # 줄바꿈을 뺀 공백(NBSP 포함)
_SPEC = r"\d{2}\.\d{3}(?:-\d+)?(?!\d)"

_HEAD_RE = re.compile(
    rf"\b(?:(?P<tk>Tables?|tables?|Figures?){_SP}(?P<tn>{_CAPTION_NUM})"
    rf"|(?P<ck>clauses?|subclauses?|sections?|Annex){_SP}(?P<cn>{_CLAUSE_NUM})){_END}"
)
_SEP_RE = re.compile(rf",?{_SP}(?P<conj>and|or|to){_SP}|,[^\S\n]*")
_CAPTION_NUM_RE = re.compile(rf"{_CAPTION_NUM}{_END}")
_CLAUSE_NUM_RE = re.compile(rf"{_CLAUSE_NUM}{_END}")

_DESIG = (
    rf"(?:(?<![A-Za-z])TS{_SP}(?P<ts>{_SPEC})(?:{_SP}\[(?P<tn>\d+)\])?"
    rf"|\[(?P<bn>\d+)(?:,[^\S\n]*TS{_SP}(?P<bts>{_SPEC}))?\])"
)
_TRAIL_RE = re.compile(rf"{_SP}(?:of|in){_SP}{_DESIG}")
_PREFIX_RE = re.compile(rf"{_DESIG},?{_SP}\Z")
_PREFIX_WINDOW = 48

_SINGULAR_CLAUSE = {"clause", "subclause", "section"}

_FENCE_RE = re.compile(r"(```|~~~)")
_INLINE_RE = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$|<[A-Za-z/!][^<>]*>", re.S)


@dataclass(frozen=True)
class Ref:
    start: int
    end: int
    text: str
    line: int
    kind: str
    target_id: str
    target_spec_number: str
    target_code: str | None
    status: str
    target: Target | None


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def protected_spans(text: str) -> list[tuple[int, int]]:
    """참조로 보지 않는 구간 (start, end) 목록. 정렬되고 겹치지 않는다."""
    lines = text.split("\n")
    offsets = []
    pos = 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln) + 1

    def line_end(i: int) -> int:
        return min(offsets[i] + len(lines[i]) + 1, len(text))

    spans: list[tuple[int, int]] = []
    first = 0
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                spans.append((0, line_end(i)))
                first = i + 1
                break

    line_spans: list[tuple[int, int]] = []
    fence_start = None
    for i in range(first, len(lines)):
        ln = lines[i]
        if fence_start is not None:
            if _FENCE_RE.match(ln):
                line_spans.append((fence_start, line_end(i)))
                fence_start = None
            continue
        if _FENCE_RE.match(ln):
            fence_start = offsets[i]
        elif ln.startswith(("#", "**Table ", "*Figure ")):
            line_spans.append((offsets[i], line_end(i)))
    if fence_start is not None:
        line_spans.append((fence_start, len(text)))

    # 수식·HTML 태그는 줄 단위 보호 구간 바깥에서만 찾는다($가 펜스 안팎으로 짝지어지지 않게).
    blocked = _merge(spans + line_spans)
    gap = 0
    for a, b in blocked + [(len(text), len(text))]:
        if a > gap:
            for m in _INLINE_RE.finditer(text, gap, a):
                spans.append(m.span())
        gap = max(gap, b)
    return _merge(spans + line_spans)


def _overlaps(spans: list[tuple[int, int]], starts: list[int], a: int, b: int) -> bool:
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0 and spans[i][1] > a:
        return True
    return i + 1 < len(spans) and spans[i + 1][0] < b


def _desig_spec(m: re.Match, spec: SpecIndex) -> str:
    if m.group("ts"):
        return m.group("ts")
    if m.group("bts"):
        return m.group("bts")
    n = m.group("tn") or m.group("bn")
    return spec.references.get(n, "")


def _resolve(kind: str, ident: str, number: str | None, spec: SpecIndex,
             corpus: CorpusIndex) -> tuple[str, str | None, str, Target | None]:
    if number == "":    # 참고문헌 [n]이 3GPP 규격이 아님(또는 목록에 없음)
        return "", None, "missing_spec", None
    if number is None or number == spec.spec_number:
        target_spec = spec
    else:
        code = corpus.by_number.get(number)
        if code is None:
            return number, None, "missing_spec", None
        target_spec = corpus.specs[code]
    store = {"table": target_spec.tables, "figure": target_spec.figures,
             "clause": target_spec.clauses}[kind]
    t = store.get(ident)
    if t is None:
        return target_spec.spec_number, target_spec.code, "missing_target", None
    if t.ambiguous:
        return target_spec.spec_number, target_spec.code, "ambiguous", None
    return target_spec.spec_number, target_spec.code, "resolved", t


def find_refs(text: str, spec: SpecIndex, corpus: CorpusIndex) -> list[Ref]:
    """본문 참조를 찾아 해석한다. start 순으로 정렬해 돌려준다."""
    spans = protected_spans(text)
    starts = [a for a, _ in spans]
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    refs: list[Ref] = []
    pos = 0
    consumed = 0    # 뒤쪽 지시로 쓴 텍스트 끝: 앞쪽 지시로 다시 쓰지 않는다
    while True:
        m = _HEAD_RE.search(text, pos)
        if m is None:
            break
        pos = m.end()
        if _overlaps(spans, starts, m.start(), m.end()):
            continue
        if m.group("tk"):
            word = m.group("tk")
            kind = "figure" if word.startswith("F") else "table"
            num_re = _CAPTION_NUM_RE
            items = [(m.start(), m.end(), m.group("tn"))]
            elide_needs_dot = False
        else:
            word = m.group("ck")
            kind = "clause"
            num_re = _CLAUSE_NUM_RE
            items = [(m.start(), m.end(), m.group("cn"))]
            elide_needs_dot = word in _SINGULAR_CLAUSE

        # 나열: X and Y, X, Y and Z, X or Y, X to Y (뒤 번호는 단어 생략)
        # 꼬리 전체 뒤에 규격 지시가 오면 나열로 확정하고 전부 남긴다. 지시가 없으면
        # 쉼표만으로 이어진 꼬리와, 단수 조항 단어 뒤의 점 없는 번호부터는 버린다.
        keep = 1
        dotted = True
        cur = m.end()
        while True:
            s = _SEP_RE.match(text, cur)
            if s is None:
                break
            n = num_re.match(text, s.end())
            if n is None or _overlaps(spans, starts, n.start(), n.end()):
                break
            if elide_needs_dot and "." not in n.group(0):
                dotted = False
            items.append((n.start(), n.end(), n.group(0)))
            cur = n.end()
            if s.group("conj") and dotted:
                keep = len(items)
        t = _TRAIL_RE.match(text, cur)
        if t is None:
            items = items[:keep]
            cur = items[-1][1]
            t = _TRAIL_RE.match(text, cur)

        # 규격 지시: 뒤쪽 우선, 없으면 바로 앞쪽
        number = None
        if t is not None:
            number = _desig_spec(t, spec)
            consumed = t.end()
            pos = max(pos, t.end())
        else:
            lo = max(consumed, m.start() - _PREFIX_WINDOW)
            p = _PREFIX_RE.search(text, lo, m.start())
            if p is not None:
                number = _desig_spec(p, spec)
        pos = max(pos, cur)

        for a, b, ident in items:
            tsn, code, status, target = _resolve(kind, ident, number, spec, corpus)
            refs.append(Ref(
                start=a, end=b, text=text[a:b],
                line=bisect.bisect_right(line_starts, a),
                kind=kind, target_id=ident, target_spec_number=tsn,
                target_code=code, status=status, target=target,
            ))
    refs.sort(key=lambda r: r.start)
    return refs

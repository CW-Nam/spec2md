"""참조 찾기와 해석: 본문의 표·그림·조항 참조를 찾아 목적지 색인으로 해석한다."""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

from .link_index import CorpusIndex, SpecIndex, Target, caption_at, line_sections

# 번호 모양. 각 부분이 점으로 시작하므로 나누는 방법이 하나뿐이라 되돌아가기가 폭주하지 않는다.
_HEAD_SEG = r"(?:\d+[A-Za-z]?|[A-Z])"
_CLAUSE_NUM = rf"{_HEAD_SEG}(?:\.[0-9A-Za-z]+)*"
# 5.2-1, 7.3.1-1aa, 5.2.2.6.2-2E-1. 다른 번호로 이어지면(4.2-1-4.2, 4.2-1.5) 캡션 번호가 아니다.
_CAPTION_NUM = rf"{_CLAUSE_NUM}-\d+[A-Za-z]{{0,2}}(?:-\d+[A-Za-z]{{0,2}})*(?![.\-]\d)"
_END = r"(?![0-9A-Za-z])"
_SP = r"[^\S\n]+"          # 줄바꿈을 뺀 공백(NBSP 포함)
_SP0 = r"[^\S\n]*"
_SPEC = r"\d{2}\.\d{3}(?:-\d+)?(?!\d)"
_TSPEC = r"\d{2}\.?\d{3}(?:-\d+)?(?!\d)"   # TS/TR 뒤에서는 점 없는 번호(TS36133)도 받는다

_HEAD_RE = re.compile(
    rf"\b(?:(?P<tk>[Tt]ables?|[Ff]igures?){_SP}(?P<tn>{_CAPTION_NUM})"
    rf"|(?P<ck>[Cc]lauses?|[Ss]ubclauses?|[Ss]ections?|[Aa]nnex(?:es)?){_SP}(?P<cn>{_CLAUSE_NUM})){_END}"
)
_SEP_RE = re.compile(rf"{_SP0},?{_SP}(?P<conj>and|or|to){_SP}|(?P<slash>/)|{_SP0},{_SP0}")
_SLASH_TAIL_RE = re.compile(r"(?:/[0-9A-Za-z][0-9A-Za-z.\-]*)+")   # 7.3.1.1.2-28/29/30 의 /29/30
_CAPTION_NUM_RE = re.compile(rf"{_CAPTION_NUM}{_END}")
_CLAUSE_NUM_RE = re.compile(rf"{_CLAUSE_NUM}{_END}")
_ANNEX_LIST_NUM_RE = re.compile(rf"(?:{_CLAUSE_NUM}|[A-Z]\d+(?:\.[0-9A-Za-z]+)+){_END}")

# 규격 지시: [3GPP ]TS|TR nn.nnn[ [n]], [n], [n, TS nn.nnn], [n. TS nn.nnn], [n TS nn.nnn],
# [n, nn.nnn], [TS nn.nnn], [nn.nnn]
_DESIG = (
    rf"(?:(?:(?<![A-Za-z])|(?<=\bof))(?:3GPP{_SP})?T[SR]{_SP0}(?P<ts>{_TSPEC})(?:{_SP0}\[(?P<tn>\d+)\])?"
    rf"|\[(?P<bn>\d+)\]"
    rf"|\[(?:(?P<bn2>\d+)[.,]?{_SP0})?(?:(?:3GPP{_SP})?T[SR]{_SP0})?(?P<bts>{_SPEC})\]"
    rf"|(?P<own>(?:present|this){_SP}(?:document|specification))\b)"
)
# "of"와 TS를 붙여 쓰기도 한다("clause 5.1.1.2 ofTS 36.213 [2]").
_OF = (rf"{_SP}(?:(?:as{_SP})?(?:defined|specified|described|given){_SP})?"
       rf"(?:of|in|from)(?:{_SP}(?:the{_SP})?|(?=T[SR]{_SP0}\d))")
_TS_AHEAD = rf"(?:3GPP{_SP})?T[SR]{_SP0}{_TSPEC}"
# 뒤쪽 지시에서만 TS 없는 규격 번호도 받는다("table 6.3.5.2.1-1 of 36.101[5]", "of 38.101-1 [2]").
# 3GPP 규격 번호 계열(2x~5x)만 받아 "of 10.000 MHz" 같은 값과 섞이지 않게 한다.
_TRAIL_DESIG = (_DESIG[:-1]
                + rf"|(?P<bare>[2-5]\d\.\d{{3}}(?:-\d+)?)(?![\d.])(?:{_SP0}\[(?P<bare_n>\d+)\])?)")
# 뒤쪽 지시: "of|in|from …", "defined in …", 번호 바로 뒤의 대괄호("clause 5.4.2.1 [5, TS 38.212]"),
# 공백만 두고 바로 붙은 TS("clause 10.2.6 TS 36.211 [16]"), 괄호를 닫는 쉼표 뒤 TS("(clause 4.2.7.9, TS 38.306 [22])").
# 쉼표 뒤 TS가 괄호로 닫히지 않으면 다음 참조의 앞쪽 지시일 수 있어 쓰지 않는다("clause 5.5, TS 25.104 [6] clause 5.2").
_TRAIL_RE = re.compile(
    rf"(?:{_OF}|{_SP0}(?=\[)|{_SP}(?={_TS_AHEAD})"
    rf"|{_SP0},{_SP}(?={_TS_AHEAD}(?:{_SP0}\[\d+\])?{_SP0}\))){_TRAIL_DESIG}")
# 다른 문서를 가리키는 듯하지만 3GPP 규격 지시로 읽히지 않는 꼬리(IETF RFC, IEEE Std, TS 오타 …).
# 이때는 현재 규격 안에서 해석하지 않는다(틀린 링크 금지).
# 번호가 바로 붙을 수 있다(RFC3550, IEEE802.11). ETR/ETS만 낱말 끝을 확인한다.
_OTHER_DOCUMENT = r"(?:RFC|IETF|IEEE|ITU|ETSI|ANSI|ISO|ET[RS](?![A-Za-z]))"
_OTHER_RE = re.compile(rf"{_OF}(?:3GPP|T[SR](?:\d|\b)|{_OTHER_DOCUMENT}|\[)")
_PREFIX_RE = re.compile(rf"{_DESIG}(?:{_SP0},)?{_SP}\Z")
# 참조를 둘러싼 대괄호의 여는 부분: [n, …] 또는 [다른 문서 …]
_BRACKET_OPEN_RE = re.compile(rf"\[(?:(?P<cite>\d+){_SP0},|{_OTHER_DOCUMENT})")
_BRACKET_CLOSE_RE = re.compile(r"[^\[\]\n]*\]")
_GAP_RE = re.compile(rf"{_SP}\Z")
_PREFIX_WINDOW = 48
_NO_SPEC = ""    # _resolve: 지시는 있으나 3GPP 규격으로 읽을 수 없음

_SINGULAR_CLAUSE = {"clause", "subclause", "section"}
_ANNEX_WORDS = {"annex", "annexes"}

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
    override: bool = False    # 사용자가 지정한 대상(--overrides)으로 해석했다


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
        elif ln.startswith(("#", "**Table ", "*Figure ")) or caption_at(lines, i):
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


def _head(m: re.Match) -> tuple[str, str, str]:
    """(kind, 소문자 단어, 번호)."""
    if m.group("tk"):
        word = m.group("tk")
        kind = "figure" if word[0] in "Ff" else "table"
        ident = m.group("tn")
    else:
        word = m.group("ck")
        kind = "clause"
        ident = m.group("cn")
    return kind, word.lower(), ident


def _chain(text: str, cur: int, kind: str, spans: list[tuple[int, int]],
           starts: list[int]) -> tuple[list[tuple[int, int, str]], int]:
    """cur 뒤로 '구분자 + 같은 종류 단어 + 번호 하나'가 되풀이되는 나열
    (Table X, Table Y and Table Z / clause X or Annex Y)."""
    out: list[tuple[int, int, str]] = []
    while True:
        s = _SEP_RE.match(text, cur)
        if s is None:
            break
        h = _HEAD_RE.match(text, s.end())
        if h is None or _overlaps(spans, starts, h.start(), h.end()):
            break
        k, _, ident = _head(h)
        if k != kind:
            break
        out.append((h.start(), h.end(), ident))
        cur = h.end()
    return out, cur


def _trail(text: str, cur: int) -> tuple[re.Match | None, bool]:
    """cur 바로 뒤의 규격 지시와, 3GPP 규격으로 읽을 수 없는 다른 문서 지시가 있는지."""
    t = _TRAIL_RE.match(text, cur)
    return t, t is None and _OTHER_RE.match(text, cur) is not None


def _bracket(text: str, lo: int, start: int, end: int) -> re.Match | None:
    """start..end 참조가 같은 줄의 '[n, … ]' 또는 '[다른 문서 … ]' 안에 있으면 여는 부분 매치."""
    a = text.rfind("[", max(lo, text.rfind("\n", 0, start) + 1), start)
    if a < 0 or "]" in text[a:start]:
        return None
    o = _BRACKET_OPEN_RE.match(text, a)
    return o if o is not None and _BRACKET_CLOSE_RE.match(text, end) else None


def _desig_spec(m: re.Match, spec: SpecIndex) -> str:
    if m.group("own"):
        return spec.spec_number
    ts = m.group("ts") or m.group("bts") or m.groupdict().get("bare")
    if ts:
        return ts if "." in ts else f"{ts[:2]}.{ts[2:]}"
    return spec.references.get(m.group("bn"), _NO_SPEC)


def _by_context(t: Target, ctx: tuple[str, str | None] | None) -> Target | None:
    """모호한 번호의 후보 가운데 참조와 같은 파일·같은 하위 제목 아래에 있는 것이 하나뿐이면 그 후보."""
    if ctx is None:
        return None
    hits = [c for c in t.candidates if (c.file, c.section) == ctx]
    return hits[0] if len(hits) == 1 else None


def _resolve(kind: str, ident: str, number: str | None, spec: SpecIndex,
             corpus: CorpusIndex, ctx: tuple[str, str | None] | None = None,
             ) -> tuple[str, str | None, str, Target | None]:
    if number == _NO_SPEC:    # 참고문헌 [n]이 3GPP 규격이 아님(목록에 없음), 또는 다른 문서 지시
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
    if t is None:    # 대소문자만 다른 번호(본문 5.3.19a, 제목 5.3.19A)는 후보가 하나일 때만 쓴다
        t = target_spec.folded(kind).get(ident.lower())
    if t is None:
        # Void로 비어 있는 번호: 상태는 void, Void 제목·캡션 줄이 있으면 그곳으로 링크한다
        voids = target_spec.voids[kind]
        hit = ident if ident in voids else next((v for v in voids if v.lower() == ident.lower()), None)
        if hit is not None:
            return target_spec.spec_number, target_spec.code, "void", voids[hit]
        return target_spec.spec_number, target_spec.code, "missing_target", None
    if t.ambiguous:
        # 같은 규격 안의 참조만 문맥(파일·하위 제목)으로 고른다
        t = _by_context(t, ctx) if target_spec is spec else None
        if t is None:
            return target_spec.spec_number, target_spec.code, "ambiguous", None
    return target_spec.spec_number, target_spec.code, "resolved", t


def find_refs(text: str, spec: SpecIndex, corpus: CorpusIndex,
              from_file: str | None = None) -> list[Ref]:
    """본문 참조를 찾아 해석한다. start 순으로 정렬해 돌려준다.
    from_file(규격 폴더 기준 경로)을 주면 모호한 번호를 같은 하위 제목 아래의 후보로 고를 수 있다."""
    secs = line_sections(text.split("\n")) if from_file else None
    spans = protected_spans(text)
    starts = [a for a, _ in spans]
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    refs: list[Ref] = []
    pos = 0
    consumed = 0    # 뒤쪽 지시로 쓴 텍스트 끝: 앞쪽 지시로 다시 쓰지 않는다
    carry = None    # (끝, 규격 번호): 앞쪽 지시로 해석한 바로 앞 참조. 공백만 사이에 두고 이어지면 같이 쓴다
    while True:
        m = _HEAD_RE.search(text, pos)
        if m is None:
            break
        pos = m.end()
        if _overlaps(spans, starts, m.start(), m.end()):
            continue
        kind, word, ident = _head(m)
        num_re = _CLAUSE_NUM_RE if kind == "clause" else _CAPTION_NUM_RE
        if word in _ANNEX_WORDS:
            num_re = _ANNEX_LIST_NUM_RE
        items = [(m.start(), m.end(), ident)]
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
            item_id = n.group(0)
            if (elide_needs_dot and "." not in item_id
                    or word in _ANNEX_WORDS and not _CLAUSE_NUM_RE.fullmatch(item_id)):
                dotted = False
            items.append((n.start(), n.end(), item_id))
            cur = n.end()
            if (s.group("conj") or s.group("slash")) and dotted:
                keep = len(items)
        sl = _SLASH_TAIL_RE.match(text, cur)
        t, other = _trail(text, sl.end() if sl else cur)
        if t is None and not other and len(items) > keep:
            items = items[:keep]
            cur = items[-1][1]
            t, other = _trail(text, cur)

        # 규격 지시: 뒤쪽 우선, 없으면 바로 앞쪽
        p = None
        bracket = None
        if t is None and not other:
            lo = max(consumed, m.start() - _PREFIX_WINDOW)
            bracket = _bracket(text, consumed, m.start(), cur)
            if bracket is None:
                p = _PREFIX_RE.search(text, lo, m.start())
            elif bracket["cite"] is not None:
                p = _PREFIX_RE.search(text, max(consumed, bracket.start() - _PREFIX_WINDOW),
                                      bracket.start())
                # "TS 38.214 [5, clause 4]"는 앞 지시를 쓰지만, 앞 지시에 다른 참고문헌 번호가
                # 붙어 있으면("TS 38.331 [2], [5, clause 4]") 대괄호 안 번호를 쓴다.
                own = p and (p["tn"] or p["bn"] or p["bn2"])
                if own and own != bracket["cite"]:
                    p = None
            # 같은 단어가 되풀이되는 나열(Table X, Table Y and Table Z of [2])은 지시를 함께 쓴다.
            # 첫 항목 바로 앞에 지시가 있으면 그 지시를 쓰고, 이때 나열 뒤 지시는 뒤 항목에만 남긴다.
            clause_range = (kind == "clause" and len(items) == 2
                            and _SEP_RE.match(text, m.end())["conj"] == "to")
            if bracket is None and (len(items) == 1 or clause_range):
                chain, chain_end = _chain(text, cur, kind, spans, starts)
                # "clause X to Y and Annex Z of TR ..."도 하나의 문서를 가리킨다.
                if chain and (not clause_range or text[chain[0][0]:chain[0][1]].lower().startswith("annex")):
                    ct, cother = _trail(text, chain_end)
                    if not clause_range and p is not None and ct is None and not cother:
                        items += chain
                        cur = chain_end
                    elif p is None and (ct is not None or cother):
                        items += chain
                        cur = chain_end
                        t, other = ct, cother
        number = None
        if other:
            number = _NO_SPEC
        elif t is not None:
            number = _desig_spec(t, spec)
            consumed = t.end()
            pos = max(pos, t.end())
        elif p is not None:
            number = _desig_spec(p, spec)
        elif bracket is not None:
            number = spec.references.get(bracket["cite"], _NO_SPEC)
        elif carry is not None and carry[0] < m.start() and _GAP_RE.match(text[carry[0]:m.start()]):
            # "TS 36.211 clause 4.2 Table 4.2-2"
            number = carry[1]
        carry = (cur, number) if t is None and not other and number is not None else None
        pos = max(pos, cur)

        for a, b, ident in items:
            line = bisect.bisect_right(line_starts, a)
            ctx = (from_file, secs[line - 1]) if secs is not None else None
            tsn, code, status, target = _resolve(kind, ident, number, spec, corpus, ctx)
            refs.append(Ref(
                start=a, end=b, text=text[a:b],
                line=line,
                kind=kind, target_id=ident, target_spec_number=tsn,
                target_code=code, status=status, target=target,
            ))
    refs.sort(key=lambda r: r.start)
    return refs

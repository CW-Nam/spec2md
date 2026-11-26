"""렌더링: 앵커 줄, 참조 링크, 미디어 경로, 역참조 절을 raw 본문에 넣는다."""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass

from .link_index import SpecIndex, Target
from .link_refs import Ref

_TABLE_TAG_RE = re.compile(r"<(/?)table\b[^>]*>?", re.I)
BACKLINKS_MARKER = "<!-- spec2md:backlinks -->"


@dataclass(frozen=True)
class Backlink:
    from_code: str
    from_spec_number: str
    from_file: str
    from_clause: str
    text: str
    target_anchor: str | None


def href(from_code: str, from_file: str, to_code: str, target: Target) -> str:
    """from_code의 from_file에서 to_code의 target으로 가는 상대 경로(항상 '/')."""
    start = posixpath.dirname(posixpath.join("/", from_code, from_file))
    dest = posixpath.join("/", to_code, target.file)
    path = posixpath.relpath(dest, start)
    return f"{path}#{target.anchor}" if target.anchor else path


def table_spans(text: str) -> list[tuple[int, int]]:
    """바깥 <table> ... </table> 구간(중첩은 깊이로 센다). 닫히지 않으면 끝까지."""
    spans: list[tuple[int, int]] = []
    depth, begin = 0, 0
    for m in _TABLE_TAG_RE.finditer(text):
        if m.group(1):
            if depth:
                depth -= 1
                if depth == 0:
                    spans.append((begin, m.end()))
        else:
            if depth == 0:
                begin = m.start()
            depth += 1
    if depth:
        spans.append((begin, len(text)))
    return spans


def render(text: str, refs: list[Ref], spec: SpecIndex, from_file: str,
           media_prefix: str, backlinks: list[Backlink]) -> str:
    spans = table_spans(text)
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]

    # (시작, 끝, 대체 문자열, 순서): 뒤에서부터 적용한다. 같은 위치면 링크가 앵커 줄보다 먼저.
    edits: list[tuple[int, int, str, int]] = []
    for r in refs:
        if r.status != "resolved" or r.target is None or r.target_code is None:
            continue
        link = href(spec.code, from_file, r.target_code, r.target)
        in_table = any(a <= r.start and r.end <= b for a, b in spans)
        rep = f'<a href="{link}">{r.text}</a>' if in_table else f"[{r.text}]({link})"
        edits.append((r.start, r.end, rep, 0))

    anchors: dict[int, set[str]] = {}
    seen: set[str] = set()
    for store in (spec.clauses, spec.tables, spec.figures):
        for t in store.values():
            if t.file != from_file or not t.anchor or t.ambiguous:
                continue
            if not 1 <= t.line <= len(line_starts):
                continue
            anchors.setdefault(t.line, set()).add(t.anchor)
    for line in sorted(anchors):
        names = anchors[line]
        block = ""
        for name in sorted(names):
            if name in seen:
                continue
            seen.add(name)
            block += f'<a id="{name}"></a>\n'
        if block:
            pos = line_starts[line - 1]
            edits.append((pos, pos, block, 1))

    out = text
    for a, b, rep, _ in sorted(edits, key=lambda e: (-e[0], e[3])):
        out = out[:a] + rep + out[b:]

    out = out.replace("](../media/", f"]({media_prefix}").replace('src="../media/', f'src="{media_prefix}')

    if backlinks:
        uniq = {(b.from_file, b.target_anchor, b.text, b.from_spec_number, b.from_code, b.from_clause): b
                for b in backlinks}
        seen_keys: set[tuple] = set()
        rows: list[str] = []
        for b in sorted(uniq.values(), key=lambda b: (b.from_spec_number, b.from_file, b.text,
                                                      b.target_anchor or "")):
            key = (b.from_file, b.target_anchor, b.text)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            link = href(spec.code, from_file, b.from_code, Target(b.from_file, None, 1))
            rows.append(f"- [TS {b.from_spec_number} {b.from_clause}]({link}) — {b.text}")
        out = out.rstrip("\n") + "\n\n" + BACKLINKS_MARKER + "\n## Referenced by\n\n" + "\n".join(rows) + "\n"
    return out

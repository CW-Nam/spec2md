"""link 전체 실행: raw 코퍼스를 읽어 링크·앵커·역참조가 들어간 사본을 OUT에 쓴다."""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field, replace

from .link_index import CorpusIndex, Target, build_corpus_index
from .link_refs import find_refs
from .link_render import Backlink, render

STATUSES = ("resolved", "missing_target", "missing_spec", "ambiguous", "void")


@dataclass
class LinkStats:
    specs: int = 0
    files: int = 0
    refs: dict[str, int] = field(default_factory=dict)
    per_spec: dict[str, dict[str, int]] = field(default_factory=dict)
    overrides: int = 0                                     # 적용한 사용자 지정 항목 수
    warnings: list[str] = field(default_factory=list)     # 적용하지 못한 사용자 지정 항목


_OVERRIDE_KEYS = ("spec", "file", "line", "text", "target_spec", "target_id")


def _load_overrides(path: str | None) -> list[dict]:
    """사용자 지정 대상 파일({"overrides": [...]}). 파일이 없으면 빈 목록."""
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        items = json.load(f).get("overrides", [])
    for n, o in enumerate(items):
        missing = [k for k in _OVERRIDE_KEYS if k not in o]
        if missing:
            raise ValueError(f"{path}: override #{n + 1} lacks {', '.join(missing)}")
    return items


def _override_target(o: dict, kind: str, corpus: CorpusIndex) -> tuple[str | None, Target | None]:
    code = corpus.by_number.get(o["target_spec"])
    if code is None:
        return None, None
    spec = corpus.specs[code]
    store = {"table": spec.tables, "figure": spec.figures, "clause": spec.clauses}[kind]
    t = store.get(o["target_id"]) or spec.folded(kind).get(o["target_id"].lower())
    if t is not None and t.ambiguous:    # 같은 번호가 여럿이면 target_file(과 target_anchor)로 고른다
        hits = [c for c in t.candidates if c.file == o.get("target_file")
                and o.get("target_anchor") in (None, c.anchor)]
        t = hits[0] if len(hits) == 1 else None
    return code, t


def _apply_overrides(items: list[dict], refs_by: dict, corpus: CorpusIndex, stats: LinkStats) -> None:
    """(규격, 파일, 줄, 참조 텍스트)가 같은 참조를 사용자가 지정한 대상으로 해석한다."""
    for o in items:
        refs = refs_by.get((o["spec"], o["file"]), [])
        hits = [i for i, r in enumerate(refs) if r.line == o["line"] and r.text == o["text"]]
        where = f"{o['spec']}/{o['file']}:{o['line']} {o['text']!r}"
        if not hits:
            stats.warnings.append(f"override not applied: no reference at {where}")
            continue
        kind = refs[hits[0]].kind
        code, t = _override_target(o, kind, corpus)
        if code is None or t is None:
            stats.warnings.append(f"override not applied: target not found: TS {o['target_spec']} "
                                  f"{kind} {o['target_id']} (for {where})")
            continue
        for i in hits:
            refs[i] = replace(refs[i], target_spec_number=corpus.specs[code].spec_number, target_code=code,
                              target_id=o["target_id"], status="resolved", target=t, override=True)
        stats.overrides += 1


def _real(p: str) -> str:
    return os.path.normcase(os.path.realpath(p))


def _inside(child: str, parent: str) -> bool:
    try:
        return os.path.commonpath([child, parent]) == parent and child != parent
    except ValueError:
        return False


def _check_roots(raw_root: str, out_root: str) -> None:
    raw, out = _real(raw_root), _real(out_root)
    if raw == out or _inside(raw, out) or _inside(out, raw):
        raise ValueError(f"unsafe output directory {out_root!r}: must be separate from raw {raw_root!r}")


def _clear_spec_dir(out_root: str, code: str) -> str:
    path = os.path.join(out_root, code)
    if os.path.islink(path) or (os.path.lexists(path) and not os.path.isdir(path)):
        raise ValueError(f"refusing to replace non-directory or symlink {path!r}")
    expected = os.path.join(_real(out_root), os.path.normcase(code))
    if _real(path) != expected or not _inside(_real(path), _real(out_root)):
        raise ValueError(f"refusing to clear {path!r}: not strictly inside {out_root!r}")
    if os.path.isdir(path):
        shutil.rmtree(path)
    return path


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _dump(path: str, obj) -> None:
    _write(path, json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=1) + "\n")


def _tdict(t: Target) -> dict:
    if t.ambiguous:
        return {"ambiguous": True, "candidates": [{"file": c.file, "anchor": c.anchor} for c in t.candidates]}
    return {"file": t.file, "anchor": t.anchor}


def _index_json(corpus: CorpusIndex) -> dict:
    out = {}
    for code, s in corpus.specs.items():
        out[code] = {
            "spec_number": s.spec_number, "version": s.version, "release": s.release,
            "clauses": {k: _tdict(t) for k, t in s.clauses.items()},
            "tables": {k: _tdict(t) for k, t in s.tables.items()},
            "figures": {k: _tdict(t) for k, t in s.figures.items()},
        }
    return out


def _read(path: str) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def run_link(raw_root: str, out_root: str, only: set[str] | None = None,
             overrides: str | None = None) -> LinkStats:
    """overrides: 사용자 지정 대상 파일 경로(없으면 무시)."""
    _check_roots(raw_root, out_root)
    override_items = _load_overrides(overrides)
    stats = LinkStats(refs={s: 0 for s in STATUSES})
    corpus = build_corpus_index(raw_root)
    if only:
        unknown = sorted(only - set(corpus.specs))
        if unknown:
            raise ValueError(f"unknown spec code(s): {', '.join(unknown)}")
    selected = [c for c in corpus.specs if not only or c in only]

    # 1) 모든 규격의 참조를 한 번씩 계산한다 (역참조는 항상 전체 코퍼스 기준).
    texts: dict[tuple[str, str], str] = {}
    refs_by: dict[tuple[str, str], list] = {}
    clause_of: dict[tuple[str, str], str] = {}
    manifests: dict[str, dict] = {}
    for code, spec in corpus.specs.items():
        with open(os.path.join(raw_root, code, "manifest.json"), encoding="utf-8") as f:
            manifests[code] = json.load(f)
        for e in manifests[code].get("clauses", []):
            if e.get("file"):
                clause_of.setdefault((code, e["file"]), e["clause"])
        for rel in spec.files:
            text = _read(os.path.join(raw_root, code, *rel.split("/")))
            texts[(code, rel)] = text
            refs_by[(code, rel)] = find_refs(text, spec, corpus, rel)
    _apply_overrides(override_items, refs_by, corpus, stats)

    backlinks: dict[tuple[str, str], list[Backlink]] = {}
    for (code, rel), refs in refs_by.items():
        spec = corpus.specs[code]
        for r in refs:
            if r.status not in ("resolved", "void") or r.target is None or r.target_code is None:
                continue
            if (r.target_code, r.target.file) == (code, rel):
                continue
            backlinks.setdefault((r.target_code, r.target.file), []).append(Backlink(
                from_code=code, from_spec_number=spec.spec_number, from_file=rel,
                from_clause=clause_of.get((code, rel), ""), text=r.text,
                target_anchor=r.target.anchor))

    # 2) 쓰기
    os.makedirs(out_root, exist_ok=True)
    _dump(os.path.join(out_root, "index.json"), _index_json(corpus))
    abs_out = os.path.abspath(out_root)
    for code in selected:
        spec = corpus.specs[code]
        spec_out = _clear_spec_dir(out_root, code)
        media_prefix = os.path.relpath(
            os.path.join(os.path.abspath(raw_root), code, "media"),
            os.path.join(abs_out, code, "clauses")).replace(os.sep, "/") + "/"
        counts = {s: 0 for s in STATUSES}
        rows = []
        for rel in spec.files:
            refs = refs_by[(code, rel)]
            md = render(texts[(code, rel)], refs, spec, rel, media_prefix,
                        backlinks.get((code, rel), []))
            _write(os.path.join(spec_out, *rel.split("/")), md)
            stats.files += 1
            for r in refs:
                counts[r.status] = counts.get(r.status, 0) + 1
                rows.append((rel, r.line, r.start, {
                    "from_file": rel, "from_clause": clause_of.get((code, rel), ""),
                    "line": r.line, "text": r.text, "kind": r.kind,
                    "target_spec": r.target_spec_number, "target_id": r.target_id,
                    "target_file": r.target.file if r.target else None,
                    "anchor": r.target.anchor if r.target else None,
                    "status": r.status, **({"override": True} if r.override else {})}))
        rows.sort(key=lambda x: x[:3])
        manifest = dict(manifests[code])
        manifest["link"] = {"refs": counts}
        _dump(os.path.join(spec_out, "manifest.json"), manifest)
        _dump(os.path.join(spec_out, "refs.json"),
              {"spec": spec.code, "version": spec.version, "refs": [x[3] for x in rows]})
        stats.specs += 1
        stats.per_spec[code] = counts
        for k, v in counts.items():
            stats.refs[k] = stats.refs.get(k, 0) + v
    if only and len(selected) < len(corpus.specs):
        print("warning: --only: 'Referenced by' sections of specs not selected are not updated",
              file=sys.stderr)
    return stats

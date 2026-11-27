"""linked/*/refs.json에서 resolved가 아닌 참조를 모아 점검·수정용 HTML을 만든다.
사용: python mk_unresolved.py <repo_root> <out.html> [overrides.json]

overrides.json(기본: out.html과 같은 폴더의 05_link_overrides.json)은 HTML에서 사용자가 고른 대상을
저장하는 파일이다. `spec2md link raw -o linked --overrides <파일>`이 이 파일을 읽어 반영한다.
HTML에는 기존 지정 항목과 그 적용 상태(적용됨 / 대상 없음 / 참조 위치 없음)도 함께 넣는다."""
import json, os, re, sys

root, out = sys.argv[1], sys.argv[2]
out_dir = os.path.dirname(os.path.abspath(out))
ov_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(out_dir, "05_link_overrides.json")
raw_root, linked_root = os.path.join(root, "raw"), os.path.join(root, "linked")
ANCHOR = re.compile(r'^<a id="[^"]*"></a>$')
index = json.load(open(os.path.join(linked_root, "index.json"), encoding="utf-8"))
STORES = {"clause": "clauses", "table": "tables", "figure": "figures"}
MAX_CAND = 6


def read_lines(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read().split("\n")


def rel_link(p):
    # 출력 HTML 위치 기준 상대경로 (파일 링크라 줄 번호는 붙일 수 없다)
    return os.path.relpath(p, out_dir).replace("\\", "/")


def vkey(v):
    return tuple(int(x) for x in v.split(".") if x.isdigit())


# 규격 번호 -> 가장 높은 버전의 코드 (spec2md link와 같은 규칙)
by_number = {}
for code, s in index.items():
    cur = by_number.get(s["spec_number"])
    if cur is None or vkey(s["version"]) > vkey(index[cur]["version"]):
        by_number[s["spec_number"]] = code
folded = {}    # (규격 번호, 종류) -> 소문자 번호 -> 번호. 대소문자만 다른 번호가 여럿이면 None
for sn, code in by_number.items():
    for kind in STORES:
        f = folded[(sn, kind)] = {}
        for k in index[code][STORES[kind]]:
            f[k.lower()] = None if k.lower() in f else k


def base(sn):
    return sn.split("-")[0]


def candidates(r, src):
    """같은 번호(대소문자 무시)가 있는 로컬 규격의 위치. 대상 규격, 같은 기본 번호(38.101-x)나 출발 규격,
    그 밖의 규격 순. 조항 번호(5.1 등)는 어느 규격에나 있어 그 밖의 규격은 후보로 내지 않는다."""
    kind, tid, ts = r["kind"], r["target_id"], r["target_spec"] or ""
    out = []
    for sn, code in by_number.items():
        store = index[code][STORES[kind]]
        key = tid if tid in store else folded[(sn, kind)].get(tid.lower())
        if key is None:
            continue
        e = store[key]
        rank = 0 if sn == ts else 1 if base(sn) in (base(ts), base(src)) else 2
        if rank == 2 and kind == "clause":
            continue
        if e.get("ambiguous"):
            for c in e.get("candidates", []):
                out.append((rank, sn, key, c["file"], c["anchor"]))
        else:
            out.append((rank, sn, key, None, None))
    out.sort(key=lambda x: (x[0], x[1], x[3] or ""))
    return [list(x[1:]) for x in out[:MAX_CAND]]


overrides = []
if os.path.isfile(ov_path):
    overrides = json.load(open(ov_path, encoding="utf-8")).get("overrides", [])
ov_key = {(o["spec"], o["file"], o["line"], o["text"]): o for o in overrides}
ov_state = {}

rows = []
for code in sorted(index):
    number = index[code]["spec_number"]
    refs = json.load(open(os.path.join(linked_root, code, "refs.json"), encoding="utf-8"))["refs"]
    for r in refs:
        k = (code, r["from_file"], r["line"], r["text"])
        if k in ov_key:
            prev = ov_state.get(k)
            ov_state[k] = "applied" if r.get("override") or prev == "applied" else "target_missing"
    shown = [r for r in refs if r["status"] != "resolved" or r.get("override")]
    cache = {}
    for r in shown:
        rel = r["from_file"]
        if rel not in cache:
            rp = os.path.join(raw_root, code, *rel.split("/"))
            lp = os.path.join(linked_root, code, *rel.split("/"))
            raw_lines = read_lines(rp)
            # raw 줄 번호 → linked 줄 번호 (앵커 줄만 끼어든다)
            m, n = {}, 0
            for i, ln in enumerate(read_lines(lp), 1):
                if ANCHOR.match(ln):
                    continue
                n += 1
                m.setdefault(n, i)
            cache[rel] = (rp, lp, raw_lines, m)
        rp, lp, raw_lines, m = cache[rel]
        ln = r["line"]
        body = raw_lines[ln - 1] if 0 < ln <= len(raw_lines) else ""
        rows.append({
            "s": "override" if r.get("override") else r["status"], "c": code, "n": number,
            "cl": r["from_clause"], "f": rel, "l": ln, "ll": m.get(ln, ln), "t": r["text"], "k": r["kind"],
            "ts": r["target_spec"] or "", "ti": r["target_id"],
            "ur": rel_link(rp), "ul": rel_link(lp), "b": body,
            "cand": [] if r.get("override") else candidates(r, number),
        })

for o in overrides:
    o["state"] = ov_state.get((o["spec"], o["file"], o["line"], o["text"]), "stale")

# 직접 입력한 번호를 브라우저에서 확인할 수 있게 규격별 번호 목록을 넣는다(줄바꿈으로 이은 문자열,
# 같은 번호가 여러 곳인 모호한 번호는 앞에 "*")
keys = {sn: {kind[0]: "\n".join(("*" if e.get("ambiguous") else "") + k
                                 for k, e in index[code][STORES[kind]].items()) for kind in STORES}
        for sn, code in by_number.items()}
payload = {"rows": rows, "overrides": overrides, "keys": keys,
           "ovfile": os.path.relpath(ov_path, root).replace("\\", "/")}
data = json.dumps(payload, ensure_ascii=False).replace("</", r"<\/")
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "unresolved_tpl.html"), encoding="utf-8").read()
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write(tpl.replace("/*DATA*/{}", data))
applied = sum(o["state"] == "applied" for o in overrides)
print(len(rows), "rows ->", out, f"(overrides: {applied}/{len(overrides)} applied)")

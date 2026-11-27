"""linked/*/refs.json에서 resolved가 아닌 참조를 모아 점검용 HTML을 만든다.
사용: python mk_unresolved.py <repo_root> <out.html>"""
import json, os, re, sys, html

root, out = sys.argv[1], sys.argv[2]
raw_root, linked_root = os.path.join(root, "raw"), os.path.join(root, "linked")
ANCHOR = re.compile(r'^<a id="[^"]*"></a>$')
index = json.load(open(os.path.join(linked_root, "index.json"), encoding="utf-8"))

def read_lines(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read().split("\n")

out_dir = os.path.dirname(os.path.abspath(out))

def rel_link(p):
    # 출력 HTML 위치 기준 상대경로 (파일 링크라 줄 번호는 붙일 수 없다)
    return os.path.relpath(p, out_dir).replace("\\", "/")

rows = []
for code in sorted(index):
    refs = json.load(open(os.path.join(linked_root, code, "refs.json"), encoding="utf-8"))["refs"]
    bad = [r for r in refs if r["status"] != "resolved"]
    cache = {}
    for r in bad:
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
            "s": r["status"], "c": code, "n": index[code]["spec_number"], "cl": r["from_clause"],
            "f": rel, "l": ln, "ll": m.get(ln, ln), "t": r["text"], "k": r["kind"],
            "ts": r["target_spec"] or "", "ti": r["target_id"],
            "ur": rel_link(rp), "ul": rel_link(lp), "b": body,
        })

data = json.dumps(rows, ensure_ascii=False).replace("</", r"<\/")
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "unresolved_tpl.html"), encoding="utf-8").read()
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write(tpl.replace("/*DATA*/[]", data))
print(len(rows), "rows ->", out)

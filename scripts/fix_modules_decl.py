"""同步修正套卷的 modules 声明

背景：
  guokao.json 里图形推理题原本被误标 cat=judge，
  修正为 cat=graph 后，套卷索引里的 modules 声明还没更新：
    声明 [politics 20, common 15, verbal 30, quantity 10, judge 35, data 20]
    实际 [politics 20, common 15, verbal 30, quantity 10, judge 25, graph 10, data 20]

  结果展开卷时按 modules 分组，
  但 graph 模块没声明 → 「图形推理」模块练习取不到题。

修复：
  按题目实际分类重新计算每套卷的 modules 列表，
  保持原有顺序约定（政治/常识/言语/数量/判断/图形/资料）。

用法：
  python scripts/fix_modules_decl.py --dry-run
  python scripts/fix_modules_decl.py --apply
"""

import sys
import io
import os
import json
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "data")
ZT = os.path.join(DATA, "zt")
APPLY = "--apply" in sys.argv

CAT_ORDER = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "law", "shenlun"]
CAT_NAME = {
    "politics": "政治理论", "common": "常识判断", "verbal": "言语理解与表达",
    "quantity": "数量关系", "judge": "判断推理", "graph": "图形推理",
    "data": "资料分析", "law": "法律", "shenlun": "申论",
}


def load_ids():
    allq = {}
    for cat in ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]:
        p = os.path.join(ZT, cat + ".json")
        if not os.path.exists(p):
            continue
        for q in json.load(open(p, encoding="utf-8")):
            allq[str(q.get("id"))] = q
    return allq


def main():
    papers_path = os.path.join(DATA, "zt-papers.json")
    data = json.load(open(papers_path, encoding="utf-8"))
    papers = data["papers"]
    allq = load_ids()

    print("=" * 66)
    print("  同步套卷 modules 声明")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    fixed = 0
    for pi, p in enumerate(papers):
        if p.get("kind") == "shenlun":
            continue
        qids = [str(x) for x in p.get("qids", [])]
        if not qids:
            continue

        # 按题目实际分类统计
        actual = Counter()
        for qid in qids:
            q = allq.get(qid)
            if q:
                actual[q.get("cat") or "?"] += 1

        old_mods = [(m["cat"], m["count"]) for m in p.get("modules", [])]
        new_mods = []
        order = [c for c in CAT_ORDER if c in actual]
        order += [c for c in actual if c not in CAT_ORDER]
        for c in order:
            new_mods.append({
                "cat": c,
                "name": CAT_NAME.get(c, c),
                "count": actual[c],
            })

        old_sum = {c: n for c, n in old_mods}
        changed = old_sum != {m["cat"]: m["count"] for m in new_mods}

        if changed:
            fixed += 1
            print(f"  [{pi}] {p.get('paper','')[:34]}")
            print(f"      旧: {old_mods}")
            print(f"      新: {[(m['cat'], m['count']) for m in new_mods]}")
            p["modules"] = new_mods
            p["moduleCount"] = len(new_mods)

    print()
    print(f"  修正套卷: {fixed}")

    data["meta"]["modulesFixApplied"] = "2026-10-31"

    if APPLY and fixed:
        bak = papers_path + ".bak2"
        if not os.path.exists(bak):
            import shutil
            shutil.copy(papers_path, bak)
        json.dump(data, open(papers_path, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"  已写入 zt-papers.json")

        js = os.path.join(DATA, "zt-papers.js")
        if os.path.exists(js):
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            open(js, "w", encoding="utf-8").write("window.__ZT_PAPERS__ = " + body + ";\n")
            print(f"  已同步 zt-papers.js")
    elif not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

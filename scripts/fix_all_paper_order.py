"""修复行测卷的 qids 顺序：按 modules 声明的模块顺序重排

问题：
  卷 [0] 2026国考副省级（kind=xingce）qids 实际顺序：
    1-15   常识(common)
    16-35  资料分析(data)
    36-45  图形推理(graph)
    46-70  判断推理(judge)
    71-90  政治理论(politics)
    91-105 数量关系(quantity)
    106-135 言语理解(verbal)

  而 modules 声明顺序（正确）：
    politics(20) → common(15) → verbal(30) → quantity(15)
    → judge(25) → graph(10) → data(20)

  用户看到「真题全是政治理论和常识」是因为开始的题确实只有这两类；
  并且计时按模块分配时长会完全错位。

根因：
  fix_paper_order.py 只处理了 kind=guokao 的 8 套卷，
  42 套 kind=xingce 的行测卷顺序从未整理。

修复：
  按卷内 modules 声明顺序重排 qids，同模块内按题目 no 升序。
  若卷内没有 modules 声明，按标准行测顺序推断。

用法：
  python scripts/fix_all_paper_order.py --dry-run
  python scripts/fix_all_paper_order.py --apply
"""

import sys
import io
import os
import json
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
DATA = os.path.join(ROOT, "site", "data")
APPLY = "--apply" in sys.argv

# 标准行测模块顺序
STD_ORDER = ["politics", "common", "verbal", "quantity", "judge", "graph", "data"]


def load_questions():
    """返回 {qid: (cat, no, stem)}"""
    m = {}
    for cat in ["politics", "common", "verbal", "quantity", "judge",
                "graph", "data", "guokao"]:
        p = os.path.join(ZT, cat + ".json")
        if not os.path.exists(p):
            continue
        for q in json.load(open(p, encoding="utf-8")):
            m[str(q.get("id"))] = (
                q.get("cat") or cat,
                q.get("no") if isinstance(q.get("no"), int) else 9999,
                q.get("sub") or "",
            )
    return m


def detect_cat_order(qids, allq):
    """找出该卷实际有哪些 cat，并按 STD_ORDER 排序"""
    cats = set()
    for qid in qids:
        info = allq.get(qid)
        if info:
            cats.add(info[0])
    return [c for c in STD_ORDER if c in cats] + \
           [c for c in cats if c not in STD_ORDER]


def main():
    papers_path = os.path.join(DATA, "zt-papers.json")
    doc = json.load(open(papers_path, encoding="utf-8"))
    papers = doc["papers"]
    allq = load_questions()

    print("=" * 68)
    print("  重排所有行测卷的 qids 顺序")
    print("=" * 68)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print(f"  题目索引: {len(allq)} 题")
    print()

    fixed = 0
    for pi, p in enumerate(papers):
        if p.get("kind") == "shenlun":
            continue
        qids = [str(x) for x in p.get("qids", [])]
        if not qids:
            continue

        # 当前顺序是否已符合
        cur_cats = [allq.get(q, ("?",))[0] for q in qids]

        # 目标顺序：modules 声明优先，否则标准顺序
        mod_cats = [m["cat"] for m in p.get("modules", [])]
        want_order = mod_cats if mod_cats else detect_cat_order(qids, allq)

        # 桶排序
        buckets = defaultdict(list)
        unknown = []
        for qid in qids:
            info = allq.get(qid)
            if not info:
                unknown.append(qid)
                continue
            buckets[info[0]].append((info[1], qid))

        ordered = []
        for cat in want_order:
            # 同模块内按 no 升序
            ordered.extend(qid for _no, qid in sorted(buckets.get(cat, [])))
        # 补充未在 want_order 里的 cat
        for cat in buckets:
            if cat not in want_order:
                ordered.extend(qid for _no, qid in sorted(buckets[cat]))
        ordered.extend(unknown)

        new_cats = [allq.get(q, ("?",))[0] for q in ordered]

        if cur_cats == new_cats:
            continue   # 已经正确

        fixed += 1
        # 显示前几段
        print(f"--- [{pi}] {p.get('paper','')[:40]} ---")
        print(f"  旧: {cur_cats[:10]}{'...' if len(cur_cats)>10 else ''}")
        print(f"  新: {new_cats[:10]}{'...' if len(new_cats)>10 else ''}")

        p["qids"] = ordered
        # 同步 modules 的 count
        from collections import Counter
        cnt = Counter(new_cats)
        new_mods = []
        for cat in want_order:
            if cnt.get(cat):
                new_mods.append({
                    "cat": cat,
                    "name": dict((m["cat"], m.get("name", m["cat"]))
                                 for m in p.get("modules", [])).get(cat, cat),
                    "count": cnt[cat],
                })
        if new_mods:
            p["modules"] = new_mods

    print()
    print(f"  重排卷数: {fixed}")

    if APPLY and fixed:
        bak = papers_path + ".oimportbak"
        if not os.path.exists(bak):
            import shutil
            shutil.copy(papers_path, bak)
        doc["meta"]["orderFixAllApplied"] = "2026-11-01"
        doc["meta"]["orderFixAllCount"] = fixed
        json.dump(doc, open(papers_path, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"  已写入 zt-papers.json")

        js = os.path.join(DATA, "zt-papers.js")
        if os.path.exists(js):
            body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
            open(js, "w", encoding="utf-8").write(
                "window.__ZT_PAPERS__ = " + body + ";\n")
            print(f"  已同步 zt-papers.js")
    elif not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

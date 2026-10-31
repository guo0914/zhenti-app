"""修复套卷 qids 的交错乱序

问题现象：
  打开「完整模拟」，第1题政治、第2题常识、第3题言语……
  看起来像「政治理论里混进了其它模块」，
  实际是所有模块的第1题被交错排列在一起。

根因：
  zt-papers.json 里国考卷的 qids 是交错排列的：
    politics no=1, common no=1, verbal no=1, ..., politics no=2, common no=2 ...
  这不是卷面顺序。真实卷面应该是：
    政治 1-20, 常识 21-35, 言语 36-65, 数量 66-75, 判断 76-90, 资料 91-110 ...
  也就是「按模块分组，组内按题号递增」。

  papers-v5.js 的排序逻辑：
    pool.sort((a,b) => {
      if (a.no !== b.no) return a.no - b.no;   // 先按 no
      return CAT_ORDER.indexOf(a.cat) - ...;   // no 相同才按模块
    });
  因为 no 是「模块内编号」，政治第1题和常识第1题都是 no=1，
  所以各模块的第1题被并列在一起，导致卷面完全错乱。

修复策略（两层）：
  1. 修数据：把 qids 按「模块顺序 + 模块内题号」重排，写回索引
  2. 修前端：排序改为「先按模块顺序，再按题号」

用法：
  python scripts/fix_paper_order.py --dry-run
  python scripts/fix_paper_order.py --apply
"""

import sys
import io
import os
import json
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "data")
ZT = os.path.join(DATA, "zt")

APPLY = "--apply" in sys.argv

CAT_ORDER = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "shenlun"]


def load_questions():
    allq = {}
    for cat in ["politics", "common", "verbal", "quantity", "judge",
                "graph", "data", "guokao"]:
        p = os.path.join(ZT, cat + ".json")
        if not os.path.exists(p):
            continue
        for q in json.load(open(p, encoding="utf-8")):
            allq[str(q.get("id"))] = q
    return allq


def is_interleaved(qids, allq):
    """前 8 题里出现 >= 3 种模块，视为交错乱序"""
    cats = []
    for qid in qids[:8]:
        q = allq.get(qid)
        if q:
            cats.append(q.get("cat"))
    return len(set(c for c in cats if c)) >= 3


def reorder(qids, allq, module_order):
    """按模块顺序分组，组内按模块内题号排序"""
    # module_order: 该卷 modules 声明的顺序
    buckets = defaultdict(list)
    unknown = []

    for qid in qids:
        q = allq.get(qid)
        if not q:
            unknown.append(qid)
            continue
        cat = q.get("cat") or "?"
        buckets[cat].append((int(q.get("no") or 0), qid))

    out = []
    order = module_order + [c for c in buckets if c not in module_order]
    for cat in order:
        for _no, qid in sorted(buckets.get(cat, []), key=lambda x: x[0]):
            out.append(qid)
    out.extend(unknown)
    return out


def main():
    papers_path = os.path.join(DATA, "zt-papers.json")
    data = json.load(open(papers_path, encoding="utf-8"))
    papers = data["papers"]
    allq = load_questions()

    print("=" * 66)
    print("  修复套卷 qids 交错乱序")
    print("=" * 66)
    print(f"  题目总数: {len(allq)}")
    print(f"  套卷总数: {len(papers)}")
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    fixed = 0
    details = []

    for pi, paper in enumerate(papers):
        if paper.get("kind") == "shenlun":
            continue
        qids = [str(x) for x in paper.get("qids", [])]
        if not qids:
            continue
        if not is_interleaved(qids, allq):
            continue

        module_order = [m["cat"] for m in paper.get("modules", [])]
        new = reorder(qids, allq, module_order)
        if new == qids:
            continue

        fixed += 1
        # 生成前后对照
        before_cats = []
        after_cats = []
        for qid in qids[:8]:
            q = allq.get(qid)
            before_cats.append(q.get("cat", "?") if q else "?")
        for qid in new[:8]:
            q = allq.get(qid)
            after_cats.append(q.get("cat", "?") if q else "?")

        details.append({
            "idx": pi,
            "paper": paper.get("paper", "")[:38],
            "before": before_cats,
            "after": after_cats,
        })
        paper["qids"] = new

    print(f"  重排套卷: {fixed}")
    print()
    for d in details:
        print(f"  [{d['idx']}] {d['paper']}")
        print(f"      修复前: {d['before']}")
        print(f"      修复后: {d['after']}")
    print()

    data["meta"]["orderFixApplied"] = "2026-10-31"
    data["meta"]["orderFixCount"] = fixed

    if APPLY:
        bak = papers_path + ".bak"
        if not os.path.exists(bak):
            import shutil
            shutil.copy(papers_path, bak)
            print("  已备份 zt-papers.json.bak")

        json.dump(data, open(papers_path, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"  已写入 {papers_path}")

        js_path = os.path.join(DATA, "zt-papers.js")
        if os.path.exists(js_path):
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            open(js_path, "w", encoding="utf-8").write(
                "window.__ZT_PAPERS__ = " + body + ";\n")
            print(f"  已同步 {js_path}")
    else:
        print("  演练结束。确认无误后加 --apply。")


if __name__ == "__main__":
    main()

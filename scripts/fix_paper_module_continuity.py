"""修复套卷 qids 的「模块被打断」缺陷（最小侵入，不动模块内相对顺序）

问题：
  4 套国考卷的 qids 里，数量关系被拆成两段 —— 9 道在前，1 道（no=10）被排到
  图形推理之后：
    2024 国考地市级   [..., judge, graph, quantity, data]
    2024 国考行政执法 [..., judge, graph, quantity, data]
    2023 国考副省级   [..., graph, data, quantity]
    2023 国考地市级   [..., graph, data, quantity]

  界面表现为「数量关系做完了又冒出一道」「模块题量统计与实际不符」。

根因：
  fix_all_paper_order.py 用 (no, qid) 排序做桶排序，但这几套卷的 no 编号体系
  与卷面题号不一致（judge 的 no 到 40、graph 的 no 到 15），按 no 排序会打乱
  模块内顺序，因此不能直接重跑那个脚本。

修复：
  稳定分组 —— 按 modules 声明顺序，把同 cat 的题聚成一块，
  块内保持现有相对顺序（不重排、不按 no 排序）。
  这样只消除「同一模块被切开」的问题，不影响任何已正确的卷。

用法：
  python scripts/fix_paper_module_continuity.py --dry-run
  python scripts/fix_paper_module_continuity.py --apply
"""

import sys
import io
import os
import json
import shutil
from collections import OrderedDict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
DATA = os.path.join(ROOT, "site", "data")
APPLY = "--apply" in sys.argv

SHARDS = ["politics", "common", "verbal", "quantity", "judge",
          "graph", "data", "guokao"]


def load_cat_map():
    """{qid: cat}"""
    m = {}
    for cat in SHARDS:
        p = os.path.join(ZT, cat + ".json")
        if not os.path.exists(p):
            continue
        for q in json.load(io.open(p, encoding="utf-8")):
            m[str(q.get("id"))] = q.get("cat") or cat
    return m


def block_count(seq):
    """连续段数"""
    n = 0
    for i, c in enumerate(seq):
        if i == 0 or seq[i - 1] != c:
            n += 1
    return n


def regroup(qids, cats, want_order):
    """按 want_order 稳定分组，块内保持原相对顺序"""
    buckets = OrderedDict()
    unknown = []
    for qid in qids:
        c = cats.get(qid)
        if c is None:
            unknown.append(qid)
            continue
        buckets.setdefault(c, []).append(qid)

    ordered = []
    for c in want_order:
        ordered.extend(buckets.pop(c, []))
    for c, items in buckets.items():      # 未在 want_order 里的 cat
        ordered.extend(items)
    ordered.extend(unknown)
    return ordered


def main():
    papers_path = os.path.join(DATA, "zt-papers.json")
    doc = json.load(io.open(papers_path, encoding="utf-8"))
    papers = doc["papers"]
    cats = load_cat_map()

    print("=" * 70)
    print("  修复套卷 qids 的模块连续性（模块被打断）")
    print("=" * 70)
    print("  模式: %s" % ("写入" if APPLY else "演练"))
    print("  题目索引: %d 题" % len(cats))
    print()

    fixed = 0
    skipped_shenlun = 0
    for pi, p in enumerate(papers):
        qids = [str(x) for x in p.get("qids", [])]
        if not qids:
            continue

        known = [q for q in qids if q in cats]
        if not known:
            skipped_shenlun += 1        # 申论卷 id 体系不同，跳过
            continue

        cur_cats = [cats[q] for q in qids if q in cats]
        n_blk_cur = block_count(cur_cats)
        uniq = len(set(cur_cats))
        if n_blk_cur == uniq:
            continue                    # 每个模块已是连续一块

        mod_cats = [m["cat"] for m in p.get("modules", [])]
        want_order = mod_cats if mod_cats else list(OrderedDict.fromkeys(cur_cats))

        ordered = regroup(qids, cats, want_order)
        new_cats = [cats[q] for q in ordered if q in cats]
        n_blk_new = block_count(new_cats)

        print("--- [%d] %s ---" % (pi, p.get("paper", "")[:44]))
        print("  模块数 %d，连续段 旧 %d → 新 %d" % (uniq, n_blk_cur, n_blk_new))
        print("  旧: %s" % cur_cats)
        print("  新: %s" % new_cats)

        p["qids"] = ordered
        fixed += 1

    print()
    print("  需修复卷数: %d" % fixed)
    print("  跳过（申论/无匹配题）: %d" % skipped_shenlun)

    if APPLY and fixed:
        bak = papers_path + ".continuitybak"
        if not os.path.exists(bak):
            shutil.copy(papers_path, bak)
            print("  已备份 %s" % os.path.basename(bak))
        doc["meta"]["moduleContinuityFixed"] = fixed
        body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        io.open(papers_path, "w", encoding="utf-8").write(body)
        print("  已写入 zt-papers.json")

        js = os.path.join(DATA, "zt-papers.js")
        if os.path.exists(js):
            io.open(js, "w", encoding="utf-8").write(
                "window.__ZT_PAPERS__ = " + body + ";\n")
            print("  已同步 zt-papers.js")
    elif not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

"""按分片实际内容重算套卷索引的 modules 计数（幂等）

背景：fix_guokao_material_imgs.py 把 5445878、5893530 两条数学运算题
从 data 分片移到 quantity 分片（guokao 分片里的 gk-2023ds-5445878、
gk-2024ds-5893530、gk-2024xz-5893530 三条副本同样改了 cat）。
zt-papers.json / zt-papers.js 里的 modules 计数是静态快照，不同步的话
「资料分析 21 题 / 数量关系 14 题」这类标签会和实际卷面不符。

做法：只重算受影响卷的 modules 计数，其余字段（qids、noSpan、
orderFix 元信息）原样保留 —— 不能重跑 build_paper_index.py，那会因
guokao 副本与分类分片重复计数把总题数翻倍。

口径：
  · qids 全是 gk-* → 以 guokao 分片为准（App 里国考卷就走这个分片）
  · 否则以 7 个分类分片为准

用法：
  python scripts/sync_paper_modules.py           # 演练
  python scripts/sync_paper_modules.py --apply   # 写入
"""

import io
import json
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "data")
ZT = os.path.join(DATA, "zt")

BASE_CATS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data"]

APPLY = "--apply" in sys.argv


def load(cat):
    d = json.load(open(os.path.join(ZT, cat + ".json"), encoding="utf-8"))
    return d["questions"] if isinstance(d, dict) and "questions" in d else d


def main():
    path = os.path.join(DATA, "zt-papers.json")
    payload = json.load(open(path, encoding="utf-8"))

    base = {cat: load(cat) for cat in BASE_CATS}
    gk = load("guokao")

    changed = 0
    for p in payload["papers"]:
        name = p["paper"]
        is_gk = all(str(x).startswith("gk-") for x in p["qids"][:3])
        pool = gk if is_gk else [q for cat in BASE_CATS for q in base[cat]]
        c = Counter(q.get("cat") for q in pool if (q.get("paper") or "") == name)
        if not c:
            print("  ! 分片里找不到卷，跳过:", name[:46])
            continue

        declared = {m["cat"]: m["count"] for m in p["modules"]}
        actual = {m["cat"]: c.get(m["cat"], 0) for m in p["modules"]}
        if declared == actual:
            continue

        print("  %s" % name[:46])
        print("    before: %s" % declared)
        print("    after : %s" % actual)
        for m in p["modules"]:
            m["count"] = actual[m["cat"]]
        p["total"] = sum(m["count"] for m in p["modules"])
        changed += 1

    if not changed:
        print("  所有卷的 modules 计数都与分片一致，无需同步")
        return

    if not APPLY:
        print()
        print("  演练结束，加 --apply 写入。")
        return

    json.dump(payload, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(DATA, "zt-papers.js"), "w", encoding="utf-8").write(
        "window.__ZT_PAPERS__ = " +
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print()
    print("  已写入 zt-papers.json / zt-papers.js")
    print("  卷数:", len(payload["papers"]),
          " 总题数:", sum(p["total"] for p in payload["papers"]))


if __name__ == "__main__":
    main()

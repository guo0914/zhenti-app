"""用 zt/*.json 回填 zhenti.json 的修复字段

背景：
  分类刷题用 site/data/zhenti.json（3480 题），
  套卷用 site/data/zt/*.json（4520 题），
  两者是同一批题的两个副本。

  之前所有数据修复（横线、材料、选项图片、[图]）都只做了 zt/*.json，
  zhenti.json 一直是旧的，所以分类刷题里 449 道填空题只有 1 道有横线。

修复：
  按 id 匹配，把 zt 里已修正的字段同步到 zhenti.json：
    stem / options / optionImgs / material / materialImgs / imgs
  只在这些字段确实更好时才覆盖（stem 含 ____ 优先）。
"""

import sys
import io
import os
import json
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
P = os.path.join(ROOT, "site", "data", "zhenti.json")
APPLY = "--apply" in sys.argv

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]


def main():
    # 建 zt 索引
    zt = {}
    for c in SHARDS:
        p = os.path.join(ZT, c + ".json")
        if not os.path.exists(p):
            continue
        for q in json.load(open(p, encoding="utf-8")):
            zt[str(q.get("id"))] = q

    data = json.load(open(P, encoding="utf-8"))
    qs = data["questions"]

    print("=" * 70)
    print("  用 zt/*.json 回填 zhenti.json")
    print("=" * 70)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print(f"  zt 索引: {len(zt)} 题   zhenti: {len(qs)} 题")
    print()

    stats = {"stem": 0, "options": 0, "optionImgs": 0,
             "material": 0, "imgs": 0, "未匹配": 0}
    samples = []

    for q in qs:
        qid = str(q.get("id"))
        src = zt.get(qid)
        if not src:
            stats["未匹配"] += 1
            continue

        # stem：源里有 ____ 而当前没有 → 用源的
        cur = q.get("stem") or ""
        new = src.get("stem") or ""
        if "____" in new and "____" not in cur:
            q["stem"] = new
            stats["stem"] += 1
            if len(samples) < 5:
                samples.append((qid, new[:56]))
        elif new and cur != new and "[图]" in cur and "[图]" not in new:
            q["stem"] = new
            stats["stem"] += 1

        # optionImgs
        si = src.get("optionImgs") or []
        if si and any(si) and not (q.get("optionImgs") or []):
            q["optionImgs"] = si
            q["options"] = list(src.get("options") or q.get("options") or [])
            stats["optionImgs"] += 1

        # material
        sm = src.get("material") or ""
        cm = q.get("material") or ""
        if cm and not sm:
            q["material"] = ""
            q.pop("matNo", None)
            stats["material"] += 1

        # imgs
        sg = src.get("imgs") or []
        if sg and not (q.get("imgs") or []):
            q["imgs"] = sg
            stats["imgs"] += 1

    print("  同步结果：")
    for k, v in stats.items():
        print(f"    {k}: {v}")
    if samples:
        print("  样例：")
        for s in samples:
            print(f"    {s[0]}: {s[1]}")

    if APPLY:
        bak = P + ".syncbak"
        if not os.path.exists(bak):
            shutil.copy(P, bak)
        json.dump(data, open(P, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"\n  已写入 zhenti.json")
    else:
        print("\n  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

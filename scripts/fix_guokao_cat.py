"""修复 guokao.json 的分类错误

问题：
  guokao.json 里 80 道图形推理题的 cat 字段是 'judge'，
  正确应是 'graph'。

  后果：
    · 套卷选「图形推理」模块时，从 graph.json 取题
      → guokao 里没有 graph 分类 → 该模块 0 题
    · 「判断推理」模块里混进了图形题
    · 用户看到模块内容不符、图片异常

修复：
  按 sub 字段重新归属 cat：
    图形推理 → graph
    逻辑判断 / 定义判断 / 类比推理 → judge
    逻辑填空 / 片段阅读 / 语句表达 → verbal
    数学运算 → quantity
    增长 / 比重 / 平均数 / 倍数 / 综合 → data
    新思想 / 毛中特 / 马克思主义 / 时事政治 → politics
    法律常识 / 经济常识 / 人文常识 / 科技常识 / 地理国情 → common

用法：
  python scripts/fix_guokao_cat.py --dry-run
  python scripts/fix_guokao_cat.py --apply
"""

import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "data", "zt", "guokao.json")
APPLY = "--apply" in sys.argv

SUB_TO_CAT = {
    "图形推理": "graph",
    "逻辑判断": "judge",
    "定义判断": "judge",
    "类比推理": "judge",
    "逻辑填空": "verbal",
    "片段阅读": "verbal",
    "语句表达": "verbal",
    "数学运算": "quantity",
    "增长": "data",
    "比重": "data",
    "平均数": "data",
    "倍数": "data",
    "综合": "data",
    "新思想": "politics",
    "毛中特": "politics",
    "马克思主义": "politics",
    "时事政治": "politics",
    "法律常识": "common",
    "经济常识": "common",
    "人文常识": "common",
    "科技常识": "common",
    "地理国情": "common",
}


def main():
    data = json.load(open(P, encoding="utf-8"))
    print("=" * 66)
    print("  修正 guokao 的 cat 分类")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    changed = 0
    unknown = []
    moved = {}

    for q in data:
        sub = q.get("sub") or ""
        want = SUB_TO_CAT.get(sub)
        if not want:
            if sub:
                unknown.append(sub)
            continue
        old = q.get("cat")
        if old != want:
            q["cat"] = want
            changed += 1
            moved[(old, want)] = moved.get((old, want), 0) + 1

    print(f"  修正题数: {changed} / {len(data)}")
    print()
    if moved:
        print("=== 分类迁移 ===")
        for (o, w), n in sorted(moved.items(), key=lambda x: -x[1]):
            print(f"  {o} → {w} : {n} 题")
        print()
    if unknown:
        print("=== 未映射的题型（保持原样）===")
        for u in sorted(set(unknown)):
            print(f"  {u}")

    # 修正后分布
    from collections import Counter
    print("=== 修正后分类分布 ===")
    for c, n in Counter(q.get("cat") for q in data).items():
        print(f"  {c:10s} {n}")

    # 检查每套卷的 modules 声明是否与实际相符
    print()
    papers_path = os.path.join(ROOT, "site", "data", "zt-papers.json")
    if os.path.exists(papers_path):
        papers = json.load(open(papers_path, encoding="utf-8"))["papers"]
        byid = {str(q["id"]): q for q in data}
        bad = []
        for pi, p in enumerate(papers):
            if p.get("kind") != "guokao":
                continue
            actual = Counter()
            for qid in p.get("qids", []):
                q = byid.get(str(qid))
                if q:
                    actual[q.get("cat")] += 1
            expected = {m["cat"]: m["count"] for m in p.get("modules", [])}
            diffs = []
            for c in set(list(actual.keys()) + list(expected.keys())):
                if actual.get(c, 0) != expected.get(c, 0):
                    diffs.append(f"{c}: 声明{expected.get(c,0)} 实际{actual.get(c,0)}")
            if diffs:
                bad.append((pi, p.get("paper", "")[:32], diffs))
        if bad:
            print(f"=== 仍有模块不符的套卷: {len(bad)} ===")
            for pi, t, d in bad[:6]:
                print(f"  [{pi}] {t}")
                for x in d[:3]:
                    print(f"      {x}")
        else:
            print("=== 所有国考卷模块划分均与数据相符 ✓ ===")

    if APPLY and changed:
        bak = P + ".bak"
        if not os.path.exists(bak):
            import shutil
            shutil.copy(P, bak)
            print(f"\n  已备份 {os.path.basename(bak)}")
        json.dump(data, open(P, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"  已写入 {P}")
    elif not APPLY:
        print("\n  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

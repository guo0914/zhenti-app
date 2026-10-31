"""分析现有套卷的完整性：每套卷覆盖哪些模块、题号是否连续"""
import json
import os
import sys
import io
import re
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

# 收集所有题，按 paper 分组
papers = defaultdict(list)
for f in os.listdir(ZT):
    if not f.endswith(".json"):
        continue
    cat = f[:-5]
    d = json.load(open(os.path.join(ZT, f), encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])
    for q in qs:
        p = str(q.get("paper") or "")
        if p:
            papers[p].append(dict(q, _cat=cat))

print("=" * 72)
print(f"套卷完整性分析（共 {len(papers)} 套）")
print("=" * 72)

# 行测标准模块顺序
MODULES = ["常识判断", "言语理解与表达", "数量关系", "判断推理", "资料分析"]
CAT_TO_MODULE = {
    "common": "常识判断", "verbal": "言语理解与表达", "quantity": "数量关系",
    "judge": "判断推理", "graph": "图形推理", "data": "资料分析",
    "politics": "政治理论",
}

complete = []
partial = []
for p, qs in papers.items():
    cats = defaultdict(int)
    for q in qs:
        cats[q["_cat"]] += 1
    mods = {CAT_TO_MODULE.get(c, c): n for c, n in cats.items()}
    # 题号连续性
    nos = []
    for q in qs:
        try:
            nos.append(int(q.get("no")))
        except (ValueError, TypeError):
            pass
    nos = sorted(set(nos))
    gaps = 0
    if len(nos) > 1:
        gaps = (nos[-1] - nos[0] + 1) - len(nos)

    n_mod = len(mods)
    total = len(qs)
    if total >= 80 and n_mod >= 4:
        complete.append((p, total, mods, gaps))
    elif total >= 60:
        partial.append((p, total, mods, gaps))

complete.sort(key=lambda x: -x[1])
print(f"\n★ 较完整套卷（题数>=80 且 覆盖>=4模块）: {len(complete)} 套\n")
for p, total, mods, gaps in complete:
    modstr = " ".join(f"{m[:2]}{n}" for m, n in sorted(mods.items(), key=lambda x: -x[1]))
    gapstr = f"缺号{gaps}" if gaps else "号连续"
    print(f"  {total:>3}题 [{gapstr}] {p[:52]}")
    print(f"        {modstr}")

print(f"\n△ 中等套卷（60-80题）: {len(partial)} 套")
for p, total, mods, gaps in partial[:10]:
    print(f"  {total:>3}题  {p[:60]}")

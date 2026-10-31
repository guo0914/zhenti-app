"""诊断国考地市卷 / 行政执法卷的完整性缺口

输出：每卷的题数、模块配比、题号范围与缺口，判断缺哪些题。
"""
import json
import os
import sys
import io
import re
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

CAT_NAME = {
    "politics": "政治理论", "common": "常识判断", "verbal": "言语理解与表达",
    "quantity": "数量关系", "judge": "判断推理", "graph": "图形推理",
    "data": "资料分析",
}
# 国考标准模块顺序与题量区间
STD_ORDER = ["政治理论", "常识判断", "言语理解与表达", "数量关系",
             "判断推理", "图形推理", "资料分析"]

papers = defaultdict(lambda: {"n": 0, "cats": Counter(), "nos": []})

for f in sorted(os.listdir(ZT)):
    if not f.endswith(".json"):
        continue
    cat = f[:-5]
    if cat.startswith("zt-"):
        continue
    d = json.load(open(os.path.join(ZT, f), encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])
    for q in qs:
        p = str(q.get("paper") or "")
        if not p:
            continue
        papers[p]["n"] += 1
        papers[p]["cats"][cat] += 1
        try:
            papers[p]["nos"].append(int(q.get("no")))
        except (ValueError, TypeError):
            pass

# 只看国考卷
targets = [p for p in papers if "国家公务员" in p or "国考" in p]
targets.sort()

print("=" * 76)
print("国考行测各卷完整性诊断")
print("=" * 76)

for p in targets:
    e = papers[p]
    nos = sorted(set(e["nos"]))
    if not nos:
        continue
    lo, hi = nos[0], nos[-1]
    span = hi - lo + 1
    missing_nos = [n for n in range(lo, hi + 1) if n not in set(nos)]
    mods = {CAT_NAME.get(c, c): n for c, n in e["cats"].items()}
    has_mods = set(mods.keys())
    lack_mods = [m for m in STD_ORDER if m not in has_mods]

    print(f"\n【{p}】")
    print(f"  题数 {e['n']}  题号 {lo}-{hi}（跨度{span}）  缺号 {len(missing_nos)}")
    print(f"  模块 {len(mods)}: " + " ".join(
        f"{m}{mods.get(m, 0)}" for m in STD_ORDER if m in mods))
    if lack_mods:
        print(f"  缺模块: {', '.join(lack_mods)}")
    if missing_nos:
        # 压缩显示连续区间
        ranges = []
        start = prev = missing_nos[0]
        for n in missing_nos[1:]:
            if n == prev + 1:
                prev = n
            else:
                ranges.append((start, prev))
                start = prev = n
        ranges.append((start, prev))
        rtxt = ",".join(f"{a}-{b}" if a != b else str(a) for a, b in ranges)
        print(f"  缺题号: {rtxt[:150]}")

print("\n" + "=" * 76)
print("汇总")
print("=" * 76)
for kw in ("地市级", "行政执法"):
    sel = [p for p in targets if kw in p]
    print(f"\n{kw}: {len(sel)} 套")
    for p in sel:
        e = papers[p]
        m = re.search(r"(20\d{2})", p)
        print(f"  {m.group(1) if m else '?'}  {e['n']:>3} 题  {len(e['cats'])} 模块  {p[:60]}")

"""分析题目的真实卷面顺序：id 是否单调递增？按模块分组后如何排序？"""
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

PAPER = "2023年国家公务员录用考试《行测》题（副省级网友回忆版）"

qs = []
for f in sorted(os.listdir(ZT)):
    if not f.endswith(".json") or f.startswith("zt-"):
        continue
    cat = f[:-5]
    d = json.load(open(os.path.join(ZT, f), encoding="utf-8"))
    arr = d if isinstance(d, list) else d.get("questions", [])
    for q in arr:
        if q.get("paper") == PAPER:
            qs.append(dict(q, _cat=cat))

print(f"卷: {PAPER}  共 {len(qs)} 题\n")

# 按模块分组，看每组的 id 是否连续/单调
from collections import defaultdict
groups = defaultdict(list)
for q in qs:
    groups[q["_cat"]].append(q)

ORDER = ["politics", "common", "verbal", "quantity", "judge", "graph", "data"]
NAME = {"politics": "政治", "common": "常识", "verbal": "言语", "quantity": "数量",
        "judge": "判断", "graph": "图形", "data": "资料"}

print("各模块 id 区间与单调性:")
for cat in ORDER:
    g = groups.get(cat)
    if not g:
        continue
    ids = [int(q["id"]) for q in g]
    mono = all(ids[i] <= ids[i + 1] for i in range(len(ids) - 1))
    print(f"  {NAME[cat]:<4} {len(g):>3}题  id {min(ids)}-{max(ids)}  "
          f"单调递增={mono}")

# 全局按 id 排序，看模块是否成块聚集
print("\n按 id 升序排列后的模块序列（前 40 个）:")
srt = sorted(qs, key=lambda q: int(q["id"]))
seq = [NAME.get(q["_cat"], q["_cat"]) for q in srt[:40]]
print("  " + " ".join(seq))

# 检查模块是否成连续块
print("\n模块成块检测:")
blocks = []
cur = None
for q in srt:
    c = q["_cat"]
    if c != cur:
        blocks.append([c, 0])
        cur = c
    blocks[-1][1] += 1
print(f"  块数: {len(blocks)}")
for c, n in blocks[:12]:
    print(f"    {NAME.get(c, c)} {n}")

# 每题的 sub（题型）在模块内是否也有顺序
print("\n言语模块的 sub 顺序（按 id）:")
vg = sorted(groups.get("verbal", []), key=lambda q: int(q["id"]))
from collections import Counter
print("  " + " | ".join(str(q.get("sub"))[:6] for q in vg[:24]))

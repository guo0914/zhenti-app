"""检查 no 字段的真实含义：为何 135 题却只有 1-40 的题号"""
import json
import os
import sys
import io
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

PAPER = "2023年国家公务员录用考试《行测》题（副省级网友回忆版）"

qs = []
for f in sorted(os.listdir(ZT)):
    if not f.endswith(".json") or f.startswith("zt-"):
        continue
    d = json.load(open(os.path.join(ZT, f), encoding="utf-8"))
    arr = d if isinstance(d, list) else d.get("questions", [])
    for q in arr:
        if q.get("paper") == PAPER:
            qs.append(dict(q, _cat=f[:-5]))

print(f"卷: {PAPER}")
print(f"题数: {len(qs)}\n")

# no 分布
nos = Counter(str(q.get("no")) for q in qs)
print("no 字段分布（前 20）:")
for k, v in list(nos.most_common(20)):
    print(f"  no={k!r}: {v} 题")

print(f"\n不同的 no 值: {len(nos)} 个")

# 看前 8 题的所有字段
print("\n前 8 题的字段:")
for q in qs[:8]:
    print(f"  cat={q['_cat']:<10} no={str(q.get('no')):<6} sub={str(q.get('sub'))[:12]:<14} "
          f"id={q.get('id')}  stem={str(q.get('stem'))[:36]}")

# 检查是否所有题都有唯一 id
ids = [q["id"] for q in qs]
print(f"\nid 唯一性: {len(set(ids))}/{len(ids)}")

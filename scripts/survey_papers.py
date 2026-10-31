"""统计现有题库中「按套卷」的组织情况

检查 site/data/zt/*.json 里 paper 字段的分布，
判断现有数据是否已经能组成完整套卷。
"""
import json
import os
import sys
import io
import re
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

if not os.path.isdir(ZT):
    print(f"目录不存在: {ZT}")
    sys.exit(1)

files = [f for f in os.listdir(ZT) if f.endswith(".json")]
print("=" * 70)
print("现有题库套卷统计")
print("=" * 70)

all_papers = Counter()
cat_papers = defaultdict(Counter)
total_q = 0

for f in sorted(files):
    path = os.path.join(ZT, f)
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"  {f}: 读取失败 {e}")
        continue
    qs = d if isinstance(d, list) else d.get("questions", [])
    if not qs:
        continue
    cat = f[:-5]
    total_q += len(qs)
    papers = Counter()
    for q in qs:
        p = str(q.get("paper") or q.get("region") or "(无)")
        papers[p] += 1
        all_papers[p] += 1
    cat_papers[cat] = papers
    print(f"\n{cat}: {len(qs)} 题, {len(papers)} 套")

print("\n" + "=" * 70)
print(f"总计: {total_q} 题, {len(all_papers)} 个不同的卷名")
print("=" * 70)

# 找出题数>=80 的（接近完整卷）
big = [(p, n) for p, n in all_papers.items() if n >= 80]
big.sort(key=lambda x: -x[1])
print(f"\n题数 >= 80 的卷（接近完整套卷）: {len(big)} 套")
for p, n in big[:25]:
    print(f"  {n:>4} 题  {p[:60]}")

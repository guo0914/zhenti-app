"""统计现有套卷的年份/地区分布，以及完整度"""
import json
import os
import sys
import io
import re
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

# 按 paper 聚合
papers = defaultdict(lambda: {"n": 0, "cats": Counter(), "nos": [], "year": None, "region": None})

for f in os.listdir(ZT):
    if not f.endswith(".json"):
        continue
    cat = f[:-5]
    d = json.load(open(os.path.join(ZT, f), encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])
    for q in qs:
        p = str(q.get("paper") or "")
        if not p:
            continue
        e = papers[p]
        e["n"] += 1
        e["cats"][cat] += 1
        try:
            e["nos"].append(int(q.get("no")))
        except (ValueError, TypeError):
            pass
        if not e["year"]:
            e["year"] = str(q.get("year") or "")
        if not e["region"]:
            e["region"] = str(q.get("region") or "")

print("=" * 74)
print(f"套卷清单（共 {len(papers)} 套）")
print("=" * 74)

# 按年份分组
by_year = defaultdict(list)
for p, e in papers.items():
    y = e["year"] or "?"
    by_year[y].append((p, e))

for y in sorted(by_year, reverse=True):
    items = sorted(by_year[y], key=lambda x: -x[1]["n"])
    print(f"\n【{y} 年】{len(items)} 套")
    for p, e in items:
        nos = sorted(set(e["nos"]))
        gaps = (nos[-1] - nos[0] + 1) - len(nos) if len(nos) > 1 else 0
        mods = len(e["cats"])
        flag = "★" if e["n"] >= 80 and mods >= 4 else ("△" if e["n"] >= 60 else "·")
        short = re.sub(r"年.*?考试", "考", p)[:56]
        print(f"  {flag} {e['n']:>3}题 {mods}模块 {'缺'+str(gaps) if gaps else '连续'}  {short}")

print("\n" + "=" * 74)
tot = sum(e["n"] for e in papers.values())
star = sum(1 for e in papers.values() if e["n"] >= 80 and len(e["cats"]) >= 4)
print(f"合计 {tot} 题 / {len(papers)} 套")
print(f"其中 ★ 较完整（>=80题 且 >=4模块）: {star} 套")

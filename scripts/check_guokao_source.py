"""统计源仓库中所有国考卷的实际题量，与现有数据对比"""
import sys
import io
import re
import json
import os
import time
import urllib.parse
from urllib.request import Request, urlopen

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

H = {"User-Agent": "Mozilla/5.0"}
MODS = ["01-政治理论", "02-常识判断", "03-言语理解与表达",
        "04-数量关系", "05-判断推理", "06-资料分析"]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

# 现有数据里国考各卷的题数
local = {}
for f in os.listdir(ZT):
    if not f.endswith(".json") or f.startswith("zt-"):
        continue
    d = json.load(open(os.path.join(ZT, f), encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])
    for q in qs:
        p = str(q.get("paper") or "")
        if "国家公务员" in p:
            local[p] = local.get(p, 0) + 1

# 需要检查的卷（地市级 + 行政执法 + 副省级对照）
papers = []
for year in (2023, 2024, 2025, 2026):
    for sub in ("地市级", "行政执法卷"):
        papers.append(f"{year}年国家公务员录用考试《行测》题（{sub}网友回忆版）")


def fetch_count(paper):
    """统计该卷在源仓库的总题数。"""
    total = 0
    mods_hit = 0
    for m in MODS:
        u = ("https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"
             + urllib.parse.quote(m + "/" + paper + ".md"))
        for attempt in range(2):
            try:
                d = urlopen(Request(u, headers=H), timeout=30).read().decode("utf-8", "replace")
                cnt = len(re.findall(r"qid\s+\d+", d))
                if cnt:
                    total += cnt
                    mods_hit += 1
                break
            except Exception:
                if attempt == 1:
                    pass
                time.sleep(1)
    return total, mods_hit


print("=" * 74)
print("国考地市级 / 行政执法卷：源仓库 vs 现有数据")
print("=" * 74)
print(f"{'卷名':<44} {'源仓库':>8} {'现有':>8} {'差':>8}")
print("-" * 74)

results = []
for p in papers:
    remote, mods = fetch_count(p)
    now = local.get(p, 0)
    diff = remote - now
    results.append((p, remote, now, diff, mods))
    short = p.replace("年国家公务员录用考试《行测》题（", " ").replace("网友回忆版）", "")
    print(f"{short:<44} {remote:>8} {now:>8} {diff:>+8}")

print("\n" + "=" * 74)
print("汇总")
print("=" * 74)
tot_r = sum(x[1] for x in results)
tot_l = sum(x[2] for x in results)
print(f"源仓库合计: {tot_r} 题")
print(f"现有合计:   {tot_l} 题")
print(f"可补:       {tot_r - tot_l} 题")

json.dump([{"paper": x[0], "remote": x[1], "local": x[2], "diff": x[3], "mods": x[4]}
           for x in results],
          open(os.path.join(ROOT, "..", "law_ocr", "guokao_gap.json"), "w",
               encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n缺口明细已写入 ../law_ocr/guokao_gap.json")

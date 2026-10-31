"""深挖：源仓库的 Markdown 里有没有原卷题号？

仓库格式：### 第 1 题　<sub>qid 19526404 · 语句表达</sub>
其中「第 1 题」就是原卷题号！这对还原卷面顺序至关重要。
"""
import sys
import io
import re
import urllib.parse
import time
from urllib.request import Request, urlopen

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

H = {"User-Agent": "Mozilla/5.0"}
paper = "2023年国家公务员录用考试《行测》题（行政执法卷网友回忆版）"

print("=" * 70)
print(f"检查源仓库题号结构：{paper[:40]}")
print("=" * 70)

for m in ["02-常识判断", "05-判断推理"]:
    u = ("https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"
         + urllib.parse.quote(m + "/" + paper + ".md"))
    for attempt in range(3):
        try:
            d = urlopen(Request(u, headers=H), timeout=30).read().decode("utf-8", "replace")
            # 提取「### 第 N 题　<sub>qid X · 类型</sub>」
            heads = re.findall(r"###\s*第\s*(\d+)\s*题\s*<sub>\s*qid\s*(\d+)\s*·\s*([^<]*)</sub>", d)
            print(f"\n{m}: 提取到 {len(heads)} 个题头")
            for h in heads[:10]:
                print(f"  第{h[0]}题  qid={h[1]}  {h[2]}")
            if heads:
                print(f"  题号范围: {heads[0][0]} ~ {heads[-1][0]}")
            break
        except Exception as e:
            if attempt == 2:
                print(f"\n{m}: 失败 {str(e)[:50]}")
            time.sleep(2)

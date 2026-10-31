"""定位所有超长选项，分析污染形态"""
import json
import sys
import io
import os
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "..", "law_ocr")

SUBJECTS = [("xf", "刑法"), ("mf", "民法"), ("msf", "民诉法"), ("xsf", "刑诉法"),
            ("xzf", "行政法"), ("sxz", "商经知"), ("sgf", "三国法"), ("lilun", "理论法")]

for code, name in SUBJECTS:
    path = os.path.join(OCR, f"law_{code}.json")
    if not os.path.exists(path):
        continue
    d = json.load(open(path, encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])

    long_opts = []
    for q in qs:
        for i, v in enumerate(q.get("options") or []):
            vs = str(v)
            if len(vs) > 250:
                long_opts.append((q["id"], q.get("page"), "ABCD"[i], len(vs), vs))

    if long_opts:
        print(f"\n{'='*66}")
        print(f"{name}: {len(long_opts)} 个超长选项")
        for qid, page, letter, n, vs in long_opts[:4]:
            print(f"  {qid} 第{page}页 {letter}选项 ({n}字)")
            print(f"    开头: {vs[:100]}")
            print(f"    中间: ...{vs[100:200]}...")
            print(f"    结尾: {vs[-80:]}")

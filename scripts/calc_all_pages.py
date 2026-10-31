import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "..", "law_ocr")

subs = [("xf", "刑法"), ("mf", "民法"), ("msf", "民诉法"), ("xsf", "刑诉法"),
        ("xzf", "行政法"), ("sxz", "商经知"), ("sgf", "三国法"), ("lilun", "理论法")]

total_pages = 0
for code, name in subs:
    path = os.path.join(OCR, f"law_{code}.json")
    if not os.path.exists(path):
        print(f"{name}: 文件不存在 {path}")
        continue
    d = json.load(open(path, encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])
    ps = set(q["page"] for q in qs if q.get("page"))
    total_pages += len(ps)
    print(f"{name}: {len(qs)} 题, 涉及 {len(ps)} 个不同页")

print(f"\n全部题页合计: {total_pages} 页")
print(f"按 110KB/张估算: {total_pages * 110 / 1024:.0f} MB")
print(f"按 80KB/张（更激进压缩）: {total_pages * 80 / 1024:.0f} MB")

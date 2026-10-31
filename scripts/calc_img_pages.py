"""统计各科需要生成原书图片的页码（有 flags 的题）"""
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "..", "law_ocr")

SUBJECTS = [
    ("xf", "刑法", "xingfa"), ("mf", "民法", "minfa_all"),
    ("msf", "民诉法", "minsu"), ("xsf", "刑诉法", "xingsu"),
    ("xzf", "行政法", "xingzheng"), ("sxz", "商经知", "shangjing"),
    ("sgf", "三国法", "sanguo"), ("lilun", "理论法", "lilun"),
]

total_pages = 0
for code, name, ocr_name in SUBJECTS:
    path = os.path.join(OCR, f"law_{code}.json")
    if not os.path.exists(path):
        continue
    d = json.load(open(path, encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])

    # 有 flags 的题 + 选项可能被截断的题（内容很短）都算需要图片
    need = set()
    for q in qs:
        flags = q.get("flags") or []
        if flags:
            if q.get("page"):
                need.add(q["page"])
        # 选项过短（可能 OCR 截断）也加进来
        elif any(len(str(v)) < 8 for v in (q.get("options") or [])):
            if q.get("page"):
                need.add(q["page"])

    total_pages += len(need)
    print(f"{name}: {len(qs)} 题, 需要图片 {len(need)} 页")
    if 0 < len(need) <= 40:
        print(f"   页码: {','.join(str(p) for p in sorted(need))}")

print(f"\n合计需要生成: {total_pages} 页")
print(f"预计体积: {total_pages * 190 / 1024:.1f} MB")

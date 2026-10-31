"""验证图片与题库页码的对应关系"""
import json
import os
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "..", "law_ocr")
IMG = os.path.join(ROOT, "site", "data", "zt", "law_img")

SUBJECTS = [
    ("xf", "刑法"), ("mf", "民法"), ("msf", "民诉法"), ("xsf", "刑诉法"),
    ("xzf", "行政法"), ("sxz", "商经知"), ("sgf", "三国法"), ("lilun", "理论法"),
]

print("=" * 66)
print("图片与题库页码对应验证")
print("=" * 66)

total_flagged = total_with_img = 0
missing_samples = []

for code, name in SUBJECTS:
    path = os.path.join(OCR, f"law_{code}.json")
    if not os.path.exists(path):
        continue
    d = json.load(open(path, encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])

    flagged = [q for q in qs if q.get("flags")]
    with_img = 0
    for q in flagged:
        page = q.get("page")
        if not page:
            continue
        f = os.path.join(IMG, f"{code}-{page:04d}.jpg")
        if os.path.exists(f):
            with_img += 1
        elif len(missing_samples) < 8:
            missing_samples.append(f"{q['id']} 第{page}页 缺 {os.path.basename(f)}")

    total_flagged += len(flagged)
    total_with_img += with_img
    rate = with_img / max(len(flagged), 1) * 100
    mark = "✓" if with_img == len(flagged) else "✗"
    print(f"  {mark} {name:<6} 有疑点 {len(flagged):>3} 题, 有图片 {with_img:>3} ({rate:.0f}%)")

print(f"\n合计: {total_flagged} 题有疑点, {total_with_img} 题有图片")

if missing_samples:
    print("\n缺失样例:")
    for s in missing_samples:
        print("  " + s)

# 检查图片总数
imgs = [f for f in os.listdir(IMG) if f.endswith(".jpg")]
print(f"\n图片文件总数: {len(imgs)}")
by_subj = {}
for f in imgs:
    c = f.split("-")[0]
    by_subj[c] = by_subj.get(c, 0) + 1
print("分科图片数:", by_subj)

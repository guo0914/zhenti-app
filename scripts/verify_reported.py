"""验证用户截图里报告的具体题目是否已修复

用户截图的问题题：
  图1: 行政法 2024金题-1-3-3 第24页（公务员王某）—— 原书图片未生成
  图2: 行政法 2022金题-1-3-12 第48页（农业农村部许可办法）—— C选项混入"①见本书第60题"
  图3: 民法 2021金题-2-1-18 第203页（黄某遗产继承）—— D选项混入示意图
  图4: 民法 2025金题-2-1-17 第104页（甲公司/洪某）—— A选项混入大段解析
  图5: 民法 2021金题-2-1-2 第28页（潘某红木）—— D选项混入示意图+解析
"""
import json
import os
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "..", "law_ocr")
IMG = os.path.join(ROOT, "site", "data", "zt", "law_img")

# (科目代码, 科目名, 书印页码, 题干关键词, 期望的选项数)
TARGETS = [
    ("xzf", "行政法", 24, "公务员王某因过失犯罪", 4),
    ("xzf", "行政法", 48, "农业农村部行政许可", 4),
    ("mf", "民法", 203, "黄某育有一子一女", 4),
    ("mf", "民法", 104, "甲公司欠乙公司10万元", 4),
    ("mf", "民法", 28, "潘某有一批珍贵红木", 4),
]

POLLUTE = [
    (r"综上", "含「综上」"),
    (r"本题的?正确答案|本题答案为", "含答案标记"),
    (r"[\[［【]?\s*(?:民事|刑事)?法律关系示意图", "含示意图"),
    (r"[\[［【]?\s*(?:有体系|知识体系|思维导图)", "含体系图"),
    (r"[\[［【]?\s*(?:解题思路|分析与思路|题支逐项|题干信息|命题陷阱)", "含解析标记"),
    (r"考点\s*\d+\s*[：:]", "含考点标记"),
    (r"PROJECT\s*\d+", "含 PROJECT"),
    (r"专题[一二三四五六七八九十百零\d]+", "含章节名"),
    (r"见本书第\d+题", "含页内引用"),
    (r"故[A-D]项(?:说法)?(?:正确|错误)", "含逐项分析"),
]

print("=" * 70)
print("用户报告题目验证")
print("=" * 70)

all_ok = True
for code, name, page, keyword, expect_opts in TARGETS:
    path = os.path.join(OCR, f"law_{code}.json")
    d = json.load(open(path, encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])

    # 按页码+关键词匹配
    hit = None
    for q in qs:
        if q.get("page") == page and keyword in str(q.get("stem") or ""):
            hit = q
            break

    if not hit:
        # 放宽：同页码的题
        same_page = [q for q in qs if q.get("page") == page]
        if same_page:
            hit = same_page[0]
            print(f"\n{name} 第{page}页: 关键词未精确匹配，用同页第一题 {hit['id']}")
        else:
            print(f"\n{name} 第{page}页: ✗ 未找到题目")
            all_ok = False
            continue
    else:
        print(f"\n{name} 第{page}页: {hit['id']}")

    opts = hit.get("options") or []
    print(f"  题干: {str(hit.get('stem'))[:60]}")
    print(f"  选项数: {len(opts)} {'✓' if len(opts) == expect_opts else '✗'}")

    # 检查每个选项的污染
    q_ok = len(opts) == expect_opts
    for i, v in enumerate(opts):
        vs = str(v)
        marks = [label for pat, label in POLLUTE if re.search(pat, vs)]
        letter = "ABCD"[i] if i < 4 else "?"
        flag = "✗" if marks else "✓"
        print(f"    {flag} {letter}({len(vs)}字): {vs[:55]}")
        if marks:
            print(f"        污染: {', '.join(marks)}")
            q_ok = False

    # 检查图片
    base = os.path.join(IMG, f"{code}-{page:04d}")
    has_img = os.path.exists(base + ".webp") or os.path.exists(base + ".jpg")
    print(f"  原书图片: {'✓ 存在' if has_img else '✗ 缺失'}")

    if not q_ok:
        all_ok = False

print("\n" + "=" * 70)
print("✅ 全部题目已修复" if all_ok else "❌ 仍有问题")

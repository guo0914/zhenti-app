"""诊断：选项污染（解析混入选项）

用户截图的 3 种形态：
  1. 选项 D 里混入大段解析 + "综上所述，本题的正确答案为B"
  2. 选项 D 里混入 "[民事法律关系示意图]" 等图表文字
  3. 选项 A 里混入上题解析
"""
import json
import sys
import io
import re
import glob
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "..", "law_ocr")

SUBJECTS = [
    ("xf", "刑法"), ("mf", "民法"), ("msf", "民诉法"), ("xsf", "刑诉法"),
    ("xzf", "行政法"), ("sxz", "商经知"), ("sgf", "三国法"), ("lilun", "理论法"),
]

# 污染特征
POLLUTE_PATTERNS = [
    (r"综上", "含「综上」"),
    (r"本题的?正确答案", "含「正确答案」"),
    (r"本题答案为", "含「本题答案为」"),
    (r"\[?民事法律关系示意图\]?", "含示意图"),
    (r"\[?有体系\]?", "含「有体系」"),
    (r"\[?解题思路", "含解析标记"),
    (r"\[?分析与思路", "含解析标记"),
    (r"\[?解析[\]］】]", "含解析标记"),
    (r"考点\s*\d+", "含考点标记"),
    (r"项说法?(正确|错误)", "含逐项分析"),
    (r"故[A-D]项", "含逐项分析"),
    (r"PROJECT\d", "含 PROJECT"),
    (r"[专]题[一二三四五六七八九十]+", "含章节名"),
]


def check_subject(code, name):
    path = os.path.join(OCR, f"law_{code}.json")
    if not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    qs = d if isinstance(d, list) else d.get("questions", [])

    issues = []
    for q in qs:
        opts = q.get("options") or []
        for i, v in enumerate(opts):
            v = str(v)
            for pat, label in POLLUTE_PATTERNS:
                if re.search(pat, v):
                    issues.append({
                        "id": q["id"], "page": q.get("page"),
                        "opt": "ABCD"[i] if i < 4 else "?",
                        "len": len(v),
                        "label": label,
                        "sample": v[:80],
                    })
                    break

    return {"code": code, "name": name, "total": len(qs), "issues": issues}


def main():
    print("=" * 70)
    print("选项污染诊断")
    print("=" * 70)

    grand = 0
    for code, name in SUBJECTS:
        r = check_subject(code, name)
        if not r:
            continue
        n = len(r["issues"])
        grand += n
        rate = n / max(r["total"], 1) * 100
        print(f"\n{name}: {r['total']} 题, 污染 {n} 处 ({rate:.1f}%)")

        # 按标签分组
        by_label = {}
        for it in r["issues"]:
            by_label.setdefault(it["label"], []).append(it)
        for label, items in sorted(by_label.items(), key=lambda x: -len(x[1])):
            print(f"   {len(items):>3}  {label}")
            for it in items[:2]:
                print(f"        {it['id']} {it['opt']}选项({it['len']}字) {it['sample'][:60]}")

    print(f"\n{'='*70}")
    print(f"污染总计: {grand} 处")


if __name__ == "__main__":
    main()

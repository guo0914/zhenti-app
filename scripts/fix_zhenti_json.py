"""修复分类刷题数据（zhenti.json）的横线与选项图片

问题：
  套卷用的 site/data/zt/*.json 已修复，
  但分类刷题用的是 site/data/zhenti.json（3480 题，独立数据源），
  存在同样的缺陷却从未修复：

    填空类题 449 道，仅 1 道含 ____（448 道无法作答）
    选项含裸 <img> HTML 61 道（选项显示成标签文字）

修复：
  1. 逻辑填空 / 语句表达：把中文之间的孤立空格还原成 ____
  2. 选项里的 <img src> 解析成 optionImgs，并从文本中移除
"""

import sys
import io
import os
import re
import json
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "data", "zhenti.json")
APPLY = "--apply" in sys.argv

CJK = "\u4e00-\u9fff"
L = CJK + "，。；：、\u201c\u201d\u2018\u2019！？"
BLANK = re.compile("(?<=[" + L + "])( )(?=[" + L + "])")
IMG = re.compile(r'<img[^>]*?src="([^"]+)"[^>]*?>', re.I)


def norm_img(src):
    name = src.split("/")[-1]
    if "公式图" in src:
        return "公式图/" + name
    if "题目图" in src:
        return "题目图/" + name
    return name


def main():
    data = json.load(open(P, encoding="utf-8"))
    qs = data["questions"]
    print("=" * 70)
    print("  修复分类刷题数据 zhenti.json")
    print("=" * 70)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print(f"  题目: {len(qs)}")
    print()

    n_blank = 0
    n_optimg = 0
    samples = []

    for q in qs:
        sub = q.get("sub") or ""
        stem = q.get("stem") or ""

        # 1. 横线还原
        if sub in ("逻辑填空", "语句表达") and "____" not in stem:
            if "画横线" in stem or "依次填入" in stem or "填入" in stem:
                new = BLANK.sub("____", stem)
                if new != stem:
                    q["stem"] = new
                    n_blank += 1
                    if len(samples) < 4:
                        samples.append(("横线", q.get("id"), sub, new[:50]))

        # 2. 选项图片
        opts = [str(o) for o in (q.get("options") or [])]
        if any("<img" in o.lower() for o in opts):
            arr = [""] * len(opts)
            newopts = []
            for i, o in enumerate(opts):
                m = IMG.search(o)
                if m:
                    rel = norm_img(m.group(1))
                    p = os.path.join(ROOT, "site", "assets", "zt", rel)
                    if os.path.exists(p):
                        arr[i] = "assets/zt/" + rel
                    newopts.append("")
                else:
                    newopts.append(o)
            if any(arr):
                q["optionImgs"] = arr
                q["options"] = newopts
                n_optimg += 1
                if len(samples) < 8:
                    samples.append(("选项图", q.get("id"), q.get("sub"), ""))

    print(f"  横线修复: {n_blank} 题")
    print(f"  选项图片: {n_optimg} 题")
    for s in samples:
        print(f"    [{s[0]}] {s[1]} [{s[2]}] {s[3]}")

    if APPLY:
        bak = P + ".bak"
        if not os.path.exists(bak):
            shutil.copy(P, bak)
        json.dump(data, open(P, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"\n  已写入 zhenti.json")
    else:
        print("\n  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

"""材料清理终版：用「题干长度」判定，取代关键词猜测

核心洞察：
  片段阅读/语句表达的题干有两种形态：
    A. 自带文段（题干 >= 100 字，文段就在题干里）
       → 材料必是错配，删掉
    B. 指代外部材料（题干很短，如「关于悬泉置，文中介绍了哪些信息？」）
       → 材料必需，保留

  用关键词（文中/这段文字/文章）判断会出错：
    「这段文字主要说明的是」是所有片段阅读的通用结尾，
    指的是题干自带的文段，不代表需要外部材料。
    实测因此残留 15+ 题错配材料。

规则：
  · 资料分析类（增长/比重/平均数/倍数/综合）→ 永远保留
  · 图形推理 / 类比推理 / 定义判断 → 一律删除
  · 其他题型：题干 >= 100 字 → 删除；否则保留
  · 例外：题干含「填入文中」「填入文章中」→ 保留（横线在材料里）
"""

import sys
import io
import os
import json
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
APPLY = "--apply" in sys.argv

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]
DATA_SUBS = ("增长", "比重", "平均数", "倍数", "综合")
NOMAT_SUBS = ("图形推理", "类比推理", "定义判断")
# 横线在材料里的明确信号
IN_MATERIAL = ("填入文中", "填入文章中", "填入第", "文中画横线", "文章中画横线")

LONG_STEM = 100


def main():
    print("=" * 70)
    print("  材料清理终版（按题干长度判定）")
    print("=" * 70)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    total = 0
    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        n = 0
        samples = []

        for q in data:
            mat = q.get("material") or ""
            mimg = q.get("materialImgs") or []
            if (not mat and not mimg) or mat.strip() in ("[图]", "[图片]"):
                continue
            sub = q.get("sub") or ""
            stem = q.get("stem") or ""

            if sub in DATA_SUBS:
                continue
            if any(k in stem for k in IN_MATERIAL):
                continue

            drop = False
            if sub in NOMAT_SUBS:
                drop = True
            elif len(stem) >= LONG_STEM:
                drop = True

            if not drop:
                continue

            if len(samples) < 3:
                samples.append((q.get("id"), sub, len(stem), stem[:32]))
            q["material"] = ""
            q.pop("materialImgs", None)
            q.pop("matNo", None)
            n += 1

        if n:
            print(f"  {name:10s} 清理 {n} 题")
            for s in samples:
                print(f"      {s[0]} [{s[1]}] 题干{s[2]}字 | {s[3]}")
            total += n
            if APPLY:
                bak = path + ".matv2bak"
                if not os.path.exists(bak):
                    shutil.copy(path, bak)
                json.dump(data, open(path, "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                print(f"      已写入")

    print()
    print(f"  合计清理 {total} 题")
    if not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

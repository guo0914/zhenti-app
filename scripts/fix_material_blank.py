"""修复材料（material 字段）里的横线丢失

问题：
  部分填空题的横线位于文章材料中（不是题干），例如：
    "身上 着生命的力量"          应为"身上____着生命的力量"
    "种子在此“ ”。"              应为"种子在此“____”。"
  用户看到材料里有个看不出来的空格，不知道怎么填。

根因：
  与题干相同，原始 markdown 里横线是连续 \\xa0，
  被 parse 成空格后压缩成 1 个。

修复：
  对 material 字段做同样的单空格 → ____ 还原，
  只处理题型含「填空」「选词」或题干含「画横线」的题。

用法：
  python scripts/fix_material_blank.py --dry-run
  python scripts/fix_material_blank.py --apply
"""

import sys
import io
import os
import re
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
APPLY = "--apply" in sys.argv

TARGETS = ["verbal.json", "guokao.json", "common.json"]

CJK = "\u4e00-\u9fff"
PUNC = "，。；：、（）\u201c\u201d\u2018\u2019《》！？—·【】…"
BLANK_SPACE = re.compile(
    "(?<=[" + CJK + PUNC + "])( )(?=[" + CJK + PUNC + "]|\\n|\u3000)"
)


def need_fix(q):
    """只处理需要填词的题"""
    sub = q.get("sub") or ""
    stem = q.get("stem") or ""
    return ("填空" in sub or "选词" in sub or "画横线" in stem)


def main():
    print("=" * 66)
    print("  修复材料里的横线")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    total = 0
    for name in TARGETS:
        path = os.path.join(ZT, name)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        changed = 0
        samples = []

        for q in data:
            if not need_fix(q):
                continue
            mat = q.get("material") or ""
            if not mat or "____" in mat:
                continue
            new = BLANK_SPACE.sub("____", mat)
            if new != mat:
                q["material"] = new
                changed += 1
                if len(samples) < 3:
                    for i in range(min(len(mat), len(new))):
                        if mat[i] != new[i]:
                            lo = max(0, i - 14)
                            samples.append((q.get("id"), mat[lo:i + 14], new[lo:i + 14]))
                            break

        print(f"  {name:14s} 修复材料横线 {changed} 题")
        for qid, before, after in samples:
            print(f"      {qid}: ...{before}... → ...{after}...")
        total += changed

        if APPLY and changed:
            bak = path + ".bak3"
            if not os.path.exists(bak):
                import shutil
                shutil.copy(path, bak)
            json.dump(data, open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
            print(f"      已写入 {name}")

    print()
    print(f"  合计修复: {total} 题")
    if not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

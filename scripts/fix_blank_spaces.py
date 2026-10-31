"""把填空题里「被压成单个空格」的横线还原成 ____（支持多分片）

问题：
  逻辑填空等填空题里，题干横线丢失变成 1 个普通空格：
    "形成 的整体风格"      应为  "形成 ____ 的整体风格"
    "拥有顺风耳、千里眼，避免“ ”式"  应为  "避免“____”式"
  用户不知道要在哪里填词。

根因：
  原始 markdown 里横线是连续 \\xa0（8~20 个），
  parse_zhenti.py 把它转成空格后又压缩成 1 个。

修复策略：
  只处理题型含「填空」「选词」的题；
  把 stem 里「孤立的一个空格」还原为 ____，覆盖场景：
    · 中文空格中文     "物种 的"
    · 中文空格标点     "刻不容缓。 ，"
    · 引号空格引号     "避免“ ”式"
    · 标点空格中文     "， 每一个"

用法：
  python scripts/fix_blank_spaces.py --dry-run
  python scripts/fix_blank_spaces.py --apply
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

# 待处理的分片
TARGETS = ["verbal.json", "guokao.json", "common.json", "politics.json", "judge.json"]

CJK = "\u4e00-\u9fff"
PUNC = "，。；：、（）\u201c\u201d\u2018\u2019《》！？—·【】…"
# 单个空格，两侧是中文或中文标点或引号
BLANK_SPACE = re.compile(
    "(?<=[" + CJK + PUNC + "])( )(?=[" + CJK + PUNC + "]|\\n|\u3000)"
)


def is_fill_sub(sub: str) -> bool:
    return bool(sub) and ("填空" in sub or "选词" in sub)


def fix_stem(stem: str) -> str:
    if not stem:
        return stem
    if "\u3000" in stem:
        stem = stem.replace("\u3000\u3000", "____").replace("\u3000", " ")
    parts = stem.split("____")
    fixed = [BLANK_SPACE.sub("____", p) for p in parts]
    return "____".join(fixed)


def main():
    print("=" * 66)
    print("  还原填空题的横线")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    grand_fixed = 0
    grand_total = 0

    for name in TARGETS:
        path = os.path.join(ZT, name)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        fill = [q for q in data if is_fill_sub(q.get("sub") or "")]
        if not fill:
            continue

        changed = 0
        samples = []
        for q in fill:
            stem = q.get("stem") or ""
            if "____" in stem:
                continue
            new = fix_stem(stem)
            if new != stem:
                q["stem"] = new
                changed += 1
                if len(samples) < 3:
                    for i in range(min(len(stem), len(new))):
                        if stem[i] != new[i]:
                            lo = max(0, i - 10)
                            samples.append((q.get("id"),
                                            stem[lo:i + 10],
                                            new[lo:i + 10]))
                            break

        print(f"  {name:16s} 填空题 {len(fill):3d} 题  修复 {changed:3d} 题")
        for qid, before, after in samples:
            print(f"      {qid}: {before} → {after}")

        grand_total += len(fill)
        grand_fixed += changed

        if APPLY and changed:
            bak = path + ".bak"
            if not os.path.exists(bak):
                import shutil
                shutil.copy(path, bak)
            json.dump(data, open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
            print(f"      已写入 {name}")

    print()
    print(f"  合计: {grand_total} 题，修复 {grand_fixed} 题")

    # 复核
    residual = 0
    for name in TARGETS:
        path = os.path.join(ZT, name)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for q in data:
            if is_fill_sub(q.get("sub") or ""):
                s = q.get("stem") or ""
                if BLANK_SPACE.search(s):
                    residual += 1
    print(f"  修复后仍残留孤立空格: {residual} 题")

    if not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

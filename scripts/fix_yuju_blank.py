"""修复语句表达类题目的横线 + 顺带清理多余材料

问题：
  fix_blank_spaces.py 的 is_fill_sub() 只匹配 sub 含「填空」或「选词」，
  而「语句表达」题型同样有填空（"填入画横线部分最恰当的一项"），
  被整体跳过，导致 75 题横线仍是单个空格。

后果：
  · 用户看不到要填哪里
  · 后续材料清理规则（依赖 ____ 判断）也失效，
    这些题仍挂着完全无关的材料（如 5445827 挂 1541 字降雨材料）

修复：
  1. sub 为 逻辑填空/语句表达，且题干含「画横线」或「依次填入」，且无 ____
     → 把中文/中文标点之间的单个空格还原为 ____（排除 （ ） 内的空格）
  2. 还原后，题干自带 ____ 且不引用材料的，清空 material
"""

import sys
import io
import os
import re
import json
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
APPLY = "--apply" in sys.argv

SHARDS = ["verbal", "guokao", "common", "politics"]

CJK = "\u4e00-\u9fff"
# 两侧是中文或中文标点，排除 （ ） 内的空格
L = CJK + "，。；：、\u201c\u201d\u2018\u2019！？"
PAT = re.compile("(?<=[" + L + "])( )(?=[" + L + "])")

KEEP_KW = ("文章", "文中", "这段文字", "给定资料", "根据材料",
           "上述资料", "本文", "上述信息", "以上信息", "上文")


def main():
    print("=" * 70)
    print("  修复语句表达横线 + 清理多余材料")
    print("=" * 70)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    t_blank = 0
    t_mat = 0

    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        n_blank = n_mat = 0
        samples = []

        for q in data:
            sub = q.get("sub") or ""
            stem = q.get("stem") or ""
            if sub not in ("逻辑填空", "语句表达"):
                continue
            if "画横线" not in stem and "依次填入" not in stem:
                continue

            # 1. 还原横线
            if "____" not in stem:
                new = PAT.sub("____", stem)
                if new != stem:
                    q["stem"] = new
                    stem = new
                    n_blank += 1
                    if len(samples) < 5:
                        samples.append((q.get("id"), sub, new[:56]))

            # 2. 清空多余材料
            mat = q.get("material") or ""
            if mat and not q.get("materialImgs") \
                    and mat.strip() not in ("[图]", "[图片]") \
                    and "____" in stem \
                    and not any(k in stem for k in KEEP_KW):
                q["material"] = ""
                q.pop("matNo", None)
                n_mat += 1

        if n_blank or n_mat:
            print(f"  {name:10s} 横线 {n_blank}  材料 {n_mat}")
            for s in samples:
                print(f"      {s[0]} [{s[1]}] {s[2]}")
            t_blank += n_blank
            t_mat += n_mat
            if APPLY:
                bak = path + ".blankbak"
                if not os.path.exists(bak):
                    shutil.copy(path, bak)
                json.dump(data, open(path, "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                print(f"      已写入")

    print()
    print(f"  合计：横线修复 {t_blank} 题，材料清理 {t_mat} 题")
    if not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

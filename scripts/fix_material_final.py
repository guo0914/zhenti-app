"""最终版：按内容匹配度清除错误材料（含全部保留规则）

保留材料的条件（任一满足）：
  1. 有 materialImgs（材料是图片）
  2. material 就是 "[图]" 占位
  3. 题型属于图表类：增长/比重/平均数/倍数/综合
  4. 题干含指向材料的关键词：文章/文中/这段文字/画横线/给定资料/上述资料/本文/上述信息
  5. 材料与题干 2-gram 重合度 >= 6%
  6. 分片是 data（资料分析必定需要材料）

其余一律清空。
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

SHARDS = ["verbal", "guokao", "common", "politics", "judge", "data", "quantity"]

THRESHOLD = 0.10
MIN_STEM_LEN = 8

# 注意：不要包含「画横线」——那是所有填空题的通用结语，
# 并不表示题干真的指向材料（实测会误保留错配材料）
KEEP_KEYWORDS = ("文章", "文中", "这段文字", "给定资料", "根据材料",
                 "上述资料", "本文", "上述信息", "以上信息", "上文")
KEEP_SUBS = ("增长", "比重", "平均数", "倍数", "综合")


def grams(text, n=2):
    text = re.sub(r"[\s\u00a0\u3000_]+", "", text)
    if len(text) < n:
        return set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def ratio(a, b):
    ga = grams(a)
    if not ga:
        return 1.0
    gb = grams(b)
    return len(ga & gb) / len(ga) if gb else 0.0


def should_keep(q, shard_name):
    mat = q.get("material") or ""
    stem = q.get("stem") or ""
    sub = q.get("sub") or ""

    if q.get("materialImgs"):
        return True
    if mat.strip() in ("[图]", "[图片]"):
        return True
    if shard_name == "data":
        return True
    if sub in KEEP_SUBS:
        return True
    if any(k in stem for k in KEEP_KEYWORDS):
        return True

    # 题干是「填入/依次填入…画横线」这类指代型，
    # 说明横线位于材料内部，必须保留材料
    SHORT_POINTERS = ("填入画横线", "依次填入", "填入文中", "填入第", "画横线处")
    if len(stem) <= 40 and any(p in stem for p in SHORT_POINTERS):
        return True

    if len(stem) >= MIN_STEM_LEN and ratio(stem, mat) >= THRESHOLD:
        return True
    if len(stem) < MIN_STEM_LEN:
        return True       # 题干太短无法判断，保守保留

    return False


def main():
    print("=" * 66)
    print("  清除错配材料（最终版）")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    total = 0
    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        changed = 0
        samples = []

        for q in data:
            mat = q.get("material") or ""
            if not mat:
                continue
            if should_keep(q, name):
                continue
            if len(samples) < 4:
                samples.append((q.get("id"), q.get("sub"),
                                ratio(q.get("stem") or "", mat),
                                (q.get("stem") or "")[:32], mat[:24]))
            q["material"] = ""
            q.pop("materialImgs", None)
            q.pop("matNo", None)
            changed += 1

        if changed:
            print(f"  {name:12s} 清除 {changed} 题")
            for s in samples:
                print(f"      {s[0]} [{s[1]}] {s[2]:.1%}")
                print(f"          题干: {s[3]}")
                print(f"          材料: {s[4]}…")
            total += changed
            if APPLY:
                bak = path + ".finalbak"
                if not os.path.exists(bak):
                    import shutil
                    shutil.copy(path, bak)
                json.dump(data, open(path, "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                print(f"      已写入 {name}")

    print()
    print(f"  合计清除: {total} 题")

    # 复核
    print()
    print("=== 复核：仍带材料且低匹配的题 ===")
    leftovers = 0
    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for q in data:
            mat = q.get("material") or ""
            stem = q.get("stem") or ""
            if not mat:
                continue
            if not should_keep(q, name):
                leftovers += 1
                print(f"  {name} {q.get('id')} [{q.get('sub')}] "
                      f"{ratio(stem, mat):.1%} | {stem[:28]}")
    print(f"  残留: {leftovers} 题")

    if not APPLY:
        print("\n  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

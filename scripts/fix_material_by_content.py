"""按内容匹配度修复材料错误关联

问题：
  部分题目的 material 与题干无关（材料串了）。
  不能按题型一刀切——同一题型里有的题需要材料，有的不需要。

判定方法：
  材料应当与题干存在语义关联。
  实测发现两类：
    · 正确：材料「为倡导团结合作精神，某单位举办了双打比赛…」
      题干「若宋和韩组队网球双打…」→ 关键词「双打」命中
    · 错误：材料「悬泉置遗址位于敦煌…」
      题干「党员干部生活作风的蜕变…」→ 无关键词命中

  用字符 2-gram 重合度判断：
    材料与题干共享的 2-gram 数量 / 题干 2-gram 总数
    低于阈值（如 0.08）且题干较长时，判为不匹配。

用法：
  python scripts/fix_material_by_content.py --dry-run
  python scripts/fix_material_by_content.py --apply
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

# 不匹配阈值：题干 2-gram 中与材料重合的比例
THRESHOLD = 0.06
# 题干太短时不做判断（材料题题干常常很短，如「以上哪项」）
MIN_STEM_LEN = 12


def grams(text, n=2):
    text = re.sub(r"[\s\u00a0\u3000_]+", "", text)
    if len(text) < n:
        return set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def match_ratio(stem, mat):
    gs = grams(stem)
    if not gs:
        return 1.0
    gm = grams(mat)
    if not gm:
        return 0.0
    hit = len(gs & gm)
    return hit / len(gs)


def main():
    print("=" * 66)
    print("  按内容匹配度修复材料关联")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print(f"  阈值: 题干 2-gram 与材料重合 < {THRESHOLD:.2%} 判为不匹配")
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
            stem = q.get("stem") or ""
            if not mat or len(stem) < MIN_STEM_LEN:
                continue
            # 材料是图片占位（资料分析图表题）或含 materialImgs 时保留
            if mat.strip() in ("[图]", "[图片]") or q.get("materialImgs"):
                continue
            # 纯图表类题型（增长/比重/平均数/倍数/综合）也保留
            if (q.get("sub") or "") in ("增长", "比重", "平均数", "倍数", "综合"):
                continue
            # 题干明确指向材料（文章/文中/画横线/资料）时保留
            KEY = ("文章", "文中", "这段文字", "画横线", "给定资料", "根据材料", "上述资料", "本文")
            if any(k in stem for k in KEY):
                continue
            ratio = match_ratio(stem, mat)
            if ratio >= THRESHOLD:
                continue
            # 不匹配 → 清空材料
            if len(samples) < 6:
                samples.append((q.get("id"), q.get("sub"), ratio,
                                stem[:34], mat[:26]))
            q["material"] = ""
            q.pop("materialImgs", None)
            q.pop("matNo", None)
            changed += 1

        if changed:
            print(f"  {name:12s} 清除不匹配材料 {changed} 题")
            for s in samples:
                print(f"      {s[0]} [{s[1]}] 重合度 {s[2]:.1%}")
                print(f"          题干: {s[3]}")
                print(f"          材料: {s[4]}…")
            total += changed
            if APPLY:
                bak = path + ".contbak"
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
    print("=== 复核：仍带材料的题，抽查匹配度 ===")
    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        withmat = [q for q in data if q.get("material")]
        if not withmat:
            continue
        low = [q for q in withmat
               if len(q.get("stem") or "") >= MIN_STEM_LEN
               and match_ratio(q.get("stem") or "", q.get("material") or "") < THRESHOLD]
        print(f"  {name:12s} 仍带材料 {len(withmat)} 题，低匹配 {len(low)} 题")

    if not APPLY:
        print("\n  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

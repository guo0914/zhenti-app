"""修复材料错误关联

问题：
  verbal.json 里有 25 道题的 material 全被填成同一份「悬泉置遗址」材料，
  但其中多数题干与该材料无关：
    · 19526373 逻辑填空「党员干部生活作风的蜕变…」→ 不该有悬泉置材料
    · 19526373 之外的逻辑填空题也都被污染

根因：
  解析时按 matNo（材料编号）关联材料，
  但不同题型（逻辑填空/片段阅读/语句表达）都编号 matNo=2，
  互相串了。

判定规则：
  只有「材料题」才应带材料：
    · sub 为 片段阅读 / 语句表达 / 综合 / 增长 / 比重 / 平均数 / 倍数
    · 或题干含「文中」「文章」「这段文字」「画横线」「材料」「资料」
  其他题（逻辑填空、类比推理、定义判断等）的独立成题，
  不该带大段材料。

处理：
  对不该带材料的题，清空 material / materialImgs / matNo。

用法：
  python scripts/fix_material_misassign.py --dry-run
  python scripts/fix_material_misassign.py --apply
"""

import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
APPLY = "--apply" in sys.argv

SHARDS = ["verbal", "guokao", "common", "politics", "judge", "data", "quantity"]

# 确实需要材料的题型
MAT_SUBS = ["片段阅读", "语句表达", "综合", "增长", "比重", "平均数", "倍数"]
# 题干出现这些词，说明是材料题
MAT_KEYWORDS = ["文中", "文章", "这段文字", "画横线", "给定资料", "根据材料", "上述资料"]


def need_material(q):
    sub = (q.get("sub") or "")
    stem = (q.get("stem") or "")
    if any(s in sub for s in MAT_SUBS):
        return True
    if any(k in stem for k in MAT_KEYWORDS):
        return True
    return False


def main():
    print("=" * 66)
    print("  修复材料错误关联")
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
            mimg = q.get("materialImgs") or []
            if not mat and not mimg:
                continue
            if need_material(q):
                continue
            # 不该带材料 → 清空
            if len(samples) < 5:
                samples.append((q.get("id"), q.get("sub"),
                                (q.get("stem") or "")[:36], mat[:28]))
            q["material"] = ""
            q.pop("materialImgs", None)
            q.pop("matNo", None)
            changed += 1

        if changed:
            print(f"  {name:12s} 清除错误材料 {changed} 题")
            for s in samples:
                print(f"      {s[0]} [{s[1]}] {s[2]}")
                print(f"          原材料: {s[3]}…")
            total += changed
            if APPLY:
                bak = path + ".matbak"
                if not os.path.exists(bak):
                    import shutil
                    shutil.copy(path, bak)
                json.dump(data, open(path, "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                print(f"      已写入 {name}")

    print()
    print(f"  合计清除: {total} 题")

    # 复核：还有多少题带材料
    print()
    print("=== 修复后仍带材料的题（应只剩材料题）===")
    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        withmat = [q for q in data if q.get("material") or q.get("materialImgs")]
        if withmat:
            wrong = [q for q in withmat if not need_material(q)]
            print(f"  {name:12s} 带材料 {len(withmat)} 题，其中不该带 {len(wrong)} 题")
            for w in wrong[:3]:
                print(f"      {w.get('id')} [{w.get('sub')}] {(w.get('stem') or '')[:30]}")

    if not APPLY:
        print("\n  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

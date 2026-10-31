"""标记源数据缺失的题目，前端给出明确提示

问题：
  部分网友回忆版题目在源仓库就标注为「缺失」：
    - **A**. 缺失题目正在全力以赴征集，将会第一时间上传。
    - **B**. 缺失
    - **C**. 缺失
    - **D**. 缺失
  前端直接显示「缺失」二字，用户困惑（以为是程序 bug）。

修复：
  1. 扫描所有分片，找出选项含「缺失」的题
  2. 给这些题打上 flags 标记（dataMissing: true）
  3. 前端检测该标记后显示明确提示

用法：
  python scripts/mark_missing_questions.py --dry-run
  python scripts/mark_missing_questions.py --apply
"""

import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

APPLY = "--apply" in sys.argv
SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]


def main():
    print("=" * 66)
    print("  标记数据缺失的题目")
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
            opts = [str(o) for o in (q.get("options") or [])]
            miss_cnt = sum(1 for o in opts if "缺失" in o)
            if miss_cnt == 0:
                continue
            flags = q.get("flags") or []
            if isinstance(flags, list):
                if "dataMissing" not in flags:
                    flags.append("dataMissing")
                    q["flags"] = flags
                    changed += 1
            if len(samples) < 3:
                samples.append((q.get("id"), miss_cnt, len(opts),
                                (q.get("stem") or "")[:34]))

        if changed:
            print(f"  {name:12s} 标记 {changed} 题")
            for s in samples:
                print(f"      {s[0]}: {s[1]}/{s[2]} 个选项缺失 | {s[3]}")
            total += changed
            if APPLY:
                bak = path + ".missbak"
                if not os.path.exists(bak):
                    import shutil
                    shutil.copy(path, bak)
                json.dump(data, open(path, "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                print(f"      已写入 {name}")

    print()
    print(f"  合计标记: {total} 题")
    if not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

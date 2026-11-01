"""最终材料清理：连 materialImgs 一起判断

问题：
  之前的清理规则有一条 `if q.get("materialImgs"): continue`，
  导致「挂着 materialImgs 的错配材料」被跳过。

  实例：
    graph 11367775  sub=图形推理
      stem: 从所给的四个选项中，选出最合适的一个填入问号处…
      material: 在环太湖自行车比赛中…（完全无关）
      materialImgs: 1 张图（属于那份无关材料）
    verbal 5445827  sub=语句表达
      stem: 构建新发展格局的关键在于经济循环的____…
      material: 降雨来源于云层…（完全无关）
      materialImgs: 3 张

规则：
  1. sub == 图形推理 → 一律清空 material / materialImgs / matNo
  2. sub ∈ {逻辑填空, 语句表达} 且题干含 ____ 且不引用材料 → 清空
  3. 资料分析类（增长/比重/平均数/倍数/综合）与题干引用材料的一律保留
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
KEEP_KW = ("文章", "文中", "这段文字", "给定资料", "根据材料",
           "上述资料", "本文", "上述信息", "以上信息", "上文")


def main():
    print("=" * 70)
    print("  最终材料清理（含 materialImgs）")
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
            if not mat and not mimg:
                continue
            sub = q.get("sub") or ""
            stem = q.get("stem") or ""

            if sub in DATA_SUBS:
                continue
            if any(k in stem for k in KEEP_KW):
                continue

            drop = False
            if sub == "图形推理":
                drop = True
            elif sub in ("逻辑填空", "语句表达") and "____" in stem:
                drop = True

            if not drop:
                continue

            if len(samples) < 4:
                samples.append((q.get("id"), sub,
                                len(mat), len(mimg), stem[:36]))
            q["material"] = ""
            q.pop("materialImgs", None)
            q.pop("matNo", None)
            n += 1

        if n:
            print(f"  {name:10s} 清理 {n} 题")
            for s in samples:
                print(f"      {s[0]} [{s[1]}] 材料{s[2]}字 图{s[3]}张 | {s[4]}")
            total += n
            if APPLY:
                bak = path + ".matfinalbak"
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

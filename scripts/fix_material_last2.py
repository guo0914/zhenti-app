"""材料清理收尾：覆盖类比/定义判断与长题干片段阅读

剩余错配模式：
  1. 类比推理 / 定义判断 挂材料
     例：judge 11367761「元宇宙：虚拟性」挂环太湖自行车赛材料
     这两类题型自带定义与词项，不需要外部材料。

  2. 片段阅读 长题干挂无关材料
     例：verbal 5747296「中国是世界第二大经济体…」挂遥感材料
     片段阅读的题干本身通常已含文段；若题干很长且与材料重合极低，
     说明材料是错配的。

规则（在 fix_material_last.py 之后执行）：
  · sub ∈ {类比推理, 定义判断} → 清空（除非题干引用材料）
  · 其他非资料分析题 → 题干 >= 60 字且与材料 2-gram 重合 < 12% 时清空
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

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]
DATA_SUBS = ("增长", "比重", "平均数", "倍数", "综合")
KEEP_KW = ("文章", "文中", "这段文字", "给定资料", "根据材料", "上述资料",
           "本文", "上述信息", "以上信息", "上文", "文意", "上述条件",
           "根据上述", "如图所示", "如图")


def grams(t, n=2):
    t = re.sub(r"[\s\u00a0\u3000_]+", "", t)
    return {t[i:i + n] for i in range(len(t) - n + 1)} if len(t) >= n else set()


def overlap(a, b):
    ga = grams(a)
    if not ga:
        return 1.0
    gb = grams(b)
    return len(ga & gb) / len(ga) if gb else 0.0


def main():
    print("=" * 70)
    print("  材料清理收尾（类比/定义判断 + 长题干片段阅读）")
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
            if not mat or mat.strip() in ("[图]", "[图片]"):
                continue
            sub = q.get("sub") or ""
            stem = q.get("stem") or ""
            if sub in DATA_SUBS:
                continue
            if any(k in stem for k in KEEP_KW):
                continue

            drop = False
            reason = ""
            if sub in ("类比推理", "定义判断"):
                drop = True
                reason = "类比/定义无需材料"
            elif len(stem) >= 60 and overlap(stem, mat) < 0.12:
                drop = True
                reason = f"长题干重合{overlap(stem, mat):.0%}"

            if not drop:
                continue

            if len(samples) < 4:
                samples.append((q.get("id"), sub, reason, stem[:34]))
            q["material"] = ""
            q.pop("materialImgs", None)
            q.pop("matNo", None)
            n += 1

        if n:
            print(f"  {name:10s} 清理 {n} 题")
            for s in samples:
                print(f"      {s[0]} [{s[1]}] {s[2]} | {s[3]}")
            total += n
            if APPLY:
                bak = path + ".matlastbak"
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

"""全面审计：找出所有渲染/数据缺陷

审计维度：
  A. 选项为空（纯图片选项丢失）
  B. 选项含未解析的 HTML img 标签
  C. 选项图片与 imgs 不匹配
  D. 材料错配（题干自带横线却挂材料）
  E. 材料冗余（同一材料挂到过多题）
  F. 题干/选项缺失占位符
  G. 图片文件缺失
"""

import sys
import io
import os
import json
import re
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]


def load():
    out = {}
    for c in SHARDS:
        p = os.path.join(ZT, c + ".json")
        if os.path.exists(p):
            out[c] = json.load(open(p, encoding="utf-8"))
    return out


def grams(t, n=2):
    t = re.sub(r"[\s\u00a0\u3000_]+", "", t)
    return {t[i:i + n] for i in range(len(t) - n + 1)} if len(t) >= n else set()


def ratio(a, b):
    ga = grams(a)
    if not ga:
        return 1.0
    gb = grams(b)
    return len(ga & gb) / len(ga) if gb else 0.0


def main():
    data = load()
    print("=" * 70)
    print("  全面渲染/数据缺陷审计")
    print("=" * 70)

    # ── A. 选项为空 ──
    print("\n[A] 选项全空（纯图片选项，内容在图里）")
    a_list = []
    for c, arr in data.items():
        n = 0
        for q in arr:
            opts = [str(o).strip() for o in (q.get("options") or [])]
            if opts and not any(opts):
                n += 1
                a_list.append((c, str(q.get("id")), len(q.get("imgs") or []),
                               (q.get("stem") or "")[:34]))
        if n:
            print(f"   {c:10s} {n}")
    print(f"   合计 {len(a_list)} 题")
    for x in a_list[:8]:
        print(f"     [{x[0]}] {x[1]}  imgs={x[2]}  {x[3]}")

    # ── B. 选项含未解析 HTML img ──
    print("\n[B] 选项含未解析的 <img> 标签")
    b_list = []
    for c, arr in data.items():
        for q in arr:
            hits = [o for o in (q.get("options") or [])
                    if "<img" in str(o).lower()]
            if hits:
                b_list.append((c, str(q.get("id")), len(hits),
                               (q.get("stem") or "")[:30]))
    print(f"   合计 {len(b_list)} 题")
    for x in b_list[:8]:
        print(f"     [{x[0]}] {x[1]}  含图选项={x[2]}  {x[3]}")

    # ── C. 选项空 + 选项图数量与选项数不符 ──
    # 注意：选项图存在 optionImgs（与 options 等长），不是 imgs（题干配图）。
    # 早期用 imgs 判据会把「选项图齐全、题干另有配图」的题误报成缺图。
    print("\n[C] 选项全空但 optionImgs 数量 < 选项数（可能丢选项图）")
    c_list = []
    for c, arr in data.items():
        for q in arr:
            opts = [str(o).strip() for o in (q.get("options") or [])]
            optimgs = [i for i in (q.get("optionImgs") or []) if i]
            if opts and not any(opts) and len(optimgs) < len(opts):
                c_list.append((c, str(q.get("id")), len(opts), len(optimgs),
                               (q.get("stem") or "")[:30]))
    print(f"   合计 {len(c_list)} 题")
    for x in c_list[:10]:
        print(f"     [{x[0]}] {x[1]}  选项{x[2]}个 选项图{x[3]}张  {x[4]}")

    # ── D. 材料错配：题干自带 ____ 却挂材料 ──
    print("\n[D] 题干自带____却挂材料（材料多余）")
    KEEP_KW = ("文章", "文中", "这段文字", "给定资料", "根据材料",
               "上述资料", "本文", "上述信息", "以上信息", "上文")
    KEEP_SUB = ("增长", "比重", "平均数", "倍数", "综合")
    d_list = []
    for c, arr in data.items():
        for q in arr:
            mat = q.get("material") or ""
            stem = q.get("stem") or ""
            sub = q.get("sub") or ""
            if not mat or "____" not in stem:
                continue
            if q.get("materialImgs"):
                continue
            if mat.strip() in ("[图]", "[图片]"):
                continue
            if sub in KEEP_SUB:
                continue
            if any(k in stem for k in KEEP_KW):
                continue
            d_list.append((c, str(q.get("id")), sub, len(mat), stem[:30]))
    print(f"   合计 {len(d_list)} 题")
    for x in d_list[:12]:
        print(f"     [{x[0]}] {x[1]} [{x[2]}] 材料{x[3]}字  {x[4]}")

    # ── E. 同一材料挂到过多题 ──
    print("\n[E] 同一材料文本被挂到 >=15 题（可能扩散）")
    bucket = defaultdict(list)
    for c, arr in data.items():
        for q in arr:
            mat = (q.get("material") or "").strip()
            if len(mat) > 100:
                bucket[(c, mat[:60])].append(str(q.get("id")))
    over = [(k, v) for k, v in bucket.items() if len(v) >= 15]
    over.sort(key=lambda x: -len(x[1]))
    print(f"   {len(over)} 组")
    for (c, head), ids in over[:10]:
        print(f"     [{c}] {len(ids)} 题  材料开头「{head[:34]}」")

    # ── F. 占位符残留 ──
    print("\n[F] 题干/选项含 [图] 等占位符")
    f_list = []
    for c, arr in data.items():
        for q in arr:
            stem = q.get("stem") or ""
            opts = " ".join(str(o) for o in (q.get("options") or []))
            if "[图]" in stem or "[图]" in opts:
                f_list.append((c, str(q.get("id")), stem[:30]))
    print(f"   合计 {len(f_list)} 题")
    for x in f_list[:8]:
        print(f"     [{x[0]}] {x[1]}  {x[2]}")

    # ── G. 图片文件缺失 ──
    print("\n[G] 图片文件缺失")
    miss = 0
    tot = 0
    for c, arr in data.items():
        for q in arr:
            for s in (q.get("imgs") or []) + (q.get("materialImgs") or []):
                if not s:
                    continue
                tot += 1
                if not os.path.exists(os.path.join(ROOT, "site", s)):
                    miss += 1
    print(f"   引用 {tot} 张，缺失 {miss}")


if __name__ == "__main__":
    main()

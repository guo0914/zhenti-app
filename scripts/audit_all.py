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

    # ── G. 图片文件缺失（三类字段都要查，含选项图） ──
    print("\n[G] 图片文件缺失")
    miss = 0
    tot = 0
    for c, arr in data.items():
        for q in arr:
            for s in ((q.get("imgs") or []) + (q.get("materialImgs") or [])
                      + (q.get("optionImgs") or [])):
                if not s:
                    continue
                tot += 1
                if not os.path.exists(os.path.join(ROOT, "site", s)):
                    miss += 1
    print(f"   引用 {tot} 张，缺失 {miss}")

    # ── H. 题干配图 imgs 与选项图 optionImgs 重复 ──
    # 根因：parse_zhenti.py 按整个题目块提取 <img>，选项里的图也进了 imgs，
    # 前端会在题干下方多渲染一张本属于选项 A 的图。
    print("\n[H] 题干配图 imgs 与选项图 optionImgs 重复（题干下会多出一张选项图）")
    h_list = []
    for c, arr in data.items():
        for q in arr:
            imgs = [x for x in (q.get("imgs") or []) if x]
            oi = [x for x in (q.get("optionImgs") or []) if x]
            if not imgs or not oi:
                continue
            inter = set(imgs) & set(oi)
            if inter:
                h_list.append((c, str(q.get("id")), q.get("sub") or "",
                               len(inter), sorted(inter)[0]))
    print(f"   合计 {len(h_list)} 题")
    for x in h_list[:10]:
        print(f"     [{x[0]}] {x[1]} [{x[2]}] 重复{x[3]}张  {x[4]}")

    # ── I. optionHtml 内联图丢失 ──
    # 根因：选项里文字与图片混排（如「甘肃>广东>海南>浙江」），
    # 解析时把 <img> 抽成 optionImgs，前端「有图只渲染图」，文字被丢弃。
    # optionHtml 保存「文字+原位图片」，其 <img> 数不应少于 optionImgs 非空数。
    print("\n[I] optionHtml 内联图丢失（选项文字被图片挤掉）")
    i_list = []
    for c, arr in data.items():
        for q in arr:
            oh = q.get("optionHtml") or []
            if not oh:
                continue
            n_html = sum(str(h).count("<img") for h in oh)
            n_opt = len([x for x in (q.get("optionImgs") or []) if x])
            if n_html < n_opt:
                i_list.append((c, str(q.get("id")), q.get("sub") or "", n_html, n_opt))
    print(f"   合计 {len(i_list)} 题")
    for x in i_list[:10]:
        print(f"     [{x[0]}] {x[1]} [{x[2]}] html图{x[3]} < optionImgs{x[4]}")

    # ── J. 选项文本残留 HTML 标签 ──
    # 根因：guokao 分支解析选项时保留了 <p>/<u> 等标签，
    # 前端 esc() 会把它们当普通文字显示，用户看到「<p>…</p>」。
    print("\n[J] 选项文本残留 HTML 标签（界面会显示成 <p>…</p>）")
    j_list = []
    tag_re = re.compile(r"<(p|u|br|span|div|strong|b|em|img)\b", re.I)
    for c, arr in data.items():
        for q in arr:
            for i, o in enumerate(q.get("options") or []):
                if o and tag_re.search(str(o)):
                    j_list.append((c, str(q.get("id")), i, str(o)[:40]))
                    break
    print(f"   合计 {len(j_list)} 题")
    for x in j_list[:10]:
        print(f"     [{x[0]}] {x[1]} 选项{x[2]}  {x[3]}")

    # ── K. 题干要求「画线/划线」但选项没有下划线 ──
    # 根因：源 markdown 用 <u>…</u> 标注画线部分，
    # parse_zhenti.py 的 strip_tags 把标签剥掉，画线信息彻底丢失，
    # 题干说「下列画线的动词」而界面上没有任何画线，题目无法作答。
    # 判据：题干出现「下列/以下/选项中 …… 画线/划线」这种**指向选项**的说法，
    # 且没有任何选项的 optionHtml 里带 text-decoration:underline。
    # 排除「划线处 / 画线处」（那是填空占位，不是下划线），
    # 也排除「画线词 / 画线句」（那是指题干或材料里的词，不是选项）。
    print("\n[K] 题干要求画线但选项没有下划线（画线标记被剥掉）")
    k_list = []
    UL_RE = re.compile(r"(?:下列|以下|选项中|四个选项)[^。；]{0,14}(?:画线|划线)(?!处|词|句|部分|位置)")
    for c, arr in data.items():
        for q in arr:
            stem = str(q.get("stem") or "")
            if not UL_RE.search(stem):
                continue
            oh = q.get("optionHtml") or []
            has_ul = any("text-decoration:underline" in str(h) for h in oh)
            if not has_ul:
                k_list.append((c, str(q.get("id")), stem[:50]))
    print(f"   合计 {len(k_list)} 题")
    for x in k_list[:10]:
        print(f"     [{x[0]}] {x[1]}  {x[2]}")


if __name__ == "__main__":
    main()

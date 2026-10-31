#!/usr/bin/env python3
"""把采集到的国考卷合并进现有题库

策略：
  1. 采集数据有「原卷题号 no」→ 用于还原卷面顺序
  2. 与现有数据按 qid 去重（同一道题保留采集版，因为它有正确卷序）
  3. 输出为独立分片 site/data/zt/guokao.json，不污染现有分片
  4. 同时输出套卷索引 site/data/zt-guokao-papers.json

用法：
  python scripts/merge_guokao.py
"""

import sys
import io
import os
import re
import json
import glob
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GK_DIR = os.path.join(ROOT, "..", "law_ocr", "guokao")
ZT = os.path.join(ROOT, "site", "data", "zt")
OUT_Q = os.path.join(ZT, "guokao.json")
OUT_P = os.path.join(ROOT, "site", "data", "zt-guokao-papers.json")

CAT_NAME = {
    "politics": "政治理论", "common": "常识判断", "verbal": "言语理解与表达",
    "quantity": "数量关系", "judge": "判断推理", "data": "资料分析",
}
ORDER = ["politics", "common", "verbal", "quantity", "judge", "data"]


def load_collected():
    out = {}
    for f in glob.glob(os.path.join(GK_DIR, "*.json")):
        if f.endswith("_summary.json"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        paper = d.get("paper")
        if paper and d.get("questions"):
            out[paper] = d
    return out


def main():
    collected = load_collected()
    if not collected:
        print("x 没有采集数据")
        sys.exit(1)

    # 现有 qid（用于标记是否重复）
    existing = set()
    for f in os.listdir(ZT):
        if not f.endswith(".json") or f.startswith("zt-"):
            continue
        d = json.load(open(os.path.join(ZT, f), encoding="utf-8"))
        qs = d if isinstance(d, list) else d.get("questions", [])
        for q in qs:
            existing.add(str(q.get("id")))

    merged = []
    papers_meta = []

    # 卷 → 短标识（用于构造唯一 id）
    def paper_tag(paper):
        y = re.search(r"(20\d{2})", paper)
        year = y.group(1) if y else "0000"
        if "行政执法" in paper:
            sub = "xz"
        elif "地市级" in paper:
            sub = "ds"
        elif "副省级" in paper:
            sub = "fs"
        else:
            sub = "xx"
        return f"{year}{sub}"

    for paper, d in sorted(collected.items(), key=lambda x: x[0], reverse=True):
        qs = d["questions"]
        # 按原卷题号排序
        qs.sort(key=lambda q: (q["no"], ORDER.index(q["cat"]) if q["cat"] in ORDER else 99))

        tag = paper_tag(paper)
        mods = defaultdict(int)
        paper_qs = []

        for q in qs:
            cat = q["cat"]
            mods[cat] += 1
            # 关键：id 必须跨卷唯一。同源数据里同一 qid 会出现在多个卷
            # （地市级与行政执法卷有大量重叠题），只用 gk-<qid> 会重复。
            uid = f"gk-{tag}-{q['qid']}"
            item = {
                "id": uid,
                "cat": cat,
                "sub": q.get("sub") or "",
                "paper": paper,
                "year": str(re.search(r"(20\d{2})", paper).group(1)) if re.search(r"(20\d{2})", paper) else "",
                "region": "国考",
                "no": str(q["no"]),          # ← 原卷题号
                "stem": q["stem"],
                "options": q["options"],
                "optionKeys": q["optionKeys"],
                "answer": q["answer"],
                "answerRaw": q["answer"],
                "explain": q["explain"],
                "imgs": [],
                "tf": False,
                "material": q.get("material", ""),
                "srcQid": str(q["qid"]),
                "dup": str(q["qid"]) in existing,
            }
            merged.append(item)
            paper_qs.append(item)

        # 卷元信息
        m_year = re.search(r"(20\d{2})", paper)
        m_sub = re.search(r"（([^）]*)网友回忆版）", paper)
        papers_meta.append({
            "paper": paper,
            "year": m_year.group(1) if m_year else "",
            "subtype": m_sub.group(1) if m_sub else "",
            "region": "国考",
            "total": len(paper_qs),
            "modules": [{"cat": c, "name": CAT_NAME.get(c, c), "count": mods[c]}
                        for c in ORDER if mods.get(c)],
            "moduleCount": len(mods),
            "maxNo": max(q["no"] for q in qs) if qs else 0,
            "kind": "guokao",
            "qids": [q["id"] for q in paper_qs],
            # 完整卷判定：>=100 题且 >=5 模块 → A 级
            "grade": "A" if (len(paper_qs) >= 100 and len(mods) >= 5) else
                     ("B" if len(paper_qs) >= 60 else "C"),
            "noSpan": max(q["no"] for q in qs) if qs else 0,
            "noGaps": 0,
            "coverage": 1.0,
        })

    json.dump(merged, open(OUT_Q, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

    payload = {
        "meta": {
            "name": "国考行测套卷（地市级 / 行政执法）",
            "total": len(papers_meta),
            "totalQuestions": len(merged),
        },
        "papers": papers_meta,
    }
    json.dump(payload, open(OUT_P, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # JS 版本
    js = ("/* 国考套卷索引（由 scripts/merge_guokao.py 生成）*/\n"
          "window.__ZT_GUOKAO_PAPERS__ = "
          + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    open(os.path.join(ROOT, "site", "data", "zt-guokao-papers.js"), "w",
         encoding="utf-8").write(js)

    # 报告
    print("=" * 70)
    print("国考卷合并完成")
    print("=" * 70)
    for pm in papers_meta:
        print(f"\n{pm['year']} {pm['subtype']}  {pm['total']} 题  "
              f"{pm['moduleCount']} 模块  最大题号 {pm['maxNo']}")
        for m in pm["modules"]:
            print(f"    {m['name']}: {m['count']}")

    dupN = sum(1 for q in merged if q["dup"])
    print(f"\n{'='*70}")
    print(f"合计 {len(merged)} 题（其中 {dupN} 题已存在于现有题库）")
    print(f"输出: {OUT_Q} ({os.path.getsize(OUT_Q)/1024:.0f} KB)")

    # ── 并入主套卷索引（用新国考卷替换同名旧卷）──
    MAIN_IDX = os.path.join(ROOT, "site", "data", "zt-papers.json")
    main = json.load(open(MAIN_IDX, encoding="utf-8"))
    gk_map = {p["paper"]: p for p in papers_meta}

    new_papers = []
    replaced = 0
    for p in main.get("papers", []):
        if p["paper"] in gk_map:
            new_papers.append(gk_map.pop(p["paper"]))   # 用新数据替换
            replaced += 1
        else:
            new_papers.append(p)
    # 剩下没被替换的（新增卷）
    added = 0
    for p in gk_map.values():
        new_papers.append(p)
        added += 1

    new_papers.sort(key=lambda x: (-int(x.get("year") or 0),
                                    {"A": 0, "B": 1, "C": 2}[x.get("grade", "C")],
                                    -x["total"]))
    main["papers"] = new_papers
    main["meta"]["total"] = len(new_papers)
    main["meta"]["totalQuestions"] = sum(p["total"] for p in new_papers)
    gc = {}
    for p in new_papers:
        g = p.get("grade", "C")
        gc[g] = gc.get(g, 0) + 1
    main["meta"]["gradeCount"] = gc
    main["meta"]["name"] = "行测真题套卷索引（含国考地市级/行政执法全卷）"

    json.dump(main, open(MAIN_IDX, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    js = ("/* 真题套卷索引（由 scripts/build_paper_index.py + merge_guokao.py 生成）*/\n"
          "window.__ZT_PAPERS__ = "
          + json.dumps(main, ensure_ascii=False, separators=(",", ":")) + ";\n")
    open(os.path.join(ROOT, "site", "data", "zt-papers.js"), "w",
         encoding="utf-8").write(js)

    print(f"\n主索引更新: 替换旧卷 {replaced} 套, 新增 {added} 套")
    print(f"现在共 {main['meta']['total']} 套 / {main['meta']['totalQuestions']} 题")
    print(f"评级分布: {gc}")


if __name__ == "__main__":
    main()

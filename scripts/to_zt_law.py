#!/usr/bin/env python3
"""法律专业科目题库 → 兼容现有 zt 格式的分片

将 parse_law.py 生成的 {科目}.json 转换为：
  site/data/zt/law.json   与 verbal/politics 等同构，前端无需改数据结构
  site/data/zt-index.json 追加 law 分类（由调用方处理）

字段映射（保持与 zt/*.json 完全一致）：
  id          → 全局唯一，用 科目拼音-题号
  cat         → 固定 "law"
  sub         → 章节名（第一讲 刑法论）
  paper       → "2026法考真金题·刑法（柏浪涛）"
  year        → 从 source 提取（2015金题-2-51 → 2015），否则 2026
  region      → 科目名
  no          → 题号
  stem        → 题干
  options     → 选项文本数组（字符串形式，与现有数据一致）
  optionKeys  → ["A","B","C","D"]
  answer      → 答案字母
  answerRaw   → 同 answer
  explain     → 解析全文
  imgs        → []
  tf          → false
  ── 额外字段（法律模块专用，前端按需读取）──
  kaodian     → 考点
  ocrScore    → OCR 置信度
  flags       → 可疑标记
  page        → 原书页码
"""

import sys, io, os, re, json, argparse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 科目 → 拼音/短码
SUBJECT_CODE = {
    "刑法": "xf", "民法": "mf", "民诉法": "msf", "刑诉法": "xsf",
    "行政法": "xzf", "商经知": "sxz", "三国法": "sgf", "理论法": "llf",
}


def load_law(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def to_zt_format(law_data, subject):
    """转换为 zt 通用格式。"""
    code = SUBJECT_CODE.get(subject, "law")
    author = law_data.get("author", "")
    out = []

    for q in law_data.get("questions", []):
        # 选项：按 A/B/C/D 顺序取文本
        opts_map = {o["k"]: o["v"] for o in q.get("options", [])}
        keys = sorted(opts_map.keys())
        if not keys:
            continue
        options = [opts_map[k] for k in keys]

        # 年份
        src = q.get("source", "")
        m = re.search(r"(20\d{2})", src)
        year = m.group(1) if m else "2026"

        # 章节作为 sub
        chapter = q.get("chapter") or ""
        sub = re.sub(r"^第[一二三四五六七八九十百零\d]+[讲章编]\s*", "", chapter).strip()
        if not sub:
            sub = chapter or "综合"

        out.append({
            "id": f"law-{code}-{q['no']}",
            "cat": "law",
            "sub": sub,
            "paper": f"法考真金题·{subject}" + (f"（{author}）" if author else ""),
            "year": year,
            "region": subject,
            "no": str(q["no"]),
            "stem": q["stem"],
            "options": options,
            "optionKeys": keys,
            "answer": q.get("answer", ""),
            "answerRaw": q.get("answer", ""),
            "explain": q.get("explain", ""),
            "imgs": [],
            "tf": False,
            # 法律模块扩展字段
            "kaodian": q.get("kaodian", ""),
            "ocrScore": q.get("ocr_score", 1.0),
            "flags": q.get("flags", []),
            "page": q.get("page"),
            "qtype": q.get("qtype", "单选"),
            "chapter": chapter,
            "source": q.get("source", ""),
        })

    return out


def main():
    ap = argparse.ArgumentParser(description="法律题库转 zt 格式")
    ap.add_argument("--in", dest="inp", required=True, help="parse_law.py 输出")
    ap.add_argument("--out", required=True, help="输出 zt 分片 JSON")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--keep-flawed", action="store_true",
                    help="保留有质量问题的题（默认剔除）")
    ap.add_argument("--suspect", default=None,
                    help="反查验证输出的可疑题 ID 清单（JSON 数组），这些题会被剔除")
    ap.add_argument("--merge-index", action="store_true",
                    help="同时把 law 分类写入 zt-index.json")
    ap.add_argument("--index", default=None, help="zt-index.json 路径")
    args = ap.parse_args()

    law = load_law(args.inp)
    questions = to_zt_format(law, args.subject)

    if not questions:
        print("x 没有可用题目")
        sys.exit(1)

    total_before = len(questions)

    # 反查验证的可疑题（答案与原文不一致等）→ 直接剔除，不猜
    suspect = set()
    if args.suspect and os.path.exists(args.suspect):
        with open(args.suspect, encoding="utf-8") as f:
            suspect = set(json.load(f))
        if suspect:
            questions = [q for q in questions if q["id"] not in suspect]
            print(f"[反查] 剔除可疑题 {len(suspect)} 题")

    # 默认剔除有质量问题的题（选项不全、缺答案等），保证用户看到的都是可用题
    if not args.keep_flawed:
        good = []
        for q in questions:
            flags = q.get("flags") or []
            # 严重问题：选项不全 / 缺答案 / 答案不在选项内 → 剔除
            if "选项不完整" in flags or "缺答案" in flags:
                continue
            if q["answer"]:
                ks = q.get("optionKeys", [])
                if ks and any(c not in ks for c in q["answer"]):
                    continue
            if len(q.get("options", [])) < 4:
                continue
            if any(len(v) < 5 for v in q.get("options", [])):
                continue
            good.append(q)
        questions = good

    # 统计
    with_ans = sum(1 for q in questions if q["answer"])
    clean = sum(1 for q in questions if not q["flags"])
    subs = {}
    for q in questions:
        subs[q["sub"]] = subs.get(q["sub"], 0) + 1
    years = {}
    for q in questions:
        years[q["year"]] = years.get(q["year"], 0) + 1

    print("=" * 55)
    print(f"科目: {args.subject}")
    print(f"原始解析: {total_before} 题")
    print(f"剔除问题题: {total_before - len(questions)} 题")
    print(f"最终入库: {len(questions)} 题")
    print(f"有答案: {with_ans} ({with_ans/max(len(questions),1)*100:.0f}%)")
    print(f"无标记问题: {clean} ({clean/max(len(questions),1)*100:.0f}%)")
    print(f"\n章节:")
    for s, n in sorted(subs.items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")
    print(f"\n年份分布:")
    for y, n in sorted(years.items(), reverse=True):
        print(f"  {y}: {n}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(args.out) / 1024
    print(f"\n[DONE] -> {args.out} ({size:.0f} KB)")

    # 更新索引
    if args.merge_index and args.index and os.path.exists(args.index):
        with open(args.index, encoding="utf-8") as f:
            idx = json.load(f)
        cats = idx.setdefault("categories", [])
        entry = {
            "key": "law",
            "name": "法律专业科目",
            "short": "法律",
            "count": len(questions),
            "papers": len(subs),
            "years": {y: years[y] for y in sorted(years)},
        }
        for i, c in enumerate(cats):
            if c.get("key") == "law":
                cats[i] = entry
                break
        else:
            cats.append(entry)
        with open(args.index, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=1)
        print(f"[索引] 已更新 {args.index}：law 分类 {len(questions)} 题")


if __name__ == "__main__":
    main()

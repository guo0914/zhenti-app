#!/usr/bin/env python3
"""题库结构交叉验证 —— 用原始 OCR 文本反查题目提取是否正确

思路：对每道题，回到它所在的 OCR 原始页，检查：
  1. 题干的关键片段是否真的存在于原文（防止编造）
  2. 选项内容是否都能在原文中找到（防止串题）
  3. 答案字母是否在原文的「本题答案为X」中出现
  4. 题号是否真的在原文中

这是「反向验证」——正向解析可能出错，但反向比对能发现串题、漏字、编造内容。

用法：
  python scripts/verify_law.py --ocr ../law_ocr/minfa.jsonl --data ../law_ocr/law_minfa.json --subject 民法
"""

import sys, io, os, re, json, argparse
from collections import Counter, defaultdict

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def norm(s):
    """归一化：去掉所有空白和标点，便于模糊比对。"""
    s = re.sub(r"[\s\u3000]+", "", s or "")
    s = re.sub(r"[，。；：、！？（）()\[\]【】“”\"'‘’·—－\-]", "", s)
    return s


def load_pages(path):
    pages = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            txt = "".join(i["t"] for i in r.get("left", []) + r.get("right", []))
            pages[r["page_no"]] = norm(txt)
    return pages


def main():
    ap = argparse.ArgumentParser(description="题库结构反查验证")
    ap.add_argument("--ocr", required=True, help="OCR JSONL")
    ap.add_argument("--data", required=True, help="题库 JSON")
    ap.add_argument("--subject", default="")
    ap.add_argument("--sample-len", type=int, default=20, help="比对片段长度")
    ap.add_argument("--dump-suspect", default=None, help="把可疑题 ID 写出到该文件")
    args = ap.parse_args()

    pages = load_pages(args.ocr)
    with open(args.data, encoding="utf-8") as f:
        qs = json.load(f)
    if isinstance(qs, dict):
        qs = qs.get("questions", [])

    # 页码映射：题库用书印页码，OCR 用物理页码，需要试探偏移
    offsets = range(0, 25)

    print("=" * 66)
    print(f"反查验证：{args.subject}（{len(qs)} 题，{len(pages)} 页原文）")
    print("=" * 66)

    # 先确定偏移：用若干题的题干片段试探
    def page_for(page_no, offset):
        return pages.get(page_no + offset, "")

    best_off, best_hit, best_total = 0, 0, 0
    for off in offsets:
        hit = total = 0
        for q in qs[:50]:
            pg = q.get("pdfPage") or (q.get("page") or 0) + off
            txt = pages.get(pg, "")
            if not txt:
                continue
            total += 1
            frag = norm(q.get("stem", ""))[:args.sample_len]
            if frag and frag in txt:
                hit += 1
        if total and hit > best_hit:
            best_off, best_hit, best_total = off, hit, total
        if off == 0 and total:
            pass

    # 用 pdfPage 字段优先
    probe_q = [q for q in qs if q.get("pdfPage")][:50]
    using_pdfpage = len(probe_q) >= 10
    if using_pdfpage:
        print(f"页码映射：使用 pdfPage 字段（{len(probe_q)} 题有该字段）")
        def get_page(q):
            return q.get("pdfPage")
    else:
        print(f"页码映射：试探偏移 offset={best_off}（命中 {best_hit}/{best_total}）")
        def get_page(q):
            p = q.get("page")
            return p + best_off if p else None

    problems = defaultdict(list)
    checked = 0

    for q in qs:
        qid = q.get("id") or q.get("no") or "?"
        pg = get_page(q)
        if not pg or pg not in pages:
            problems["原文页缺失"].append(qid)
            continue
        checked += 1

        # 本题内容可能跨页：取本题页 + 后续 2 页作为检索窗口
        window = ""
        for k in range(0, 3):
            window += pages.get(pg + k, "")

        # 题干可能从上一页末尾开始，窗口再往前扩 1 页
        window_wide = pages.get(pg - 1, "") + window

        # 1. 题干片段必须在原文中（用多个片段比对，避免一处 OCR 错就判失败）
        stem_n = norm(q.get("stem", ""))
        if len(stem_n) >= 15:
            frags = [
                stem_n[:args.sample_len],
                stem_n[len(stem_n)//3:][:args.sample_len],
                stem_n[-args.sample_len:] if len(stem_n) > args.sample_len else "",
            ]
            frags = [f for f in frags if len(f) >= 10]
            # 至少一个片段命中即可
            if frags and not any(f in window_wide for f in frags):
                problems["题干不在原文"].append(qid)

        # 2. 选项片段：允许一定比例对不上（OCR 断行/错字会导致片段失配）
        #    只有「超过一半选项都对不上」才判定为串题（严重问题）
        opt_found = opt_total = 0
        for v in (q.get("options") or []):
            vn = norm(str(v))
            if len(vn) < 8:
                continue
            opt_total += 1
            # 多个片段任一命中即算找到（OCR 断行时首段可能跨页断开）
            frags = [vn[:args.sample_len],
                     vn[len(vn)//2:][:args.sample_len],
                     vn[-args.sample_len:] if len(vn) > args.sample_len else ""]
            frags = [f for f in frags if len(f) >= 8]
            if any(f in window_wide for f in frags):
                opt_found += 1
        if opt_total and opt_found * 2 < opt_total:
            problems[f"选项大面积不匹配({opt_total-opt_found}/{opt_total})"].append(qid)

        # 3. 答案一致性（宽松：原文中该题的答案集合里包含本题答案即可）
        #    各书答案标记不同：本题答案为X / 本题的正确答案为X / 正确答案为X
        ans = q.get("answer") or ""
        if ans:
            found = re.findall(
                r"(?:本题的?正确答案|正确答案|本题答案|答案)\s*(?:为|是)?\s*[：:]?\s*([A-D]{1,4})",
                window.replace(" ", ""))
            if not found:
                problems["原文无答案标记"].append(qid)
            elif ans not in found:
                problems["答案与原文不一致"].append(qid)

        # 4. 题号必须在原文中
        no = str(q.get("no") or "")
        if no and not re.search(rf"(?<!\d){no}\s*[.、]", window_wide):
            problems["题号不在原文"].append(qid)

    print(f"\n【反查结果】已核对 {checked} 题")
    total_bad = 0
    for k in sorted(problems, key=lambda x: -len(problems[x])):
        v = problems[k]
        total_bad += len(v)
        print(f"  {len(v):>4}  {k}")
        print(f"        例: {', '.join(v[:5])}")
    if not problems:
        print("  ✅ 全部题目均能在原文中定位")

    print(f"\n  问题总计: {total_bad} 处")

    # 输出可疑题 ID 清单，供 to_zt_law.py 剔除
    suspect = set()
    for k, v in problems.items():
        # 「原文无答案标记」不算硬错误（可能跨页更远）
        if k in ("原文页缺失", "答案与原文不一致"):
            suspect.update(v)
    if suspect and args.dump_suspect:
        with open(args.dump_suspect, "w", encoding="utf-8") as f:
            json.dump(sorted(suspect), f, ensure_ascii=False, indent=1)
        print(f"\n  可疑题清单已写出: {args.dump_suspect}（{len(suspect)} 题）")

    print("=" * 66)

    sys.exit(0 if total_bad == 0 else 1)


if __name__ == "__main__":
    main()

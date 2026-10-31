"""
修复资料分析题库中 OCR 识别错误的题目。

问题：171 道题的选项为空，但 OCR 原始数据（records.json）里其实有选项记录，
      是 build_final.py 的题块分段逻辑把它们归到了错误的题上。

思路：
  1. 用 records.json 的 (page, y) 坐标，为每道题重新配对 A/B/C/D 选项
  2. 清洗选项/题干中的 OCR 错字（L→1, 巧→15, &→8, 彐→3, 亻乙》亡→亿元 等）
  3. 写回 bank.json 和 bank.js

用法：python fix_ocr_options.py [--dry-run]
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

APP = os.path.dirname(os.path.abspath(__file__))
PF = os.path.abspath(os.path.join(APP, "..", ".pdfwork"))
BANK_JSON = os.path.join(APP, "site", "data", "bank.json")
BANK_JS = os.path.join(APP, "site", "data", "bank.js")
RECORDS = os.path.join(PF, "records.json")


# ---------------------------------------------------------------- 错字清洗

def fix_text(t: str) -> str:
    """清洗 OCR 错字。只处理高置信度、上下文明确的模式。"""
    if not t:
        return t
    s = t

    # 1) 「亻乙》亡」「亻乙元」「亻乙》」等 = 亿元
    s = re.sub(r"亻\s*乙\s*》\s*亡", "亿元", s)
    s = re.sub(r"亻\s*乙\s*》", "亿元", s)
    s = re.sub(r"亻\s*乙\s*元", "亿元", s)
    s = re.sub(r"亻\s*乙", "亿", s)
    s = re.sub(r"丿\s*$", "元", s)

    # 2) 「&」= 8 且常丢小数点：9&7% → 98.7%，1&4% → 18.4%
    s = re.sub(r"(?<=\d)&(?=\d)", "8.", s)      # 数字之间的 & → 8.（补小数点）
    s = re.sub(r"(?<=\d)&", "8", s)              # 其它位置的 &
    s = re.sub(r"&(?=\d)", "8", s)
    s = re.sub(r"&", "8", s)

    # 3) 「巧」= 15
    s = re.sub(r"巧", "15", s)

    # 4) 「L」的处理：
    #    - 在数字开头（前面无数字）：L94 → 1.94
    #    - 在两个数字之间：2L6 → 21.6（L=1，后面补小数点）
    #    - 其它：L → 1
    s = re.sub(r"(?<![\d.])L(?=[\d])", "1.", s)               # L94 → 1.94
    s = re.sub(r"(?<=\d)L(?=\d)", "1.", s)                     # 2L6 → 21.6
    s = re.sub(r"(?<=\d)L(?=[%％万亿元])", "1", s)
    s = re.sub(r"L(?=\d)", "1", s)
    s = re.sub(r"L", "1", s)

    # 5) 彐 = 3，且常伴随小数点丢失：36彐% → 36.3%，3彐7人 → 3.7人
    s = re.sub(r"(\d)彐(?=[%％])", r"\1.3", s)               # 36彐% → 36.3%
    s = re.sub(r"(\d)彐(?=[人万亿元]|$)", r"\1.3", s)         # 3彐7人 → 先处理 3彐
    s = re.sub(r"彐(\d)", r"3\1", s)                          # 彐后接数字
    s = re.sub(r"(?<=[\d．.])彐", "3", s)
    s = re.sub(r"彐", "3", s)
    # 数字后直接跟单位、但中间丢小数点的高频模式
    s = re.sub(r"(\d)．(?=[人万亿元%])", r"\1", s)
    # 6) 〇 = 0
    s = re.sub(r"(?<=[\d．.])〇", "0", s)
    s = re.sub(r"〇(?=[\d．.%％])", "0", s)
    # 7) 数字残渣清理
    s = s.replace("亿兀", "亿元").replace("亻乙元", "亿元")
    s = re.sub(r"(\d)[丿匚丨|\s]+$", r"\1元", s)      # 7000—8000丿1 → 7000—8000元
    s = re.sub(r"[丿匚丨]", "", s)
    s = re.sub(r"(?<=\d)[．](?=[^\d])", ".", s)
    s = re.sub(r"(\d)\.(\d)[．·]", r"\1.\2", s)
    # 8) 全角/半角归一
    s = s.replace("％", "%")
    s = re.sub(r"(?<=\d)[．·，](?=\d)", ".", s)
    s = re.sub(r"(?<=\d)一(?=[\d])", "—", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    # 9) 连续小数点等异常
    s = re.sub(r"\.{2,}", ".", s)
    s = re.sub(r"(\d)\.(?=[%万亿元]|$)", r"\1", s)
    return s.strip()


# ---------------------------------------------------------------- 选项配对

def clean_stem(s: str) -> str:
    """清理题干：剔除 OCR 混入的选项数字 / 序号噪声。"""
    if not s:
        return s
    t = s
    # 1) 题干末尾孤立的数字或图表刻度（"...正确的是：0.40.2"）
    t = re.sub(r"([：:）)])\s*[\d.]{1,8}$", r"\1", t)
    t = re.sub(r"[，,、]?\s*\d{1,2}$", "", t)
    t = re.sub(r"([？?）)])\s*\d{1,2}$", r"\1", t)
    # 2) 去掉末尾悬空的标点堆积
    t = re.sub(r"[，,]{2,}", "，", t)
    t = re.sub(r"^[，,、]\s*", "", t)
    return t.strip()


def rebuild_stem(by_page: dict, q: dict) -> str | None:
    """用 OCR 记录重建被切断的题干：合并同一行（y 相近）的多个文本片段。"""
    pg, y = q.get("pg"), q.get("y")
    if not pg or not y:
        return None
    recs = by_page.get(pg, [])
    # 收集 y 在 [y-8, y+25] 内的题干类记录（q / text），按 x 排序
    line = [r for r in recs
            if r["kind"] in ("q", "text") and abs(r["y"] - y) <= 25]
    if len(line) < 2:
        return None
    line.sort(key=lambda r: r["x"])
    merged = "".join(r["text"] for r in line)
    merged = re.sub(r"\s+", "", merged)
    # 只接受「明显更完整」且长度合理的结果，避免把下一题内容拼进来
    if len(merged) <= len(q["stem"]) or len(merged) > len(q["stem"]) + 120:
        return None
    return merged


def build_option_index(records: list[dict]) -> dict:
    """按 page 建立选项索引。"""
    by_page = defaultdict(list)
    for r in records:
        by_page[r["page"]].append(r)
    for p in by_page:
        by_page[p].sort(key=lambda r: (r["y"], r["x"]))
    return by_page


def find_options(by_page: dict, pg: int, y: float, y_end: float | None) -> list[str]:
    """在 (y, y_end) 区间内按 A→B→C→D 顺序找选项。"""
    if not pg or not y:
        return []
    limit = y_end if y_end and y_end > y else y + 700
    cands = [r for r in by_page.get(pg, [])
             if r["kind"] == "opt" and y < r["y"] < limit]
    if not cands:
        return []

    opts = ["", "", "", ""]
    cur = -1
    for r in cands:
        letter = r.get("letter")
        if not letter:
            continue
        li = "ABCD".index(letter) if letter in "ABCD" else -1
        if li < 0:
            continue
        if li == cur + 1:
            cur = li
            opts[li] = r["text"]
        elif li <= cur:
            # 重复或回退，忽略
            continue
    return opts


# ---------------------------------------------------------------- 主流程

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv

    if not os.path.exists(RECORDS):
        print(f"缺少 {RECORDS}")
        sys.exit(1)
    records = json.load(open(RECORDS, encoding="utf-8"))
    by_page = build_option_index(records)

    bank = json.load(open(BANK_JSON, encoding="utf-8"))
    qs = bank["questions"]

    # 建立题号 -> 下一题 y（用于限定选项搜索范围）的索引
    # bank 里每题有 pg / y 字段
    all_pos = [(q.get("pg"), q.get("y"), q) for q in qs if q.get("pg") and q.get("y")]
    all_pos.sort(key=lambda x: (x[0], x[1]))

    fixed_opts = 0
    fixed_text = 0
    still_empty = 0
    rebuilt = 0
    stem_rebuilt = 0
    for i, q in enumerate(qs):
        # 1) 先尝试重建被切断的题干（同行多片段合并）
        rebuilt_stem = rebuild_stem(by_page, q)
        if rebuilt_stem:
            q["stem"] = rebuilt_stem
            stem_rebuilt += 1
            # 重建成功：只做错字清洗，不剔除末尾数字（已经是完整题干）
            old_stem = q["stem"]
            q["stem"] = fix_text(q["stem"])
            if q["stem"] != old_stem:
                fixed_text += 1
        else:
            # 未能重建：清洗 + 剔除混入的选项数字噪声
            old_stem = q["stem"]
            q["stem"] = clean_stem(fix_text(q["stem"]))
            if q["stem"] != old_stem:
                fixed_text += 1

        pg, y = q.get("pg"), q.get("y")

        # 2) 从 OCR 原文重建选项（最重要：修掉历史污染，如 L94%→194%）
        if pg and y:
            y_end = None
            for (p2, y2, q2) in all_pos:
                if p2 == pg and y2 > y + 20:
                    y_end = y2 - 5
                    break
            got = find_options(by_page, pg, y, y_end)
            if any(g.strip() for g in got):
                new_opts = [fix_text(g) for g in got]
                if new_opts != q["options"]:
                    q["options"] = new_opts
                    rebuilt += 1

        # 3) 仍无选项的，尝试保留原值并标记
        if not any(o.strip() for o in q["options"]):
            still_empty += 1
        else:
            for k in range(4):
                if q["options"][k]:
                    old = q["options"][k]
                    q["options"][k] = fix_text(q["options"][k])
                    if q["options"][k] != old:
                        fixed_text += 1

    # 3) 重新计算 risky 标记
    SUS = re.compile(r"[&彐囹@丿亻乙》亡〇|丨]")
    for q in qs:
        incomplete = sum(1 for o in q["options"] if o.strip()) < 4
        dirty = SUS.search(q["stem"] + "".join(q["options"]))
        q["risky"] = bool(incomplete or dirty)

    risky_n = sum(1 for q in qs if q["risky"])
    print(f"题干重建: {stem_rebuilt} 道")
    print(f"选项重建: {rebuilt} 道")
    print(f"文本清洗: {fixed_text} 处")
    print(f"仍无选项: {still_empty} 道")
    print(f"剩余 risky: {risky_n} / {len(qs)}")

    if dry:
        print("\n[dry-run] 未写入文件")
        # 展示 10 道修复样本
        shown = 0
        for q in qs:
            if all(o.strip() for o in q["options"]) and shown < 10:
                print(f"  {q['id']}: {q['options'][:2]}...")
                shown += 1
        return

    # 4) 写回
    json.dump(bank, open(BANK_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    js = "window.__BANK__ = " + json.dumps(bank, ensure_ascii=False, separators=(",", ":")) + ";"
    open(BANK_JS, "w", encoding="utf-8").write(js)
    print(f"\n已写入 {BANK_JSON} ({os.path.getsize(BANK_JSON)/1024:.0f} KB)")
    print(f"已写入 {BANK_JS} ({os.path.getsize(BANK_JS)/1024:.0f} KB)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""法考真金题 PDF → OCR 文本提取器

特性：
  - RapidOCR (ONNX) 纯本地推理，不依赖网络/API
  - 自动检测双栏排版并重排（左栏读完再读右栏）
  - 页眉页脚分离
  - 跳过无题目的理论页
  - 输出 JSONL（每页一条），含置信度与坐标

用法：
  python scripts/ocr_law.py --pdf "路径.pdf" --out out.jsonl
  python scripts/ocr_law.py --pdf "路径.pdf" --out out.jsonl --start 10 --end 90
  python scripts/ocr_law.py --pdf "路径.pdf" --out out.jsonl --dpi 200 --only-questions
"""

import sys, io, os, re, json, time, argparse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pymupdf
from rapidocr_onnxruntime import RapidOCR

# ── 题目页判定关键词 ──
# 覆盖不同书的标记体系：
#   刑法系：[考点] [解析] 本题答案为
#   民法系：考点N： [解题思路] 本题的正确答案为
Q_MARKERS = (
    "[考点", "［考点", "【考点", "考点1", "考点2", "考点3", "考点4",
    "考点5", "考点6", "考点7", "考点8", "考点9",
    "[解析", "［解析", "【解析",
    "[解题思路", "［解题思路", "【解题思路", "解题思路",
    "本题答案", "正确答案为", "答案为",
    "下列说法", "下列选项", "下列哪一", "下列哪些", "下列表述",
)
NEG_MARKERS = ("目录", "前言", "序言", "后记", "版权", "图书在版编目")


def detect_columns(items, width):
    """检测双栏分栏点。返回 x 坐标，单栏返回 None。"""
    import collections
    BUCKET = 40
    bins = collections.Counter(int(i["cx"] // BUCKET) for i in items)
    if not bins:
        return None
    maxb = max(bins)

    # 找中部连续空白带
    runs, cur = [], []
    for b in range(maxb + 1):
        if bins.get(b, 0) == 0:
            cur.append(b)
        else:
            if cur:
                runs.append(cur)
                cur = []
    if cur:
        runs.append(cur)

    mid = [r for r in runs
           if r and (r[0] * BUCKET) > width * 0.25 and (r[-1] * BUCKET) < width * 0.85]
    if not mid:
        return None

    longest = max(mid, key=len)
    gap_w = (longest[-1] + 1 - longest[0]) * BUCKET
    # 空白带够宽才算双栏
    if gap_w < width * 0.06:
        return None
    return (longest[0] * BUCKET + (longest[-1] + 1) * BUCKET) / 2


def merge_lines(items, gap_ratio=0.004):
    """把同一栏内相邻的 OCR 块合并成段落。

    OCR 会把一行切成一两块，行距通常很小（页面高度的 0.5%-1.5%）。
    段落间距明显更大（约 2%-4%）。这里按页高比例动态计算阈值。
    """
    if not items:
        return []
    height = max(i["bottom"] for i in items) - min(i["top"] for i in items)
    # 行内阈值：页高的 0.6%（200dpi 下 2015px → 约 12px）
    gap_thresh = max(6, height * 0.006)

    out = []
    for i in sorted(items, key=lambda x: x["top"]):
        if out and (i["top"] - out[-1]["bottom"]) < gap_thresh:
            out[-1]["text"] += i["text"]
            out[-1]["bottom"] = max(out[-1]["bottom"], i["bottom"])
            out[-1]["score"] = min(out[-1]["score"], i["score"])
        else:
            out.append(dict(i))
    return out


def split_header_footer(items):
    """分离页眉页脚。

    页眉：位于页面顶部且单行文字（通常是书名/章节名，居中或对齐）
    页脚：页码（纯数字 1-4 位）或页面最底部 1-2 行
    判定用「与相邻块的垂直间距」而不是固定百分比，避免误切正文。
    """
    if not items:
        return [], [], []

    H = max(i["bottom"] for i in items)
    body = []
    header, footer = [], []

    # 页码：纯数字，且在最底部 8% 区域
    for i in items:
        t = i["text"].strip()
        if re.fullmatch(r"[0-9]{1,4}", t) and i["top"] > H * 0.92:
            footer.append(i)
        else:
            body.append(i)

    # 页眉：顶部 5% 区域，且与下一块有明显间距
    if body:
        body_sorted = sorted(body, key=lambda x: x["top"])
        first = body_sorted[0]
        if first["top"] < H * 0.06:
            # 找第一块之后的大间距
            if len(body_sorted) > 1:
                gap = body_sorted[1]["top"] - first["bottom"]
                if gap > H * 0.012:
                    header.append(first)
                    body = body_sorted[1:]
            else:
                header.append(first)
                body = []

    return header, body, footer


def process_page(ocr, page, tmp_path, dpi=200):
    """识别一页，返回结构化结果。"""
    pix = page.get_pixmap(dpi=dpi)
    pix.save(tmp_path)

    t0 = time.time()
    result, _ = ocr(tmp_path)
    elapsed = time.time() - t0

    if not result:
        return {"blocks": [], "left": [], "right": [], "header": [], "footer": [],
                "elapsed": elapsed, "empty": True}

    items = []
    for box, text, score in result:
        text = text.strip()
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append({
            "text": text,
            "score": float(score),
            "left": min(xs), "right": max(xs),
            "top": min(ys), "bottom": max(ys),
            "cx": (min(xs) + max(xs)) / 2,
            "cy": (min(ys) + max(ys)) / 2,
        })

    W = max(i["right"] for i in items)
    H = max(i["bottom"] for i in items)

    # 分离页眉页脚
    header, body, footer = split_header_footer(items)

    split_x = detect_columns(body, W)
    if split_x:
        left = merge_lines([i for i in body if i["cx"] < split_x])
        right = merge_lines([i for i in body if i["cx"] >= split_x])
    else:
        left = merge_lines(body)
        right = []

    return {
        "blocks": len(items),
        "left": left,
        "right": right,
        "header": header,
        "footer": footer,
        "elapsed": round(elapsed, 1),
        "two_column": bool(split_x),
        "empty": False,
    }


def is_question_page(page_data):
    """判断是否含题目。"""
    text = "".join(i["text"] for i in page_data["left"] + page_data["right"])
    if not text:
        return False

    # 排除版权页、目录页等前置页
    if any(m in text for m in NEG_MARKERS):
        # 若同时含强题目特征，仍算题目页
        strong = ("正确答案为" in text or "本题答案为" in text
                  or "解题思路" in text or "[解析" in text
                  or "[考点" in text)
        if not strong:
            return False

    # 含任一题目标记
    if any(m in text for m in Q_MARKERS):
        return True

    # 兜底：有「N.」题号 + 选项 A./B./C./D. 也算
    import re as _re
    has_no = bool(_re.search(r"(?:^|[\s\n])\d{1,3}[.、][\u4e00-\u9fff]", text))
    has_opt = bool(_re.search(r"(?:^|[\s\n])A[.、．]", text))
    return has_no and has_opt


def main():
    ap = argparse.ArgumentParser(description="法考真金题 PDF OCR 提取")
    ap.add_argument("--pdf", required=True, help="PDF 路径")
    ap.add_argument("--out", required=True, help="输出 JSONL 路径")
    ap.add_argument("--start", type=int, default=0, help="起始页（0-based）")
    ap.add_argument("--end", type=int, default=None, help="结束页（不含）")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--only-questions", action="store_true", help="只保留含题目的页")
    ap.add_argument("--resume", action="store_true", help="跳过输出文件中已有的页")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"x PDF 不存在: {pdf_path}")
        sys.exit(1)

    doc = pymupdf.open(str(pdf_path))
    total = doc.page_count
    start = max(0, args.start)
    end = min(total, args.end) if args.end else total

    # 断点续跑
    done_pages = set()
    if args.resume and os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            for line in f:
                try:
                    done_pages.add(json.loads(line)["page"])
                except Exception:
                    pass
        print(f"已处理 {len(done_pages)} 页，跳过")

    tmp = str(Path(args.out).with_suffix(".tmp.png"))

    print("=" * 60)
    print(f"PDF: {pdf_path.name}")
    print(f"总页数: {total}  处理范围: {start+1} - {end}")
    print(f"输出: {args.out}")
    print("=" * 60)

    ocr = RapidOCR()
    print("RapidOCR 已就绪\n")

    t_start = time.time()
    processed = kept = 0

    out_f = open(args.out, "a", encoding="utf-8")
    try:
        for pno in range(start, end):
            if pno in done_pages:
                continue

            page = doc[pno]
            data = process_page(ocr, page, tmp, dpi=args.dpi)
            processed += 1

            record = {
                "page": pno,
                "page_no": pno + 1,
                "two_column": data.get("two_column", False),
                "header": [i["text"] for i in data.get("header", [])],
                "footer": [i["text"] for i in data.get("footer", [])],
                "left": [{"t": i["text"], "s": round(i["score"], 2)} for i in data.get("left", [])],
                "right": [{"t": i["text"], "s": round(i["score"], 2)} for i in data.get("right", [])],
                "elapsed": data.get("elapsed", 0),
            }

            is_q = is_question_page(data)
            record["has_q"] = is_q

            if args.only_questions and not is_q:
                continue

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            kept += 1

            # 进度
            if processed % 5 == 0:
                el = time.time() - t_start
                avg = el / processed
                remain = (end - start - processed) * avg
                print(f"  页 {pno+1}/{end}  已保留 {kept}  "
                      f"均 {avg:.1f}s/页  剩余约 {remain/60:.0f} 分钟")

    finally:
        out_f.close()
        doc.close()
        if os.path.exists(tmp):
            os.remove(tmp)

    el = time.time() - t_start
    print("\n" + "=" * 60)
    print(f"完成：处理 {processed} 页，保留 {kept} 页，用时 {el/60:.1f} 分钟")
    print(f"输出：{args.out}")


if __name__ == "__main__":
    main()

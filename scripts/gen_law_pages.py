#!/usr/bin/env python3
"""为法律题库生成原书页面缩略图，供用户对照 OCR 疑点。

用法：
  python scripts/gen_law_pages.py --pdf "刑法.pdf" --pages 111,82,129 --out ../site/data/zt/law_img

输出：law_img/xf-0111.jpg 等（宽度 900px，JPEG 质量 82）
"""

import sys, io, os, argparse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pymupdf


def main():
    ap = argparse.ArgumentParser(description="生成题目原页图片")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--pages", required=True, help="页码列表（1-based，逗号分隔）或 all")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--prefix", default="xf", help="文件名前缀（科目代码）")
    ap.add_argument("--width", type=int, default=760, help="输出宽度 px")
    ap.add_argument("--quality", type=int, default=72, help="图像质量")
    ap.add_argument("--format", default="webp", choices=["webp", "jpg"],
                    help="输出格式，webp 比 jpg 小约 30%%")
    ap.add_argument("--color", action="store_true",
                    help="保留彩色；默认转灰度（书页本就黑白，可省 30%% 体积）")
    ap.add_argument("--offset", type=int, default=0,
                    help="PDF 页码 → 书印页码的偏移量（书印 = PDF - offset）。"
                         "文件名用书印页码，与题库中显示的页码一致")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    total = doc.page_count

    if args.pages.strip().lower() == "all":
        pages = list(range(1, total + 1))
    else:
        pages = []
        for seg in args.pages.split(","):
            seg = seg.strip()
            if not seg:
                continue
            if "-" in seg:
                a, b = seg.split("-", 1)
                pages.extend(range(int(a), int(b) + 1))
            else:
                pages.append(int(seg))

    os.makedirs(args.out, exist_ok=True)

    # 按宽度反推 DPI：A4 宽 595pt，目标宽度 width px
    dpi = int(args.width / (595 / 72))

    print(f"PDF: {Path(args.pdf).name} ({total} 页)")
    print(f"生成 {len(pages)} 页图片 → {args.out}（宽 {args.width}px, dpi≈{dpi}）\n")

    done = 0
    for pno in pages:
        if pno < 1 or pno > total:
            continue
        page = doc[pno - 1]
        pix = page.get_pixmap(dpi=dpi)

        # 文件名：前缀-四位书印页码（与题库 page 字段一致）
        # 优先 WebP（比 JPEG 小 30%），失败回退 JPEG
        label = pno - args.offset if args.offset else pno
        ext = args.format
        name = f"{args.prefix}-{label:04d}.{ext}"
        out_path = os.path.join(args.out, name)

        try:
            from PIL import Image
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if not args.color:
                img = img.convert("L")
            if ext == "webp":
                img.save(out_path, "WEBP", quality=args.quality, method=6)
            else:
                img.save(out_path, "JPEG", quality=args.quality, optimize=True)
        except Exception:
            # 回退：pymupdf 直接保存为 png→jpg
            fallback = os.path.join(args.out, f"{args.prefix}-{label:04d}.jpg")
            pix.save(fallback)

        done += 1
        if done % 10 == 0:
            print(f"  已生成 {done}/{len(pages)}")

    doc.close()

    # 统计体积
    total_size = sum(os.path.getsize(os.path.join(args.out, f))
                     for f in os.listdir(args.out) if f.endswith(".jpg"))
    print(f"\n[DONE] {done} 张图片，合计 {total_size/1024/1024:.1f} MB")
    print(f"  平均 {total_size/max(done,1)/1024:.0f} KB/张")


if __name__ == "__main__":
    main()

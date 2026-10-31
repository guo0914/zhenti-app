"""批量生成 8 科原书页面图片

为「有 flags 的题」和「选项可能截断的题」生成对应页面的图片，
文件名用书印页码（与题库 page 字段一致）。
"""
import json
import os
import sys
import io
import subprocess
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
OCR = os.path.join(ROOT, "..", "law_ocr")
IMG_OUT = os.path.join(ROOT, "site", "data", "zt", "law_img")

SUBJECTS = [
    ("xf",    "刑法",   "xingfa",     "真金题-刑法-柏浪涛.pdf"),
    ("mf",    "民法",   "minfa_all",  "真金题-民法-孟献贵.pdf"),
    ("msf",   "民诉法", "minsu",      "真金题-民诉法-戴鹏.pdf"),
    ("xsf",   "刑诉法", "xingsu",     "真金题-刑诉法-左宁.pdf"),
    ("xzf",   "行政法", "xingzheng",  "真金题-行政法-李佳.pdf"),
    ("sxz",   "商经知", "shangjing",  "真金题-商经知-郄鹏恩.pdf"),
    ("sgf",   "三国法", "sanguo",     "真金题-三国法-杨帆.pdf"),
    ("lilun", "理论法", "lilun",      "真金题-理论法-马峰.pdf"),
]


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def compute_offset(ocr_path):
    """从 OCR 数据推算页码偏移（书印页 = PDF页 - offset）。"""
    from collections import Counter
    import re
    diffs = Counter()
    with open(ocr_path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            for foot in (r.get("footer") or []):
                m = re.fullmatch(r"\s*(\d{1,4})\s*", str(foot))
                if m:
                    num = int(m.group(1))
                    pno = r.get("page_no", 0)
                    if 0 < num < pno:
                        diffs[pno - num] += 1
                    break
    if not diffs:
        return 0
    best, cnt = diffs.most_common(1)[0]
    if cnt < 3 or cnt / sum(diffs.values()) < 0.5:
        return 0
    return best


def main():
    os.makedirs(IMG_OUT, exist_ok=True)
    desk = os.path.join(os.path.expanduser("~"), "Desktop")

    grand = 0
    for code, name, ocr_name, pdf_name in SUBJECTS:
        law_json = os.path.join(OCR, f"law_{code}.json")
        ocr_path = os.path.join(OCR, ocr_name + ".jsonl")
        pdf_path = os.path.join(desk, pdf_name)

        if not (os.path.exists(law_json) and os.path.exists(ocr_path)):
            log("跳过 %s（数据不全）" % name)
            continue
        if not os.path.exists(pdf_path):
            log("跳过 %s（PDF 不存在）" % name)
            continue

        d = json.load(open(law_json, encoding="utf-8"))
        qs = d if isinstance(d, list) else d.get("questions", [])

        offset = compute_offset(ocr_path)

        # 需要图片的页：
        #   1. 有 flags 的题（低置信度、缺解析等）
        #   2. 选项差异过大（可能截断/污染）的题
        #   3. 题干或选项异常长/短（OCR 可疑）的题
        need = set()
        for q in qs:
            page = q.get("page")
            if not page:
                continue
            opts = [str(v).strip() for v in (q.get("options") or [])]
            suspicious = False

            if q.get("flags"):
                suspicious = True

            if not suspicious and len(opts) == 4:
                lens = [len(x) for x in opts]
                # 某个选项特别长（>150）而其他很短 → 疑似污染残留
                if max(lens) > 150 and min(lens) < 30:
                    suspicious = True
                # 选项长度差异极端（最大是最小的 4 倍以上）
                if min(lens) > 0 and max(lens) / min(lens) > 4 and max(lens) > 80:
                    suspicious = True

            if not suspicious:
                stem = str(q.get("stem") or "")
                if len(stem) > 300 or len(stem) < 25:
                    suspicious = True

            if suspicious:
                need.add(page)

        if not need:
            log("%s 无需图片" % name)
            continue

        # 页码 → PDF 页码
        pdf_pages = sorted({p + offset for p in need if p + offset >= 1})
        pages_arg = ",".join(str(p) for p in pdf_pages)

        log("生成 %s 图片：%d 页（offset=%d）" % (name, len(pdf_pages), offset))
        r = subprocess.run(
            [PY, "scripts/gen_law_pages.py",
             "--pdf", pdf_path, "--pages", pages_arg,
             "--out", IMG_OUT, "--prefix", code,
             "--offset", str(offset)],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        lines = [ln for ln in (r.stdout or "").strip().split("\n") if ln.strip()]
        for ln in lines[-3:]:
            print("   " + ln, flush=True)
        grand += len(pdf_pages)

    # 统计
    imgs = [f for f in os.listdir(IMG_OUT)
            if f.endswith(".webp") or f.endswith(".jpg")]
    size = sum(os.path.getsize(os.path.join(IMG_OUT, f)) for f in imgs)
    log("=" * 50)
    log("共生成 %d 张图片，合计 %.1f MB（平均 %d KB）"
        % (len(imgs), size / 1024 / 1024, size / max(len(imgs), 1) / 1024))
    # 按格式分类
    webp = [f for f in imgs if f.endswith(".webp")]
    jpg = [f for f in imgs if f.endswith(".jpg")]
    if webp or jpg:
        log("格式: webp %d 张, jpg %d 张" % (len(webp), len(jpg)))


if __name__ == "__main__":
    main()

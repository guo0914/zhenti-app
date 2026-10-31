"""全量重跑 8 科：解析 → 反查 → 剔除 → 质检"""
import subprocess
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
OCR = os.path.join(ROOT, "..", "law_ocr")

SUBJECTS = [
    ("xf",    "刑法",   "柏浪涛", "xingfa",      251, "真金题-刑法-柏浪涛.pdf"),
    ("mf",    "民法",   "孟献贵", "minfa_all",   261, "真金题-民法-孟献贵.pdf"),
    ("msf",   "民诉法", "戴鹏",   "minsu",       287, "真金题-民诉法-戴鹏.pdf"),
    ("xsf",   "刑诉法", "左宁",   "xingsu",      258, "真金题-刑诉法-左宁.pdf"),
    ("xzf",   "行政法", "李佳",   "xingzheng",   292, "真金题-行政法-李佳.pdf"),
    ("sxz",   "商经知", "郄鹏恩", "shangjing",   231, "真金题-商经知-郄鹏恩.pdf"),
    ("sgf",   "三国法", "杨帆",   "sanguo",      165, "真金题-三国法-杨帆.pdf"),
    ("lilun", "理论法", "马峰",   "lilun",       273, "真金题-理论法-马峰.pdf"),
]


def log(msg):
    import time
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run(cmd, title, tail=8):
    log("开始：" + title)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    lines = [ln for ln in out.strip().split("\n") if ln.strip()]
    for ln in lines[-tail:]:
        print("   " + ln, flush=True)
    return r.returncode == 0


def main():
    results = []

    for code, name, author, ocr_name, pages, _ in SUBJECTS:
        ocr_path = os.path.join(OCR, ocr_name + ".jsonl")
        if not os.path.exists(ocr_path):
            log("跳过 %s（OCR 文件不存在）" % name)
            results.append((name, "跳过", 0))
            continue

        ok = run([PY, "scripts/build_law_pipeline.py",
                  "--subject", name, "--code", code,
                  "--ocr", ocr_path, "--author", author,
                  "--pdf-pages", str(pages)],
                 "%s 完整流水线" % name, tail=14)

        # 取最终题数
        law_json = os.path.join(OCR, "law_%s.json" % code)
        n = 0
        if os.path.exists(law_json):
            import json
            d = json.load(open(law_json, encoding="utf-8"))
            n = len(d) if isinstance(d, list) else len(d.get("questions", []))
        results.append((name, "成功" if ok else "失败", n))

    log("=" * 50)
    log("汇总")
    total = 0
    for name, status, n in results:
        print("   %-8s %-6s %4d 题" % (name, status, n), flush=True)
        total += n
    print("   %-8s %-6s %4d 题" % ("合计", "", total), flush=True)

    # 打包
    inputs = [os.path.join(OCR, "law_%s.json" % c) for c, *_ in SUBJECTS]
    inputs = [p for p in inputs if os.path.exists(p)]
    if inputs:
        run([PY, "scripts/build_law_js.py", "--in"] + inputs +
            ["--out", os.path.join(ROOT, "site", "data", "zt", "law.js"),
             "--as-index"],
            "打包 law.js（%d 科）" % len(inputs), tail=16)

    log("全部完成")


if __name__ == "__main__":
    main()

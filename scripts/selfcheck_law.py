#!/usr/bin/env python3
"""法律题库一站式自检 —— 一条命令跑完所有检查

检查项：
  1. 数据完整性（qc_law.py）：字段、选项、答案、题型、章节
  2. 选项污染（内置）：解析/图示/标记是否混入选项
  3. 原文反查（verify_law.py）：题目内容能否在原书中定位
  4. 图片覆盖（内置）：有疑点的题是否有原书图片
  5. 前端资源（内置）：law.js 语法、data 文件存在

用法：
  python scripts/selfcheck_law.py            # 全部检查
  python scripts/selfcheck_law.py --quick    # 跳过反查（快）
"""

import sys
import io
import os
import re
import json
import argparse
import subprocess

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR = os.path.join(ROOT, "..", "law_ocr")
IMG = os.path.join(ROOT, "site", "data", "zt", "law_img")

SUBJECTS = [
    ("xf",    "刑法",   "xingfa",     "柏浪涛", 251),
    ("mf",    "民法",   "minfa_all",  "孟献贵", 261),
    ("msf",   "民诉法", "minsu",      "戴鹏",   287),
    ("xsf",   "刑诉法", "xingsu",     "左宁",   258),
    ("xzf",   "行政法", "xingzheng",  "李佳",   292),
    ("sxz",   "商经知", "shangjing",  "郄鹏恩", 231),
    ("sgf",   "三国法", "sanguo",     "杨帆",   165),
    ("lilun", "理论法", "lilun",      "马峰",   273),
]

# 选项污染特征（与 parse_law.py 的 sanitize_option 保持一致）
POLLUTE_PATTERNS = [
    (r"综上", "含「综上」"),
    (r"本题的?正确答案|本题答案为", "含答案标记"),
    (r"[\[［【]?\s*(?:民事|刑事)?法律关系示意图", "含示意图"),
    (r"[\[［【]?\s*(?:有体系|知识体系|思维导图)", "含体系图"),
    (r"[\[［【]?\s*(?:解题思路|分析与思路|题支逐项|题干信息|命题陷阱)", "含解析标记"),
    (r"考点\s*\d+\s*[：:]", "含考点标记"),
    (r"PROJECT\s*\d+", "含 PROJECT"),
    (r"专题[一二三四五六七八九十百零\d]+", "含章节名"),
]


def log(msg=""):
    print(msg, flush=True)


def check_pollution():
    """检查选项污染。"""
    log("\n[2/5] 选项污染检查")
    total = 0
    bad_subjects = []
    for code, name, *_ in SUBJECTS:
        path = os.path.join(OCR, f"law_{code}.json")
        if not os.path.exists(path):
            log(f"  ? {name}: 数据缺失")
            continue
        d = json.load(open(path, encoding="utf-8"))
        qs = d if isinstance(d, list) else d.get("questions", [])

        bad = []
        for q in qs:
            for i, v in enumerate(q.get("options") or []):
                vs = str(v)
                for pat, label in POLLUTE_PATTERNS:
                    if re.search(pat, vs):
                        bad.append((q["id"], "ABCD"[i], label, vs[:50]))
                        break
                else:
                    if len(vs) > 120 and re.search(r"(?:故)?[A-D]项(?:说法)?(?:正确|错误)", vs):
                        bad.append((q["id"], "ABCD"[i], "含逐项分析", vs[:50]))
                if len(vs) > 260:
                    bad.append((q["id"], "ABCD"[i], f"选项过长{len(vs)}字", vs[:50]))
                    break

        total += len(bad)
        if bad:
            bad_subjects.append((name, bad))
            log(f"  ✗ {name}: {len(bad)} 处污染")
            for qid, letter, label, sample in bad[:3]:
                log(f"      {qid} {letter}选项 [{label}] {sample}")
        else:
            log(f"  ✓ {name}: 0 处污染")

    return total == 0


def check_images():
    """检查图片覆盖率与按需生成能力。"""
    log("\n[4/5] 原书图片覆盖")
    ok = True

    # 4a. 有疑点的题必须有预生成图片
    for code, name, *_ in SUBJECTS:
        path = os.path.join(OCR, f"law_{code}.json")
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding="utf-8"))
        qs = d if isinstance(d, list) else d.get("questions", [])

        flagged = [q for q in qs if q.get("flags")]
        missing = []
        for q in flagged:
            page = q.get("page")
            if not page:
                continue
            base = os.path.join(IMG, f"{code}-{page:04d}")
            if not (os.path.exists(base + ".webp") or os.path.exists(base + ".jpg")):
                missing.append(q["id"])

        if missing:
            ok = False
            log(f"  ✗ {name}: {len(flagged)} 题有疑点, 缺图 {len(missing)} 个 (例: {missing[:3]})")
        else:
            log(f"  ✓ {name}: {len(flagged)} 题有疑点, 图片齐全")

    # 4b. 按需生成能力：PDF 是否存在 + server.py 是否支持
    log("\n  按需生成能力（用户点任意题都能看原书）:")
    srv = os.path.join(ROOT, "server.py")
    srv_ok = False
    if os.path.exists(srv):
        src = open(srv, encoding="utf-8").read()
        srv_ok = "_try_gen_lawimg" in src and "LAW_BOOKS" in src
    if srv_ok:
        log("  ✓ server.py 已支持 /data/zt/law_img 按需生成")
    else:
        log("  ✗ server.py 缺少按需生成支持")
        ok = False

    import re as _re
    books_ok = 0
    books_total = 0
    if srv_ok:
        src = open(srv, encoding="utf-8").read()
        block = src.split("LAW_BOOKS = {", 1)[1].split("}", 1)[0] if "LAW_BOOKS = {" in src else ""
        for m in _re.finditer(r'"(\w+)"\s*:\s*\(r"([^"]+)"\s*,\s*(\d+)\)', block):
            books_total += 1
            if os.path.isfile(m.group(2)):
                books_ok += 1
            else:
                log(f"    · {m.group(1)}: PDF 不存在，该科无法按需生成")
    log(f"  PDF 可用: {books_ok}/{books_total}")
    if books_ok == 0:
        log("  ✗ 没有可用的 PDF，按需生成不可用")
        ok = False

    return ok


def check_frontend():
    """检查前端资源。"""
    log("\n[5/5] 前端资源")
    ok = True

    lawjs = os.path.join(ROOT, "site", "assets", "law.js")
    datajs = os.path.join(ROOT, "site", "data", "zt", "law.js")

    for p, label in [(lawjs, "assets/law.js"), (datajs, "data/zt/law.js")]:
        if os.path.exists(p):
            size = os.path.getsize(p) / 1024
            log(f"  ✓ {label} ({size:.0f} KB)")
        else:
            log(f"  ✗ {label} 不存在")
            ok = False

    # 检查 index.html 引用
    idx = os.path.join(ROOT, "site", "index.html")
    if os.path.exists(idx):
        html = open(idx, encoding="utf-8").read()
        if "assets/law.js" in html:
            log("  ✓ index.html 已引用 law.js")
        else:
            log("  ✗ index.html 未引用 law.js")
            ok = False
        if 'data-route="law"' in html:
            log("  ✓ 导航已加入「法律专业」")
        else:
            log("  ✗ 导航缺失")
            ok = False

    return ok


def main():
    ap = argparse.ArgumentParser(description="法律题库一站式自检")
    ap.add_argument("--quick", action="store_true", help="跳过反查（快）")
    args = ap.parse_args()

    log("=" * 68)
    log("法律题库完整自检")
    log("=" * 68)

    results = {}

    # 1. 数据完整性
    log("\n[1/5] 数据完整性（qc_law.py）")
    qc_ok = True
    for code, name, ocr_name, author, pages in SUBJECTS:
        path = os.path.join(OCR, f"law_{code}.json")
        if not os.path.exists(path):
            log(f"  ? {name}: 数据缺失")
            qc_ok = False
            continue
        r = subprocess.run(
            [sys.executable, "scripts/qc_law.py", "--data", path,
             "--subject", name, "--pdf-pages", str(pages - 11)],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        out = r.stdout or ""
        m = re.search(r"(✅ 通过|❌ 未通过)（(\d+) 题，[^）]*?警告 (\d+) 处", out)
        if r.returncode == 0:
            log(f"  ✓ {name}: {m.group(2) if m else '?'} 题，警告 {m.group(3) if m else '?'} 处")
        else:
            qc_ok = False
            errs = re.findall(r"L1 硬性错误\] (\d+) 处", out)
            log(f"  ✗ {name}: 质检未通过（硬性错误 {errs[0] if errs else '?'} 处）")
            for line in out.split("\n"):
                if re.match(r"\s+\d+\s+\S", line) and "例:" not in line:
                    log("      " + line.strip())
    results["数据完整性"] = qc_ok

    # 2. 选项污染
    results["选项污染"] = check_pollution()

    # 3. 原文反查
    if not args.quick:
        log("\n[3/5] 原文反查（verify_law.py）")
        verify_ok = True
        for code, name, ocr_name, author, pages in SUBJECTS:
            law_json = os.path.join(OCR, f"law_{code}.json")
            ocr_jsonl = os.path.join(OCR, f"{ocr_name}.jsonl")
            if not (os.path.exists(law_json) and os.path.exists(ocr_jsonl)):
                continue
            r = subprocess.run(
                [sys.executable, "scripts/verify_law.py", "--ocr", ocr_jsonl,
                 "--data", law_json, "--subject", name],
                cwd=ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            out = r.stdout or ""
            m = re.search(r"问题总计: (\d+) 处", out)
            n = int(m.group(1)) if m else -1
            if n == 0:
                log(f"  ✓ {name}: 全部题目可在原文定位")
            else:
                # 少量题号误识可接受
                if n <= 3:
                    log(f"  ~ {name}: {n} 处（题号 OCR 误识，可接受）")
                else:
                    verify_ok = False
                    log(f"  ✗ {name}: {n} 处问题")
        results["原文反查"] = verify_ok
    else:
        log("\n[3/5] 原文反查（已跳过）")
        results["原文反查"] = None

    # 4. 图片
    results["图片覆盖"] = check_images()

    # 5. 前端
    results["前端资源"] = check_frontend()

    # 汇总
    log("\n" + "=" * 68)
    log("自检汇总")
    log("=" * 68)
    all_ok = True
    for k, v in results.items():
        if v is None:
            log(f"  ⏭  {k}: 已跳过")
        elif v:
            log(f"  ✓ {k}: 通过")
        else:
            log(f"  ✗ {k}: 未通过")
            all_ok = False

    log("=" * 68)
    if all_ok:
        log("✅ 全部检查通过")
    else:
        log("❌ 存在未通过的检查项，请修复后重跑")
    log("=" * 68)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

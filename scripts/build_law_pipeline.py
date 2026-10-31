#!/usr/bin/env python3
"""法律题库构建流水线 —— 一条命令完成 解析→反查→剔除→打包→质检

每一步都有自检，任一步硬性失败则中止并报错，不会产出坏数据。

用法：
  python scripts/build_law_pipeline.py --subject 刑法 --code xf ^
      --ocr ../law_ocr/xingfa.jsonl --author 柏浪涛 --pdf-pages 251

  # 多科目合并（最终构建）
  python scripts/build_law_pipeline.py --merge-only --subjects xf,mf,msf ^
      --subj-names 刑法,民法,民诉法 --out site/data/zt/law.js
"""

import sys, io, os, re, json, argparse, subprocess
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
PY = sys.executable


def run(desc, cmd, allow_fail=False):
    """执行一步并检查结果。"""
    print(f"\n{'─'*64}")
    print(f"▶ {desc}")
    print(f"{'─'*64}")
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    # 打印关键行
    for line in out.split("\n"):
        if line.strip() and not line.startswith("  File "):
            print(line)
    if r.returncode != 0 and not allow_fail:
        print(f"\n❌ 步骤失败（退出码 {r.returncode}）：{desc}")
        sys.exit(1)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="法律题库构建流水线")
    ap.add_argument("--subject", required=True, help="科目名，如 刑法")
    ap.add_argument("--code", required=True, help="科目代码，如 xf")
    ap.add_argument("--ocr", required=True, help="OCR JSONL 路径")
    ap.add_argument("--author", default="")
    ap.add_argument("--pdf-pages", type=int, default=None, help="PDF 总页数")
    ap.add_argument("--work-dir", default="../law_ocr", help="中间文件目录")
    ap.add_argument("--out-json", default=None, help="输出 zt 格式 JSON")
    ap.add_argument("--keep-flawed", action="store_true")
    ap.add_argument("--skip-qc", action="store_true", help="跳过质检（不推荐）")
    args = ap.parse_args()

    wd = Path(args.work_dir)
    wd.mkdir(parents=True, exist_ok=True)
    code = args.code
    parsed = wd / f"{code}_parsed.json"
    suspect = wd / f"suspect_{code}.json"
    out_json = Path(args.out_json) if args.out_json else wd / f"law_{code}.json"

    print("=" * 66)
    print(f"构建 {args.subject} 题库")
    print(f"  OCR: {args.ocr}")
    print(f"  输出: {out_json}")
    print("=" * 66)

    # ── 1. 解析 ──
    run("步骤1/4：结构化解析",
        [PY, "scripts/parse_law.py", "--in", args.ocr,
         "--out", str(parsed), "--subject", args.subject,
         "--author", args.author])

    # ── 2. 转 zt 格式（先不过滤，用于反查）──
    tmp_json = wd / f"{code}_all.json"
    run("步骤2/4：转换格式（含全部题，供反查）",
        [PY, "scripts/to_zt_law.py", "--in", str(parsed),
         "--out", str(tmp_json), "--subject", args.subject,
         "--keep-flawed"])

    # ── 3. 反查验证（对照原文）──
    run("步骤3/4：反查验证（题目 vs 原文）",
        [PY, "scripts/verify_law.py", "--ocr", args.ocr,
         "--data", str(tmp_json), "--subject", args.subject,
         "--dump-suspect", str(suspect)],
        allow_fail=True)   # 有可疑题是正常的，不中止

    # ── 4. 剔除 + 打包 ──
    run("步骤4/4：剔除可疑题 + 生成最终题库",
        [PY, "scripts/to_zt_law.py", "--in", str(parsed),
         "--out", str(out_json), "--subject", args.subject,
         "--suspect", str(suspect)]
        + (["--keep-flawed"] if args.keep_flawed else []))

    # ── 5. 最终质检 ──
    if not args.skip_qc:
        print(f"\n{'─'*64}")
        print("▶ 最终质检")
        print(f"{'─'*64}")
        cmd = [PY, "scripts/qc_law.py", "--data", str(out_json),
               "--subject", args.subject]
        if args.pdf_pages:
            cmd += ["--pdf-pages", str(args.pdf_pages - 11)]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        print((r.stdout or "") + (r.stderr or ""))
        if r.returncode != 0:
            print(f"\n⚠ 质检未通过，请检查后再入库")
            sys.exit(1)

    print(f"\n{'='*66}")
    print(f"✅ {args.subject} 构建完成 → {out_json}")
    print(f"{'='*66}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把分类分片的 optionHtml 同步到 guokao 分片的副本题（gk-*）。

背景：
  国考套卷（模拟 / 分模块）一律从 guokao 分片取题（papers-v5.js loadQuestions：
  qid 以 `gk-` 开头或 paperKind==='guokao' 时整卷读 guokao.json）。
  repair_option_html.py 只处理了 7 个分类分片，guokao 副本没跟上。
  于是「文字 + 内联公式图」的选项在国考卷里退化成「只有图、文字全丢」，
  例如 gk-2026xz-19526345 的选项「用45度角的正弦“”替代“1”」，
  前端只画一张 formula png，中间的符号位置和整句文字都没了。

修法：
  guokao 每题带 srcQid（= id 去掉 gk-YYYYxx- 前缀的尾号），按它反查分类分片；
  基础题有 optionHtml 而副本没有时，直接复制（图片路径是站内相对路径，通用）。
  仅在 options 长度一致时写入，避免错位。

用法：
  python scripts/sync_guokao_option_html.py --dry-run
  python scripts/sync_guokao_option_html.py --apply
"""
import argparse
import io
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

BASE_SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data"]


def load(name):
    p = os.path.join(ZT, name + ".json")
    with io.open(p, encoding="utf-8") as f:
        data = json.load(f)
    qs = data if isinstance(data, list) else data.get("questions", [])
    return p, data, qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run
    sys.stdout.reconfigure(encoding="utf-8")

    base = {}
    for name in BASE_SHARDS:
        _, _, qs = load(name)
        for q in qs:
            if q.get("optionHtml"):
                base[str(q["id"])] = q

    print("分类分片中含 optionHtml 的题: %d" % len(base))

    p, data, gk = load("guokao")
    filled = 0
    mismatch = 0
    no_base = 0
    for q in gk:
        if q.get("optionHtml"):
            continue
        src = str(q.get("srcQid") or str(q.get("id", "")).split("-", 2)[-1])
        b = base.get(src)
        if not b:
            continue
        bq = [str(x) for x in (b.get("optionHtml") or [])]
        if len(bq) != len([str(x) for x in (q.get("options") or [])]):
            mismatch += 1
            continue
        if not bq:
            no_base += 1
            continue
        if apply:
            q["optionHtml"] = bq
        filled += 1

    print("补齐 optionHtml 的 guokao 题: %d" % filled)
    print("选项数不一致而跳过: %d" % mismatch)
    print("基础分片无 optionHtml: %d（正常，说明该题选项本来就没内联图）" % no_base)

    if apply and filled:
        bak = p + ".opthtmlbak"
        if not os.path.exists(bak):
            shutil.copy2(p, bak)
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print("已写入 %s（备份 %s）" % (p, os.path.basename(bak)))
    elif not apply:
        print("\n[dry-run] 未写入。加 --apply 生效。")


if __name__ == "__main__":
    main()

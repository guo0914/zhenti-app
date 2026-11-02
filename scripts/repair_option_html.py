#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复「选项内联公式图/配图」缺陷（v2）。

背景：
  parse_zhenti.py 的 parse_block 用 strip_tags(om.group(2)) 解析选项，
  内联 <img> 被整段删掉只剩文字；optionImgs 又把图片抽成独立数组，
  丢失了图片在文本中的位置。前端「有图就只显示图」，导致选项文本被丢弃。
  典型 11789845：选项「陆地面积由大至小：甘肃广东海南浙江」三个 > 箭头全丢。

修法：
  为含 <img> 的选项生成 optionHtml（与 options 等长的数组），
  文字转义、图片重写为本地路径并保留原位。
  前端优先渲染 optionHtml，「文字 + 图片 + 位置」三者都保住。

安全校验（关键）：
  把原始选项的标签与图片剥掉后得到的纯文本，必须与库里 options[i] 一致
  （忽略空白），否则说明块边界抓错，该题跳过不写，避免写进别的题的选项。

用法：
  python scripts/repair_option_html.py --dry-run
  python scripts/repair_option_html.py --apply
"""
import argparse
import glob
import html
import io
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
CACHE = os.path.join(ROOT, "cache")

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]

# 题目块边界：## 第 N 题 / ### 第 N 题 / #### 第 N 题
Q_HEAD = re.compile(r"^#+\s*第\s*(\d+)\s*题", re.M)
MAT_HEAD = re.compile(r"^#+\s*材料\s*(\d+)", re.M)
OPTION_RE = re.compile(r"^-\s*\*\*([A-D])\*\*\.\s*(.*?)(?:\s*　✅)?\s*$", re.M)
TAG_RE = re.compile(r"<[^>]+>", re.I)
IMG_RE = re.compile(r'<img[^>]*src="([^"]+)"[^>]*>', re.I)
QID_RE = re.compile(r"qid\s*[（(]?(\d+)[）)]?")


def rewrite_img(src):
    name = os.path.basename(src)
    if "题目图" in src:
        return "assets/zt/timu/" + name
    if "公式图" in src:
        return "assets/zt/formula/" + name
    return src


def option_to_html(raw):
    """选项原始 HTML → 「转义文本 + 原位 img」的安全片段。"""
    parts = []
    pos = 0
    for m in TAG_RE.finditer(raw):
        txt = raw[pos:m.start()]
        if txt:
            parts.append(html.escape(txt, quote=False))
        tag = m.group(0)
        if tag.lower().startswith("<img"):
            mm = IMG_RE.match(tag)
            if mm:
                src = rewrite_img(mm.group(1))
                if "公式图" in src:
                    style = ("max-width:100%;height:auto;display:inline-block;"
                             "vertical-align:middle;margin:0 1px")
                else:
                    style = ("max-width:100%;height:auto;display:inline-block;"
                             "vertical-align:middle;border-radius:6px;margin:2px 3px")
                parts.append(
                    '<img src="%s" loading="lazy" style="%s" '
                    "onerror=\"this.style.display='none'\">" % (src, style)
                )
        pos = m.end()
    tail = raw[pos:]
    if tail:
        parts.append(html.escape(tail, quote=False))
    s = "".join(parts)
    return re.sub(r"\s+", " ", s).strip()


def plain(raw):
    """剥掉标签与图片，得到纯文本，用于一致性校验。"""
    s = IMG_RE.sub("", raw)
    s = TAG_RE.sub("", s)
    s = html.unescape(s)
    return re.sub(r"\s+", "", s)


def norm(s):
    return re.sub(r"\s+", "", html.unescape(str(s or "")))


def build_cache_map():
    """qid -> {A: raw, B: raw, ...}，用真正的题目块边界切分。"""
    out = {}
    for f in glob.glob(os.path.join(CACHE, "**", "*.md"), recursive=True):
        try:
            txt = io.open(f, encoding="utf-8").read()
        except Exception:
            continue
        # 所有题目块（含资料分析的 ### 第 N 题）
        heads = [m for m in Q_HEAD.finditer(txt)]
        for i, m in enumerate(heads):
            start = m.end()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(txt)
            block = txt[start:end]
            qm = QID_RE.search(block)
            if not qm:
                continue
            if "<img" not in block:
                continue
            qid = qm.group(1)
            # 只取本块的选项行（选项行都在答案/解析之前，取前 4 个字母各一次）
            found = {}
            for om in OPTION_RE.finditer(block):
                k = om.group(1)
                if k not in found:
                    found[k] = om.group(2)
            if found and qid not in out:
                out[qid] = found
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run
    sys.stdout.reconfigure(encoding="utf-8")

    cache_map = build_cache_map()
    print("缓存中含图片的题目块: %d" % len(cache_map))

    total_q = 0
    skipped = 0
    per_shard = {}
    skip_reasons = []

    for name in SHARDS:
        p = os.path.join(ZT, name + ".json")
        with io.open(p, encoding="utf-8") as f:
            data = json.load(f)
        qs = data if isinstance(data, list) else data.get("questions", [])
        changed = 0
        for q in qs:
            qid = str(q.get("id") or "")
            found = cache_map.get(qid)
            if not found:
                continue
            keys = q.get("optionKeys") or ["A", "B", "C", "D"]
            opts = q.get("options") or []
            out_html = []
            touched = False
            ok_letters = 0
            for i, k in enumerate(keys):
                raw = found.get(k, "")
                if not raw:
                    out_html.append("")
                    continue
                if "<img" not in raw:
                    out_html.append("")
                    # 无图选项不写 html，但仍参与一致性校验
                    if i < len(opts) and plain(raw) == norm(opts[i]):
                        ok_letters += 1
                    continue
                # 一致性校验：剥掉图后的文字必须与库里 options[i] 一致
                if i < len(opts) and plain(raw) != norm(opts[i]):
                    out_html.append("")
                    continue
                h = option_to_html(raw)
                out_html.append(h)
                touched = True
                ok_letters += 1
            while len(out_html) < len(opts):
                out_html.append("")
            out_html = out_html[: len(opts)]

            if not touched:
                # 仅当「缓存里确实有带图的选项」却校验不过时才记录，否则是图在题干，属正常
                if any("<img" in v for v in found.values()):
                    skipped += 1
                    if len(skip_reasons) < 12:
                        skip_reasons.append((name, qid, q.get("sub"),
                                             [plain(v) for v in found.values()][:4],
                                             [norm(o) for o in opts][:4]))
                continue

            # 至少一半字母校验通过才写，防止半对半错
            if ok_letters * 2 < len(opts):
                skipped += 1
                continue

            if apply:
                q["optionHtml"] = out_html
            changed += 1
            total_q += 1
        per_shard[name] = changed
        if apply and changed:
            shutil.copy2(p, p + ".optionhtmlbak")
            with io.open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print("\n写入 optionHtml 的题目: %d" % total_q)
    for k, v in per_shard.items():
        if v:
            print("  %-9s %d 题" % (k, v))
    print("校验不通过而跳过: %d 题" % skipped)
    if skip_reasons:
        print("\n跳过样例（缓存文本 vs 库内文本）：")
        for s in skip_reasons:
            print("  %s %s %s" % (s[0], s[1], s[2]))
            print("     cache: %s" % (" | ".join(s[3])[:150]))
            print("     db   : %s" % (" | ".join(s[4])[:150]))
    if not apply:
        print("\n[dry-run] 未写入。加 --apply 生效。")


if __name__ == "__main__":
    main()

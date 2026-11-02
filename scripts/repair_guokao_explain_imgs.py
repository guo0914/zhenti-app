# -*- coding: utf-8 -*-
"""从 guokao_cache 原始 md 还原 guokao explain 里的 [图] 占位为真实图片。

源仓库用 <img flag="tex" src="../90-图片/公式图/xxx.png" /> 表示公式/图形，
fetch_guokao.py 的 clean_rich() 把它替换成 [图] 占位，导致解析里的公式图
全部变成字面「[图]」。本脚本按 qid 找回原始 md 的解析段，把 [图] 还原为
markdown 图片语法（与 parse_zhenti.py 的 explain_with_formulas 一致）。

用法：
  python scripts/repair_guokao_explain_imgs.py --dry-run
  python scripts/repair_guokao_explain_imgs.py --apply
"""
import argparse
import glob
import html
import io
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "..", "law_ocr", "guokao_cache")
TARGET = os.path.join(ROOT, "site", "data", "zt", "guokao.json")

HEAD = re.compile(r"^#{1,4}\s*第\s*(\d+)\s*题", re.M)
QID = re.compile(r"qid\s*[（(]?(\d+)[）)]?")
EXPL = re.compile(r"^\*\*(?:官方解析|解析)\*\*[：:]?\s*$", re.M)
ANS = re.compile(r"^\*\*答案\*\*", re.M)
OPT = re.compile(r"^-\s*\*\*[A-D]\*\*\.", re.M)
IMG = re.compile(r'<img[^>]*src="([^"]+)"[^>]*>', re.I)
# 只剥真正的 HTML 标签，不能用 <[^>]+>（会把「r<0，则…」这类数学文本当标签吃掉）
TAG = re.compile(r"</?(?:p|div|u|span|br|strong|b|em|sub|sup|img)\b[^>]*>", re.I)
MD_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
NEXT_HEAD = re.compile(r"^#{1,4}\s", re.M)


def norm(s):
    """去掉所有空白、图片（HTML 与 markdown）与占位，用于一致性校验。"""
    s = MD_IMG.sub("", s)
    s = s.replace("[图]", "")
    s = TAG.sub("", s)
    s = html.unescape(s)
    return re.sub(r"\s+", "", s)


def img_to_md(src):
    """把源仓库图片路径映射成本地 markdown 图片语法。"""
    base = os.path.basename(src)
    if "公式图" in src:
        sub, alt = "公式图", "公式"
    elif "题目图" in src:
        sub, alt = "题目图", "图"
    else:
        return ""
    return "\n![%s](assets/zt/%s/%s)\n" % (alt, sub, base)


def expl_to_md(raw):
    """原始解析段 → 保留图片位置的 markdown 文本。"""
    # 先把图片换成占位符，避免被后面的标签清理吃掉
    tokens = []

    def repl(m):
        md = img_to_md(m.group(1))
        if not md:
            return ""
        tokens.append(md)
        return "\u0000%d\u0000" % (len(tokens) - 1)

    tmp = IMG.sub(repl, raw)
    tmp = re.sub(r"<br\s*/?>", "\n", tmp, flags=re.I)
    tmp = re.sub(r"</p>\s*<p[^>]*>", "\n", tmp, flags=re.I)
    tmp = TAG.sub("", tmp)
    tmp = html.unescape(tmp)
    tmp = re.sub(r"[ \t\u3000]+", " ", tmp)
    tmp = re.sub(r"\n{3,}", "\n\n", tmp)
    for i, md in enumerate(tokens):
        tmp = tmp.replace("\u0000%d\u0000" % i, md)
    return re.sub(r"\n{3,}", "\n\n", tmp).strip()


def build_cache_map():
    """qid -> 候选解析段原文列表（同一 qid 可能出现在多个 md 里，内容略有差异）。"""
    out = {}
    for p in glob.glob(os.path.join(CACHE_DIR, "*.md")):
        txt = io.open(p, encoding="utf-8", errors="replace").read()
        heads = list(HEAD.finditer(txt))
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(txt)
            block = txt[h.start():end]
            qm = QID.search(block)
            if not qm:
                continue
            qid = qm.group(1)
            em = EXPL.search(block)
            if not em:
                continue
            expl = block[em.end():]
            # 解析段到选项/答案/分隔线/下一个标题为止
            stop = len(expl)
            for pat in (OPT, ANS):
                mm = pat.search(expl)
                if mm:
                    stop = min(stop, mm.start())
            nh = NEXT_HEAD.search(expl)
            if nh:
                stop = min(stop, nh.start())
            expl = expl[:stop]
            expl = re.sub(r"^\s*-{3,}\s*$", "", expl, flags=re.M)
            if expl.strip():
                out.setdefault(qid, []).append(expl)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        ap.error("需要 --dry-run 或 --apply")

    cache = build_cache_map()
    lines = ["cache 覆盖 qid: %d" % len(cache)]

    data = json.load(io.open(TARGET, encoding="utf-8"))
    qs = data if isinstance(data, list) else data.get("questions", [])

    stats = {"fixed": 0, "fixed_fallback": 0, "skip_nomatch": 0, "skip_noqid": 0, "skip_nocache": 0, "skip_noph": 0}
    samples = []
    for q in qs:
        e = q.get("explain") or ""
        if "[图]" not in e:
            stats["skip_noph"] += 1
            continue
        m = re.search(r"-(\d+)$", str(q.get("id")))
        if not m:
            stats["skip_noqid"] += 1
            continue
        qid = m.group(1)
        cands = cache.get(qid)
        if not cands:
            stats["skip_nocache"] += 1
            continue
        new = None
        for raw in cands:
            cand = expl_to_md(raw)
            # 一致性校验：去掉图片占位后文本必须一致
            if norm(cand) == norm(e):
                new = cand
                break
        if new is None:
            # 兜底：库文本本身正确，只是 [图] 没还原成图片。
            # 仅当源 md 解析段里只出现同一种图片、且数量与 [图] 个数一致时才替换，
            # 避免把不同图片错配进去。
            distinct = []
            for raw in cands:
                for mm in IMG.finditer(raw):
                    md = img_to_md(mm.group(1))
                    if md and md.strip() not in distinct:
                        distinct.append(md.strip())
            n_ph = e.count("[图]")
            if len(distinct) == 1 and n_ph > 0:
                fill = "\n" + distinct[0] + "\n"
                q["explain"] = e.replace("[图]", fill)
                stats["fixed_fallback"] += 1
                continue
            stats["skip_nomatch"] += 1
            if len(samples) < 6:
                a = norm(expl_to_md(cands[0]))[:60]
                b = norm(e)[:60]
                samples.append("  %s\n    源: %s\n    库: %s" % (q.get("id"), a, b))
            continue
        q["explain"] = new
        stats["fixed"] += 1

    lines.append("结果: %s" % stats)
    if samples:
        lines.append("不匹配样例:")
        lines.extend(samples)

    if args.apply:
        bak = TARGET + ".explbak"
        if not os.path.exists(bak):
            shutil.copy2(TARGET, bak)
            lines.append("已备份 %s" % os.path.basename(bak))
        with io.open(TARGET, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        lines.append("已写入 %s" % TARGET)
    else:
        lines.append("[DRY-RUN] 未写入")

    with io.open(os.path.join(ROOT, "_gkrep.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("report -> _gkrep.txt")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""还原 7 个基分片 explain 里被丢掉的「题目图」。

根因：parse_zhenti.py 的 FORMULA_IMG 只匹配 `src="...公式图/..."` 的图片，
解析段里的「题目图」（如定义判断里的符号对照图、图形推理里的参考图）
被 strip_tags 一起剥掉，只剩「右边数位从大到小依次为」这种断句。
guokao 分片是后来用 repair_guokao_explain_imgs.py 从原始 md 补回来的，
7 个基分片（politics/common/verbal/quantity/judge/graph/data）从未补过。

做法：从 quiz-app/cache/<模块>/*.md 找回每题的「**官方解析**」原始 HTML，
把所有 <img>（题目图 + 公式图）按原位置转成 markdown 图片语法，
与库里现有 explain 做「去图去空白」文本比对，一致才替换 —— 保证不会错配。

用法：
  python scripts/repair_zhenti_explain_imgs.py --dry-run
  python scripts/repair_zhenti_explain_imgs.py --apply
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
CACHE = os.path.join(ROOT, "cache")
ZT = os.path.join(ROOT, "site", "data", "zt")

CATS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data"]

# 「## 第 N 题　<sub>qid 123 · 图形推理</sub>」与资料分析的「### 第 N 题」
HEAD = re.compile(r"^#{2,3}\s*第\s*(\d+)\s*题\s*[　\s]*<sub>qid\s*(\d+)\s*·\s*([^<]*)</sub>", re.M)
EXPL = re.compile(r"\*\*官方解析\*\*\s*\n")
IMG = re.compile(r'<img[^>]*src="([^"]+)"[^>]*>', re.I)
# 只剥真正的 HTML 标签，不能用 <[^>]+>（会把「r<0，则…」当标签吃掉）
TAG = re.compile(r"</?(?:p|div|u|span|br|strong|b|em|sub|sup|img|font|table|tr|td|th|tbody|thead)\b[^>]*>", re.I)
MD_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def norm(s):
    """去图片、去标签、去填空横线、去空白，用于一致性校验。

    注意：库里的 explain 是 parse_zhenti.py 早期产物，其中的填空横线
    （原始 md 的连续 \\xa0）已被压成空串，只剩「（）」；而本脚本按
    现行规则还原成「____」。若不把 ____ 也归一化掉，这批题会被误判
    成「文本不一致」而漏修（quantity 曾因此漏 34 题）。
    """
    s = MD_IMG.sub("", s or "")
    s = TAG.sub("", s)
    s = s.replace("____", "")
    s = html.unescape(s)
    return re.sub(r"\s+", "", s)


def img_to_md(src):
    base = os.path.basename(src)
    if "公式图" in src:
        return "\n![公式](assets/zt/公式图/%s)\n" % base
    if "题目图" in src:
        return "\n![图](assets/zt/题目图/%s)\n" % base
    return ""


def expl_to_md(raw):
    """原始解析段 → 保留全部图片位置的 markdown 文本。"""
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
    # 与 parse_zhenti.py 的 strip_tags 保持一致：\xa0 连续 → 填空横线
    tmp = re.sub(r"\xa0{2,}", "____", tmp)
    tmp = re.sub(r"(?:\xa0 ?){2,}", "____", tmp)
    tmp = tmp.replace("\xa0", " ")
    tmp = re.sub(r"[ \t\u3000]+", " ", tmp)
    tmp = re.sub(r"\n{3,}", "\n\n", tmp)
    for i, md in enumerate(tokens):
        tmp = tmp.replace("\u0000%d\u0000" % i, md)
    tmp = re.sub(r"\n{3,}", "\n\n", tmp)
    return tmp.strip()


def build_cache_map():
    """qid -> 候选解析段原文列表。"""
    out = {}
    for p in glob.glob(os.path.join(CACHE, "*", "*.md")):
        txt = io.open(p, encoding="utf-8", errors="replace").read()
        heads = list(HEAD.finditer(txt))
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(txt)
            block = txt[h.start():end]
            qid = h.group(2)
            em = EXPL.search(block)
            if not em:
                continue
            expl = block[em.end():]
            # 截掉尾部 --- 分隔线与下一个标题
            expl = re.split(r"^\s*-{3,}\s*$", expl, flags=re.M)[0]
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
    total = {"fixed": 0, "skip_same": 0, "skip_nomatch": 0, "skip_nocache": 0}
    samples = []

    for cat in CATS:
        fp = os.path.join(ZT, cat + ".json")
        data = json.load(io.open(fp, encoding="utf-8"))
        st = {"fixed": 0, "skip_same": 0, "skip_nomatch": 0, "skip_nocache": 0}
        for q in data:
            qid = str(q.get("id") or "")
            e = q.get("explain") or ""
            if not e:
                continue
            cands = cache.get(qid)
            if not cands:
                st["skip_nocache"] += 1
                continue
            new = None
            for raw in cands:
                cand = expl_to_md(raw)
                if norm(cand) == norm(e):
                    new = cand
                    break
            if new is None:
                st["skip_nomatch"] += 1
                if len(samples) < 8:
                    samples.append("  %s/%s\n    源: %s\n    库: %s" % (
                        cat, qid, norm(expl_to_md(cands[0]))[:70], norm(e)[:70]))
                continue
            # 已一致（图片数量没变）就跳过，避免无意义重写
            if new.count("![") <= e.count("!["):
                st["skip_same"] += 1
                continue
            if args.apply:
                q["explain"] = new
            st["fixed"] += 1

        for k in st:
            total[k] += st[k]
        lines.append("%-9s fixed=%3d same=%3d nomatch=%3d nocache=%3d" % (
            cat, st["fixed"], st["skip_same"], st["skip_nomatch"], st["skip_nocache"]))
        if args.apply and st["fixed"]:
            bak = fp + ".explimgbak"
            if not os.path.exists(bak):
                shutil.copy2(fp, bak)
            with io.open(fp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            lines.append("        已写入 %s.json" % cat)

    lines.append("合计: %s" % total)
    if samples:
        lines.append("不匹配样例（前 8 条）:")
        lines.extend(samples)
    if not args.apply:
        lines.append("[DRY-RUN] 未写入")

    with io.open(os.path.join(ROOT, "_ztexpl.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("report -> _ztexpl.txt")


if __name__ == "__main__":
    main()

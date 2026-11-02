# -*- coding: utf-8 -*-
"""
修复「题干内联公式图/配图被抽走、位置丢失」。

根因
----
parse_zhenti.py 把题干里的 <img> 全部抽到 imgs 数组，题干只剩文字。
对于「数列题」这类题目，题干里的数字本身就是公式图：

    <p><img 1/4>，<img 2/4>，<img 3/4>，<img 4/4>，（    ）</p>

入库后 stem 变成 "，，，，（ ）"，四张数字图被塞到 imgs，
前端在题干下方竖排显示 —— 数字与逗号的位置关系彻底丢失，
题目无法作答。

修复
----
新增字段 stemHtml（字符串），保存「转义文字 + 原位图片」的完整题干。
只处理同时满足以下条件的题：
  1. 题干在缓存里是单个 <p> 段落（避免多段落拼接产生歧义）
  2. 该段落含 <img> 且去掉图后仍有非空文字
  3. 剥掉标签和图片后的纯文本，与入库的 stem 完全一致（去空白）
  4. imgs 里的每一张图都能在这个段落里找到（不遗漏块级配图）

不满足条件的一律跳过，保持原有 stem + imgs 渲染路径不变。

用法
----
  python scripts/fix_stem_inline_html.py --dry-run
  python scripts/fix_stem_inline_html.py --apply
"""
import io
import json
import os
import re
import shutil
import sys
import html

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
CACHE = os.path.join(ROOT, "cache")

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]

Q_HEAD = re.compile(r"^#+\s*第\s*(\d+)\s*题", re.M)
QID_RE = re.compile(r"qid\s*[（(]?(\d+)[）)]?")
OPT_LINE = re.compile(r"^-\s*\*\*[A-D]\*\*\.", re.M)
TAG_RE = re.compile(r"<[^>]+>", re.I)
IMG_RE = re.compile(r'<img[^>]*src="([^"]+)"[^>]*>', re.I)
P_ONLY = re.compile(r"^\s*<p>(.*?)</p>\s*$", re.S)


def rewrite_img(src):
    name = os.path.basename(src)
    if "题目图" in src:
        return "assets/zt/timu/" + name
    if "公式图" in src:
        return "assets/zt/formula/" + name
    return src


def stem_to_html(raw):
    """题干段落 → 「转义文本 + 原位 img」。

    连续 \\xa0（不间断空格）是原文里画横线占位符，
    parse_zhenti.py 已把它还原成 ____，这里保持一致，
    否则纯文本校验会对不上。
    """
    # 括号里的连续 nbsp 是「答题括号」（ ）占位，不是填空横线，
    # parse_zhenti.py 把它保留成 "（ ）"，这里保持一致，
    # 否则题干里会多出一个 ____，与其它题目不一致。
    raw = re.sub(r"（[ \t\xa0]*）", "（ ）", raw)
    raw = re.sub(r"\xa0{2,}", "____", raw)
    raw = re.sub(r"(?:\xa0 ?){2,}", "____", raw)
    raw = raw.replace("\xa0", " ")
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
                    # 公式图（含数列数字）必须按原始尺寸内联，不能被拉伸
                    style = ("height:auto;max-width:none;width:auto;"
                             "vertical-align:middle;display:inline-block;margin:0 2px")
                else:
                    style = ("max-width:100%;height:auto;display:inline-block;"
                             "vertical-align:middle;border-radius:6px;margin:2px 4px")
                parts.append(
                    '<img src="%s" loading="lazy" style="%s" '
                    "onerror=\"this.style.display='none'\">" % (src, style)
                )
        pos = m.end()
    tail = raw[pos:]
    if tail:
        parts.append(html.escape(tail, quote=False))
    s = "".join(parts)
    # 连续空白压成一个空格，但保留全角空格以外的语义
    return re.sub(r"[ \t\r\n]+", " ", s).strip()


def plain_of(raw):
    """剥掉标签与图片得纯文本，用于与入库 stem 比对。"""
    raw = re.sub(r"（[ \t\xa0]*）", "（ ）", raw)
    raw = re.sub(r"\xa0{2,}", "____", raw)
    raw = re.sub(r"(?:\xa0 ?){2,}", "____", raw)
    s = IMG_RE.sub("", raw)
    s = TAG_RE.sub("", s)
    s = html.unescape(s)
    return re.sub(r"\s+", "", s)


def plain_variants(raw):
    """纯文本的两种口径。

    缓存里「（\\xa0\\xa0\\xa0\\xa0）」这种答题括号内的空格，
    parse_zhenti.py 保留成了「（ ）」而不是「（____）」，
    所以比对时要同时接受「nbsp 当空格」和「nbsp 当横线」两种结果。
    """
    a = plain_of(raw)
    b = IMG_RE.sub("", raw)
    b = re.sub(r"（[ \t\xa0]*）", "（ ）", b)
    b = re.sub(r"\xa0{2,}", "____", b)
    b = re.sub(r"(?:\xa0 ?){2,}", "____", b)
    b = b.replace("\xa0", " ")
    b = TAG_RE.sub("", b)
    b = html.unescape(b)
    b = re.sub(r"\s+", "", b)
    c = IMG_RE.sub("", raw)
    c = c.replace("\xa0", " ")
    c = TAG_RE.sub("", c)
    c = html.unescape(c)
    c = re.sub(r"\s+", "", c)
    return {a, b, c}


def norm(s):
    return re.sub(r"\s+", "", html.unescape(str(s or "")))


def build_cache_map():
    """qid -> 题干段落原文（只收单个 <p> 包裹的段落）。"""
    out = {}
    for root, _dirs, files in os.walk(CACHE):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(root, fn)
            try:
                t = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for m in Q_HEAD.finditer(t):
                nxt = t.find("\n#", m.end())
                blk = t[m.start(): nxt if nxt > 0 else len(t)]
                qm = QID_RE.search(blk)
                if not qm:
                    continue
                body = blk[blk.find("\n") + 1:]
                om = OPT_LINE.search(body)
                stempart = body[:om.start()] if om else body
                stempart = stempart.strip()
                if not stempart or not IMG_RE.search(stempart):
                    continue
                pm = P_ONLY.match(stempart)
                if not pm:
                    # 多个段落 / 带材料 —— 不处理，避免拼接歧义
                    continue
                inner = pm.group(1)
                if not plain_of(inner):
                    continue
                qid = qm.group(1)
                if qid not in out:
                    out[qid] = inner
    return out


def load_shard(name):
    p = os.path.join(ZT, name + ".json")
    d = json.load(io.open(p, encoding="utf-8"))
    if isinstance(d, list):
        return d, p
    return d.get("questions", []), p


def main():
    apply = "--apply" in sys.argv
    cache_map = build_cache_map()
    print("缓存中「单段落 + 含图 + 有文字」的题干: %d 题" % len(cache_map))

    stats = {}
    skipped = []
    written = 0
    for name in SHARDS:
        qs, path = load_shard(name)
        changed = 0
        for q in qs:
            sid = str(q.get("id"))
            base = sid.split("-")[-1]
            inner = cache_map.get(base)
            if not inner:
                continue
            html_src = stem_to_html(inner)
            plain = plain_of(inner)
            if norm(q.get("stem")) not in plain_variants(inner):
                skipped.append((name, sid, "文本不一致", plain[:20], norm(q.get("stem"))[:20]))
                continue
            imgs = [x for x in (q.get("imgs") or []) if x]
            inline_names = set(os.path.basename(rewrite_img(s)) for s in IMG_RE.findall(inner))
            extra = [i for i in imgs if os.path.basename(i) not in inline_names]
            if extra:
                skipped.append((name, sid, "imgs 有额外图 %d 张" % len(extra), "", ""))
                continue
            if not any("formula" in s or "公式图" in s for s in IMG_RE.findall(inner)) \
                    and len(IMG_RE.findall(inner)) < 1:
                continue
            # 关键判据：第一张图片后面必须还有文字，才是「内联」图。
            # 图形推理的块级配图是 <p>引导语</p><p><img></p>，图后什么都没有，
            # 保持原有「题干下方整块显示」的排版，不要改成内联。
            # 注意不能用「最后一张图后必须有文字」：数列题可能把最后一项
            # 放在括号之后（<img>，<img>，<img>，<img>，（ ），<img>），
            # 末尾那张图后面本来就没有文字，用最后一个判据会把整题漏掉。
            first = list(IMG_RE.finditer(inner))
            tail_txt = inner[first[0].end():] if first else ""
            if not plain_of(tail_txt):
                skipped.append((name, sid, "图后无文字（块级配图）", "", ""))
                continue
            q["stemHtml"] = html_src
            changed += 1
            written += 1
        if changed:
            stats[name] = changed
            if apply:
                shutil.copy2(path, path + ".stemhtmlbak")
                with io.open(path, "w", encoding="utf-8") as f:
                    json.dump(qs, f, ensure_ascii=False, separators=(",", ":"))

    print("\n分片写入:", stats if stats else "无")
    print("合计写入: %d 题" % written)
    print("跳过: %d 题" % len(skipped))
    for x in skipped[:20]:
        print("   [%s] %s %s %s | %s" % x)
    if not apply:
        print("\n[dry-run] 未写入。加 --apply 生效。")


if __name__ == "__main__":
    main()

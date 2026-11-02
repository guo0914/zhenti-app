# -*- coding: utf-8 -*-
"""
修复选项里的 <u>画线</u> 标记被剥掉的问题。

背景：
源 markdown 里有些选项用 <u>...</u> 标注「画线部分」（如题干要求
「下列画线的动词属于非叙实动词的是」）。parse_zhenti.py 的 strip_tags
把标签整段删掉，画线信息彻底丢失，题目无法作答。

做法：
从 cache/**/*.md 按 qid 定位题目块，取原始选项行，把 <u>X</u> 转成
<span style="text-decoration:underline">X</span>，其余标签剥离，
生成 optionHtml（与 options 等长的数组）写回分片。
一致性校验：纯文本剥标签后必须与现有 options[i] 完全一致，否则跳过。

用法：
  python scripts/fix_underline_options.py --dry-run
  python scripts/fix_underline_options.py --apply
"""
import io
import os
import re
import sys
import json
import html
import glob
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

Q_HEAD = re.compile(r"^#+\s*第\s*(\d+)\s*题", re.M)
QID_RE = re.compile(r"qid\s*[（(]?(\d+)[）)]?")
OPT_LINE = re.compile(r"^-\s*\*\*([A-D])\*\*\.\s*(.*)$", re.M)

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]


def load(name):
    p = os.path.join(ZT, name + ".json")
    with io.open(p, encoding="utf-8") as f:
        d = json.load(f)
    return d, (d if isinstance(d, list) else d.get("questions", []))


def norm(s):
    return re.sub(r"\s+", "", str(s or ""))


# 源 markdown 在正确选项行末尾加的标记（✅ / ✔ / 对）
ANSWER_MARK = re.compile(r"[✅✔☑√]+\s*$")


def strip_mark(t):
    """去掉正确选项行末尾的 ✅ 标记与首尾空白。"""
    t = t.replace("\u3000", " ")
    t = ANSWER_MARK.sub("", t)
    return t.strip()


def plain_of(raw):
    """剥掉所有标签与图片，得到纯文本，用于一致性校验。"""
    t = strip_mark(raw)
    t = re.sub(r"<img[^>]*>", "", t)
    t = re.sub(r"<br\s*/?>", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    return norm(html.unescape(t))


def to_html(raw):
    """<u>X</u> -> 下划线 span；其余标签剥离；文字转义。"""
    t = strip_mark(raw)
    # 统一 br 与段落
    t = re.sub(r"<br\s*/?>", " ", t)
    t = re.sub(r"</(p|div)>", " ", t)
    # 下划线先转成占位，避免后续 <[^>]+> 把它吃掉
    t = re.sub(r"<u\b[^>]*>(.*?)</u>", lambda m: "\x01" + m.group(1) + "\x02", t, flags=re.S | re.I)
    # 其余标签剥离
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    # 占位还原为下划线 span（内容再次转义）
    def repl(m):
        inner = html.escape(m.group(1), quote=False)
        return ('<span style="text-decoration:underline;text-decoration-thickness:2px;'
                'text-underline-offset:3px;text-decoration-color:#e0405a">'
                + inner + '</span>')
    t = re.sub("\x01(.*?)\x02", repl, t, flags=re.S)
    return t


def build_cache_map():
    """qid -> {A: raw, B: raw, ...}"""
    out = {}
    files = glob.glob(os.path.join(ROOT, "cache", "**", "*.md"), recursive=True)
    for p in files:
        try:
            t = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if "<u>" not in t:
            continue
        blocks = Q_HEAD.split(t)
        # Q_HEAD.split 结果是 [pre, no1, body1, no2, body2, ...]
        for i in range(1, len(blocks) - 1, 2):
            body = blocks[i + 1]
            m = QID_RE.search(body)
            if not m:
                continue
            qid = m.group(1)
            opts = {}
            for om in OPT_LINE.finditer(body):
                opts[om.group(1)] = om.group(2)
            if opts:
                out[qid] = opts
    return out


def main():
    apply = "--apply" in sys.argv
    cmap = build_cache_map()
    print("cache 中带 <u> 的题块: %d" % len(cmap))

    changed_total = 0
    skipped = 0
    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        data, qs = load(name)
        hit = 0
        for q in qs:
            qid = str(q.get("id", "")).split("-")[-1]
            if qid not in cmap:
                continue
            opts = list(q.get("options") or [])
            if not opts:
                continue
            src = cmap[qid]
            letters = ["A", "B", "C", "D"]
            built = []
            ok = True
            for idx in range(len(opts)):
                letter = letters[idx] if idx < len(letters) else None
                raw = src.get(letter) if letter else None
                if raw is None:
                    ok = False
                    break
                if plain_of(raw) != norm(opts[idx]):
                    ok = False
                    break
                built.append(to_html(raw))
            if not ok:
                skipped += 1
                print("  [跳过] %s %s 文本不一致" % (name, q.get("id")))
                continue
            # 必须真的含下划线，否则不写
            if not any("text-decoration:underline" in b for b in built):
                continue
            if apply:
                q["optionHtml"] = built
            hit += 1
            changed_total += 1
            print("  %s %s -> %s" % (name, q.get("id"), [b[:60] for b in built]))

        if apply and hit:
            bak = path + ".ubak"
            if not os.path.exists(bak):
                shutil.copy2(path, bak)
            payload = data
            with io.open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            print("  写入 %s (备份 .ubak)" % os.path.basename(path))

    print("\n合计写入 %d 个题对象，跳过 %d" % (changed_total, skipped))
    if not apply:
        print("（dry-run，未写盘）")


if __name__ == "__main__":
    main()

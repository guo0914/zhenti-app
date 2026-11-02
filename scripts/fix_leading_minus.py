# -*- coding: utf-8 -*-
"""
修复「数列题题干开头的负号被删掉」。

根因
----
parse_zhenti.py 的 parse_block 里有：

    stem = stem.strip("- \n")

对数列题「-3，-1，2，7，14，（ ）」这种以负号开头的题干，
strip("-") 会把开头的负号一起剥掉，入库后变成「3，-1，2，7，14，（ ）」，
数列完全变了，正确答案也随之错误。

修复
----
从 cache/**/*.md 取原始题干，只对「缓存题干以 - 开头、入库题干不以 - 开头、
其余部分完全一致」的题，把负号补回去。

用法
----
  python scripts/fix_leading_minus.py --dry-run
  python scripts/fix_leading_minus.py --apply
"""
import io
import json
import os
import re
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
CACHE = os.path.join(ROOT, "cache")

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]

Q_HEAD = re.compile(r"^#+\s*第\s*(\d+)\s*题", re.M)
QID_RE = re.compile(r"qid\s*[（(]?(\d+)[）)]?")
OPT_LINE = re.compile(r"^-\s*\*\*[A-D]\*\*\.", re.M)
IMG_RE = re.compile(r"<img[^>]*>", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def plain(raw):
    raw = re.sub(r"（[ \t\xa0]*）", "（ ）", raw)
    raw = re.sub(r"\xa0{2,}", "____", raw)
    raw = re.sub(r"(?:\xa0 ?){2,}", "____", raw)
    raw = raw.replace("\xa0", " ")
    raw = IMG_RE.sub("", raw)
    raw = TAG_RE.sub("", raw)
    return re.sub(r"\s+", "", raw)


def norm(s):
    return re.sub(r"\s+", "", str(s or ""))


def build_cache_map():
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
                s = plain(stempart)
                if not s.startswith("-"):
                    continue
                if qm.group(1) not in out:
                    out[qm.group(1)] = s
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
    print("缓存中「题干以负号开头」的题: %d" % len(cache_map))

    fixed = []
    for name in SHARDS:
        qs, path = load_shard(name)
        changed = 0
        for q in qs:
            sid = str(q.get("id"))
            base = sid.split("-")[-1]
            want = cache_map.get(base)
            if not want:
                continue
            have = norm(q.get("stem"))
            if have.startswith("-"):
                continue
            if norm("-" + have) != want:
                continue
            q["stem"] = "-" + str(q.get("stem") or "").lstrip()
            sh = q.get("stemHtml")
            if sh:
                q["stemHtml"] = "-" + str(sh).lstrip()
            changed += 1
            fixed.append((name, sid, have[:26]))
        if changed and apply:
            shutil.copy2(path, path + ".minusbak")
            with io.open(path, "w", encoding="utf-8") as f:
                json.dump(qs, f, ensure_ascii=False, separators=(",", ":"))

    print("\n修复 %d 题:" % len(fixed))
    for x in fixed:
        print("   [%s] %s  %s" % x)
    if not apply:
        print("\n[dry-run] 未写入。加 --apply 生效。")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""一次性：扫描所有分片 options 里的裸 HTML 标签，并判断渲染时会不会露出字面标签。

前端 papers-v5.js / zhenti-v5.js 的优先级：
  optionHtml[i] 非空 -> 直接注入（保留文字+原位图）
  否则 optionImgs[i] -> 渲染图片
  否则 text 含「缺失」-> 缺失提示
  否则 text 非空 -> esc(text) 转义显示（此时 <p> 会以字面形式出现）
"""
import json, io, sys, re, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>")
CATS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]

def load(n):
    d = json.load(io.open("site/data/zt/%s.json" % n, encoding="utf-8"))
    return d if isinstance(d, list) else d.get("questions", [])

leak_q = []
tag_counter = collections.Counter()
for n in CATS:
    for q in load(n):
        opts = q.get("options") or []
        oh = q.get("optionHtml") or []
        oi = q.get("optionImgs") or []
        for i, o in enumerate(opts):
            s = str(o or "")
            found = TAG.findall(s)
            if not found:
                continue
            for t in found:
                tag_counter[t.lower()] += 1
            cell = str(oh[i] if i < len(oh) else "").strip()
            img = str(oi[i] if i < len(oi) else "").strip()
            if cell or img:
                continue          # 会被 optionHtml / 图片覆盖，不露出
            leak_q.append((n, q["id"], i, s))

print("=== 会露出字面 HTML 标签的选项 ===")
for x in leak_q:
    print("%-9s %-22s [%d] %r" % x[:3] + (" %r" % x[3],))
print("受影响题:", len(set((x[0], x[1]) for x in leak_q)), " 选项数:", len(leak_q))
print("标签频次:", dict(tag_counter))

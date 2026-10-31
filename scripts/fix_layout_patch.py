"""修正上一脚本误改的 .q-card 规则"""
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "site", "assets", "style.css")
s = open(CSS, encoding="utf-8").read()

# 1) 修掉误加的 max-width:100vw（加在了 .practice > .q-card 上）
s = s.replace(
    ".practice > .q-card{display:table-cell;vertical-align:top;"
    "padding-right:16px;width:auto;max-width:100vw}",
    ".practice > .q-card{display:table-cell;vertical-align:top;"
    "padding-right:16px;width:auto}")

# 2) 修掉 .q-body 重复的 max-width
s = s.replace(
    ".q-body{padding:16px 18px;min-width:0;overflow-wrap:break-word;"
    "width:100%;max-width:100%;box-sizing:border-box;max-width:100%}",
    ".q-body{padding:16px 18px;min-width:0;overflow-wrap:break-word;"
    "width:100%;max-width:100%;box-sizing:border-box}")

# 3) 给独立 .q-card 规则加硬上限（真正需要的地方）
old = ".q-card{background:var(--card);border:1px solid var(--line-2);"
new = ".q-card{max-width:100vw;background:var(--card);border:1px solid var(--line-2);"
if old in s and ".q-card{max-width:100vw;" not in s:
    s = s.replace(old, new, 1)

open(CSS, "w", encoding="utf-8").write(s)

# 校验
s2 = open(CSS, encoding="utf-8").read()
print("=" * 56)
print("修正后校验")
print("=" * 56)
for sel in [".practice{", ".practice > .q-card", ".practice > .side-panel",
            ".options{", ".q-card{", ".q-body{"]:
    i = s2.find(sel)
    if i >= 0:
        line = s2[i:i + 200].split("\n")[0]
        print("  " + line)

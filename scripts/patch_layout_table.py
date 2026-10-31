"""把答题页布局从 grid/flex 全部改成 table

背景：用户浏览器（Edge + 150% 缩放）中 flex/grid 的宽度计算失效，
表现为选项横跨全屏。table 布局宽度计算最原始可靠。
"""

import sys
import io
import re
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "site", "assets", "style.css")

s = open(CSS, encoding="utf-8").read()
orig = s
changes = []

# ── 1. .practice：grid → table ──
old = (".practice{display:grid;grid-template-columns:minmax(0,1fr) 268px;"
       "gap:16px;align-items:start;width:100%;max-width:100%}")
new = (".practice{display:table;table-layout:fixed;width:100%;max-width:100%;"
       "box-sizing:border-box}")
if old in s:
    s = s.replace(old, new)
    changes.append("practice: grid → table")

# ── 2. practice 子项：grid 子项 → table-cell ──
old2 = ".practice > *{min-width:0;max-width:100%;box-sizing:border-box}"
new2 = (
    ".practice > *{box-sizing:border-box}\n"
    ".practice > .q-card{display:table-cell;vertical-align:top;"
    "padding-right:16px;width:auto}\n"
    ".practice > .side-panel{display:table-cell;vertical-align:top;"
    "width:268px;max-width:268px;padding-left:0}"
)
if old2 in s:
    s = s.replace(old2, new2)
    changes.append("practice 子项 → table-cell")

# ── 3. .options：加 overflow 与 contain，阻断宽度外溢 ──
s2 = s.replace(
    ".options{display:block;width:100%;max-width:100%;box-sizing:border-box;"
    "min-width:0;overflow:visible}",
    ".options{display:block;width:100%;max-width:100%;box-sizing:border-box;"
    "min-width:0;overflow:hidden;contain:layout}")
if s2 != s:
    s = s2
    changes.append("options: overflow:hidden + contain:layout")

# ── 4. .q-card / .q-body / .view 加硬上限，防止父级算错时外溢 ──
#    max-width 是硬约束，不受父容器宽度计算影响
if ".q-card{" in s:
    s = re.sub(
        r"\.q-card\{([^}]*)\}",
        lambda m: ".q-card{" + m.group(1).rstrip(";") + ";max-width:100vw}", s, count=1)
    changes.append("q-card: max-width:100vw")

if ".q-body{" in s:
    s = re.sub(
        r"\.q-body\{([^}]*)\}",
        lambda m: ".q-body{" + m.group(1).rstrip(";") + ";max-width:100%}", s, count=1)
    changes.append("q-body: max-width:100%")

if s != orig:
    open(CSS, "w", encoding="utf-8").write(s)

print("=" * 56)
print("CSS 修改")
print("=" * 56)
for c in changes:
    print("  ✓ " + c)
if not changes:
    print("  （无改动）")

# 校验关键规则现状
s3 = open(CSS, encoding="utf-8").read()
print("\n当前关键规则：")
for sel in [".practice{", ".practice > .q-card", ".options{", ".q-card{", ".q-body{"]:
    i = s3.find(sel)
    if i >= 0:
        print("  " + s3[i:i + 150].split("\n")[0])

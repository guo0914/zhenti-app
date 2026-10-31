"""修复手机端选项文字右侧被裁切的问题

根因：
  1. 表格用了 width:auto + table-layout:fixed，
     但 width:auto 时表格会按「内容」撑开，长文本导致超出容器后被裁切。
  2. 单元格用了 word-break:break-word（非标准废弃属性），
     在 iOS Safari 上不生效，长英文/数字串不换行。

修复：
  · 表格改 width:100%，table-layout:fixed，让列宽严格受容器约束
  · 单元格补 overflow-wrap:anywhere + word-break:break-word（双写兼容）
  · 补 max-width:0（表格布局中让单元格能被压缩的关键）
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "site", "assets")

FILES = ["zhenti-v5.js", "law-v5.js", "papers-v5.js"]

# 旧写法（width:auto 系列参数）
OLD_TABLE_VARIANTS = [
    # papers / law 的字符串拼接版
    ("'width:auto;' +\n"
     "        'max-width:100%;' +\n"
     "        'border-collapse:separate;' +\n"
     "        'border-spacing:0 9px;' +\n"
     "        'table-layout:fixed;' +\n"
     "        'box-sizing:border-box;' +\n"
     "        'margin:0;' +\n"
     "        'padding:0;' +",
     "'width:100%;' +\n"
     "        'max-width:100%;' +\n"
     "        'border-collapse:separate;' +\n"
     "        'border-spacing:0 9px;' +\n"
     "        'table-layout:fixed;' +\n"
     "        'box-sizing:border-box;' +\n"
     "        'margin:0;' +\n"
     "        'padding:0;' +"),
    # zhenti 的模板字符串版
    ('class="opt-table" style="width:auto;max-width:100%;border-collapse:separate;'
     'border-spacing:0 9px;table-layout:fixed;box-sizing:border-box;margin:0;padding:0;">',
     'class="opt-table" style="width:100%;max-width:100%;border-collapse:separate;'
     'border-spacing:0 9px;table-layout:fixed;box-sizing:border-box;margin:0;padding:0;">'),
]

# 单元格样式：补 max-width:0 与兼容换行
OLD_CELL = ("'font-size:14.5px;line-height:1.7;color:#1c2333;word-break:break-word;cursor:pointer;\">' +")
NEW_CELL = ("'font-size:14.5px;line-height:1.7;color:#1c2333;cursor:pointer;' +\n"
            "              'overflow-wrap:anywhere;word-break:break-word;max-width:0;\">' +")

OLD_CELL2 = ('font-size:14.5px;line-height:1.7;color:#1c2333;word-break:break-word;\n'
             '                   cursor:pointer;">')
NEW_CELL2 = ('font-size:14.5px;line-height:1.7;color:#1c2333;\n'
             '                   overflow-wrap:anywhere;word-break:break-word;max-width:0;\n'
             '                   cursor:pointer;">')

for name in FILES:
    path = os.path.join(ASSETS, name)
    if not os.path.exists(path):
        print(f"跳过（不存在）: {name}")
        continue
    s = open(path, encoding="utf-8").read()
    orig = s
    hits = []

    for old, new in OLD_TABLE_VARIANTS:
        if old in s:
            s = s.replace(old, new)
            hits.append("表格 width:auto → width:100%")

    if OLD_CELL in s:
        s = s.replace(OLD_CELL, NEW_CELL)
        hits.append("单元格补 overflow-wrap/max-width")
    if OLD_CELL2 in s:
        s = s.replace(OLD_CELL2, NEW_CELL2)
        hits.append("单元格补 overflow-wrap/max-width（模板版）")

    if s != orig:
        open(path, "w", encoding="utf-8").write(s)
        print(f"{name}: " + "；".join(hits))
    else:
        print(f"{name}: 未匹配（可能已是新写法）")

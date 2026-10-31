"""把选项表格的 width:100% 改成不依赖父容器的写法

问题：width:100% 依赖父容器宽度，父容器算错就溢出。
方案：用 display:block + width:auto + max-width:100%，配合 table-layout:fixed，
     让表格自身按内容和上限计算，不信任父容器的百分比。
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "site", "assets")

# 表格样式：改为 width:auto + max-width:100%，并显式声明盒模型
OLD_PATTERNS = [
    'width:100%;border-collapse:separate;border-spacing:0 9px;table-layout:fixed;',
    "width:100%;border-collapse:separate;'\n        'border-spacing:0 9px;table-layout:fixed;",
]

NEW_TABLE = (
    'width:auto;max-width:100%;border-collapse:separate;'
    'border-spacing:0 9px;table-layout:fixed;box-sizing:border-box;'
    'margin:0;padding:0;'
)

FILES = ["zhenti-v5.js", "law-v5.js", "papers-v5.js"]

for name in FILES:
    path = os.path.join(ASSETS, name)
    s = open(path, encoding="utf-8").read()
    orig = s
    # 统一替换所有出现形式
    s = s.replace(
        'width:100%;border-collapse:separate;border-spacing:0 9px;table-layout:fixed;',
        NEW_TABLE)
    s = s.replace(
        "width:100%;border-collapse:separate;' +\n        'border-spacing:0 9px;table-layout:fixed;",
        NEW_TABLE.replace(';', ";' +\n        '"))
    if s != orig:
        open(path, "w", encoding="utf-8").write(s)
        print(f"{name}: 已更新")
    else:
        print(f"{name}: 未匹配，检查实际内容")
        i = s.find('opt-table')
        print("   实际:", repr(s[i:i + 130]))

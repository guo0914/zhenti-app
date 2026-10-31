"""前端：识别数据缺失标记，给出明确提示而非显示「缺失」二字"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["papers-v5.js", "zhenti-v5.js"]

# 选项渲染：遇到「缺失」字样时显示明确提示
OLD = """(String(text || '').trim() ? esc(text) : '<span style="color:var(--text-3,#8b94a8);font-size:13px">（选项见上方原图）</span>')"""
NEW = """(String(text || '').indexOf('缺失') >= 0
                ? '<span style="color:#d97706;font-size:13px">⚠ 源数据缺失，无法作答</span>'
                : (String(text || '').trim()
                    ? esc(text)
                    : '<span style="color:var(--text-3,#8b94a8);font-size:13px">（选项见上方原图）</span>'))"""

for name in FILES:
    p = os.path.join(ROOT, "site", "assets", name)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    if OLD in s:
        s = s.replace(OLD, NEW)
        # 同时在题头加缺失提示条
        old_head = """      html.push('    <span class="tiny" style="margin-left:auto">' + esc(paperMeta.year) +"""
        new_head = """      if ((q.flags || []).indexOf('dataMissing') >= 0) {
        html.push('    <span class="pill" style="background:#fef3c7;color:#92400e;font-size:11px">源数据缺失</span>');
      }
      html.push('    <span class="tiny" style="margin-left:auto">' + esc(paperMeta.year) +"""
        if old_head in s:
            s = s.replace(old_head, new_head)
            print(f"{name}: 已加题头缺失标记")
        open(p, "w", encoding="utf-8").write(s)
        print(f"{name}: 已修改选项缺失提示")
    else:
        print(f"{name}: 未匹配")

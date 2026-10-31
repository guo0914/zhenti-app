"""给 papers-v5.js 的材料折叠按钮绑定点击事件"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "assets", "papers-v5.js")

s = open(P, encoding="utf-8").read()

OLD = """      // ── 事件绑定 ──
      // 申论：显示参考答案
      var rv = $('#revealRef', v);"""

NEW = """      // ── 事件绑定 ──
      // 材料折叠开关（长材料默认折叠，避免把题干挤到屏幕外）
      var mt = document.getElementById('btnMatToggle');
      if (mt) mt.onclick = function () {
        var mb = document.getElementById('matBody');
        if (!mb) return;
        var expanded = mb.style.maxHeight === 'none';
        mb.style.maxHeight = expanded ? '190px' : 'none';
        mb.style.overflow = expanded ? 'hidden' : 'visible';
        mt.textContent = expanded ? '\u5c55\u5f00\u6750\u6599' : '\u6536\u8d77\u6750\u6599';
      };

      // 申论：显示参考答案
      var rv = $('#revealRef', v);"""

if OLD in s:
    s = s.replace(OLD, NEW)
    open(P, "w", encoding="utf-8").write(s)
    print("已绑定折叠按钮事件")
else:
    print("未匹配")
    i = s.find("事件绑定")
    print(repr(s[i - 30:i + 300]))

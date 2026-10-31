"""修复公式图显示：按原始尺寸显示，不拉伸放大

问题：
  公式图是 15×33、142×22 这类小图（分数、公式片段），
  前端统一用 max-width:100% 渲染，被拉伸到 348px 宽，
  结果糊成一片黑块，看不出是什么公式。

修复：
  区分「题目图」和「公式图」：
    · 题目图（图形推理、图表）：max-width:100%，可放大
    · 公式图：不放大，按原始尺寸显示（image-rendering: auto）
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "assets", "papers-v5.js")

s = open(P, encoding="utf-8").read()

# 题目配图渲染：区分公式图
OLD = """          _imgs.forEach(function (src) {
            html.push('    <img src="' + esc(String(src)) + '" alt="题目图"' +
              ' loading="lazy"' +
              ' onerror="this.style.display=\\'none\\'"' +
              ' style="max-width:100%;height:auto;border-radius:8px;' +
              'border:1px solid var(--line,#e5e7eb)">');
          });"""

NEW = """          _imgs.forEach(function (src) {
            var isFormula = String(src).indexOf('公式图') >= 0;
            // 公式图是 15x33 这类小片段，放大就会糊；
            // 按原始尺寸显示，不设 max-width:100%
            var style = isFormula
              ? 'height:auto;max-width:none;vertical-align:middle;display:inline-block;margin:2px'
              : 'max-width:100%;height:auto;border-radius:8px;' +
                'border:1px solid var(--line,#e5e7eb)';
            html.push('    <img src="' + esc(String(src)) + '" alt="题目图"' +
              ' loading="lazy"' +
              ' onerror="this.style.display=\\'none\\'"' +
              ' style="' + style + '">');
          });"""

if OLD in s:
    s = s.replace(OLD, NEW)
    open(P, "w", encoding="utf-8").write(s)
    print("已修改题目配图渲染（区分公式图）")
else:
    print("未匹配题目配图块")

# 材料图表同样处理
OLD2 = """        (q.materialImgs || []).forEach(function (src) {
          if (!src) return;                       // 跳过空值
          html.push('      <img src="' + esc(String(src)) + '" alt="材料图表"' +
            ' loading="lazy"' +
            ' onerror="this.style.display=\\'none\\'"' +
            ' style="max-width:100%;height:auto;display:block;margin-bottom:10px">');
        });"""

NEW2 = """        (q.materialImgs || []).forEach(function (src) {
          if (!src) return;                       // 跳过空值
          var isFormula = String(src).indexOf('公式图') >= 0;
          var style = isFormula
            ? 'height:auto;max-width:none;vertical-align:middle;display:inline-block;margin:2px'
            : 'max-width:100%;height:auto;display:block;margin-bottom:10px';
          html.push('      <img src="' + esc(String(src)) + '" alt="材料图表"' +
            ' loading="lazy"' +
            ' onerror="this.style.display=\\'none\\'"' +
            ' style="' + style + '">');
        });"""

if OLD2 in s:
    s = s.replace(OLD2, NEW2)
    open(P, "w", encoding="utf-8").write(s)
    print("已修改材料图表渲染（区分公式图）")
else:
    print("未匹配材料图表块")

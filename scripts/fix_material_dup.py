"""修复材料重复渲染 + 图片渲染异常

问题 1：材料显示两遍
  papers-v5.js 里有两个材料渲染块：
    L525-536  申论材料：var matText = q.materials || q.material || ''
    L538-567  行测材料：if (q.material || (q.materialImgs||[]).length)

  申论块会把 q.material 也取出来渲染一次，
  行测块又渲染一次 → 同一份材料显示两遍。

  用户看到「怎么每个地方都有这个原文了」。

修复：
  申论块只处理 q.materials（申论专用字段），
  不再回退到 q.material（那是行测材料题的字段）。

问题 2：图片显示异常
  imgs 字段在不同分片里的形态不同：
    · 有些是相对路径        'assets/zt/题目图/xxx.png'
    · 有些可能带前缀或为空

  需要：
  · 过滤空值
  · 统一路径
  · 加加载失败兜底（不显示破图）

问题 3：电脑端问题多（回归风险）
  最近 6 次提交都改动过 papers-v5.js，
  需要逐项验证原有功能未被破坏。
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "assets", "papers-v5.js")

s = open(P, encoding="utf-8").read()
orig = s

# ── 修复 1：申论材料块不再回退到 q.material ──
old1 = """      // 申论材料
      if (isShenlun) {
        var matText = q.materials || q.material || '';"""
new1 = """      // 申论材料（只取申论专用字段 materials；
      // 不回退 q.material，那是行测材料题字段，否则会与下面的行测材料块重复渲染）
      if (isShenlun) {
        var matText = q.materials || '';"""

if old1 in s:
    s = s.replace(old1, new1)
    print("[1] 申论材料块：已移除 q.material 回退，避免重复渲染")
else:
    print("[1] 未匹配申论材料块")

# ── 修复 2：图片渲染增加空值过滤与失败兜底 ──
old2 = """        (q.materialImgs || []).forEach(function (src) {
          html.push('      <img src="' + esc(src) + '" alt="材料图表"' +
            ' style="max-width:100%;height:auto;display:block;margin-bottom:10px">');
        });"""
new2 = """        (q.materialImgs || []).forEach(function (src) {
          if (!src) return;                       // 跳过空值
          html.push('      <img src="' + esc(String(src)) + '" alt="材料图表"' +
            ' loading="lazy"' +
            ' onerror="this.style.display=\\'none\\'"' +
            ' style="max-width:100%;height:auto;display:block;margin-bottom:10px">');
        });"""

if old2 in s:
    s = s.replace(old2, new2)
    print("[2] 材料图表：已加空值过滤 + 加载失败隐藏")
else:
    print("[2] 未匹配材料图表块")

# ── 修复 3：题目配图同样处理 ──
old3 = """      if ((q.imgs || []).length) {
        html.push('  <div style="margin-top:12px;display:flex;flex-direction:column;gap:8px">');
        q.imgs.forEach(function (src) {
          html.push('    <img src="' + esc(src) + '" alt="题目图"' +
            ' style="max-width:100%;height:auto;border-radius:8px;' +
            'border:1px solid var(--line,#e5e7eb)">');
        });
        html.push('  </div>');
      }"""
new3 = """      if ((q.imgs || []).length) {
        var _imgs = q.imgs.filter(function (x) { return x; });
        if (_imgs.length) {
          html.push('  <div style="margin-top:12px;display:flex;flex-direction:column;gap:8px">');
          _imgs.forEach(function (src) {
            html.push('    <img src="' + esc(String(src)) + '" alt="题目图"' +
              ' loading="lazy"' +
              ' onerror="this.style.display=\\'none\\'"' +
              ' style="max-width:100%;height:auto;border-radius:8px;' +
              'border:1px solid var(--line,#e5e7eb)">');
          });
          html.push('  </div>');
        }
      }"""

if old3 in s:
    s = s.replace(old3, new3)
    print("[3] 题目配图：已加空值过滤 + 加载失败隐藏")
else:
    print("[3] 未匹配题目配图块")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入 papers-v5.js")
else:
    print("\n无改动")

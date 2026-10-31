"""修复套卷计时

问题：
  1. 按钮显示与实际倒计时不一致：
       按钮  Math.round(135 * 0.9) = 122 分钟
       实际  Math.round(135 * 0.9 * 60) = 7290 秒 = 121.5 分钟
     用户看到「122 分钟」，倒计时却是 2:01:25。

  2. 按 0.9 分钟/题估算，与真实国考时长不符：
       国考副省级 135 题 / 120 分钟
       国考地市级 130 题 / 120 分钟
     用 0.9 系数算出 121.5 / 117 分钟，都不是 120。

  3. 分模块练习按模块题量算时长（如 20 题 → 18 分钟），
     与实际考试节奏不符。

修复：
  · 整卷模拟：按卷的官方时长（国考 120 分钟；其他按题量×0.9 但不低于 120）
  · 分模块练习：按该模块题量 × 0.9 分钟（合理，因为只做部分题）
  · 按钮显示与实际倒计时用同一个函数计算，保证一致
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "assets", "papers-v5.js")

s = open(P, encoding="utf-8").read()
orig = s

# ── 1. 新增统一时长计算函数（放在 runSession 之前）──
ANCHOR = """  /* 答题会话 */
  function runSession(v, paperMeta, moduleCat, timed, pool) {"""

NEWFUNC = """  /* 计算考试时长（秒）
   * 整卷模拟：优先用官方时长（国考行测固定 120 分钟），
   *           其他卷按题量 × 0.9 分钟估算；
   * 分模块练习：按该模块题量 × 0.9 分钟。
   * 按钮文案与实际倒计时都调用它，避免显示与倒计时不一致。 */
  function examSeconds(poolLen, isWholePaper, kind) {
    if (!poolLen) return 0;
    if (isWholePaper) {
      // 国考行测：无论 130 题还是 135 题，考试时间都是 120 分钟
      if (kind === 'guokao') return 120 * 60;
      // 其他省考按 0.9 分/题，但不低于 100 分钟
      return Math.max(100, Math.round(poolLen * 0.9)) * 60;
    }
    // 分模块：按模块题量
    return Math.round(poolLen * 0.9 * 60);
  }

  /* 答题会话 */
  function runSession(v, paperMeta, moduleCat, timed, pool) {"""

if ANCHOR in s and "function examSeconds" not in s:
    s = s.replace(ANCHOR, NEWFUNC, 1)
    print("[1] 已加 examSeconds()")
else:
    print("[1] 未匹配 runSession")

# ── 2. runSession 里改用 examSeconds ──
OLD2 = """    // 限时：每题 0.9 分钟（54 秒）。真实国考 130 题 120 分钟 ≈ 0.92 分/题。
    // 注意单位是「秒」，必须 ×60。
    var limitSec = timed ? Math.round(pool.length * 0.9 * 60) : 0;"""

NEW2 = """    // 限时：统一走 examSeconds()，保证按钮显示与实际倒计时一致
    var limitSec = timed
      ? examSeconds(pool.length, !moduleCat, paperMeta && paperMeta.kind)
      : 0;"""

if OLD2 in s:
    s = s.replace(OLD2, NEW2)
    print("[2] runSession 计时已改用 examSeconds")
else:
    print("[2] 未匹配计时赋值")

# ── 3. 按钮文案改用 examSeconds ──
OLD3 = """    html.push('    <button class="btn primary" data-mode="timed">限时模拟（' +
      Math.round(p.total * 0.9) + ' 分钟）</button>');"""

NEW3 = """    var _wholeSec = examSeconds(p.total, true, p.kind);
    html.push('    <button class="btn primary" data-mode="timed">限时模拟（' +
      Math.round(_wholeSec / 60) + ' 分钟）</button>');"""

if OLD3 in s:
    s = s.replace(OLD3, NEW3)
    print("[3] 按钮文案已改用 examSeconds")
else:
    print("[3] 未匹配按钮文案")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入 papers-v5.js")

"""设置页增强：加 Key 测试按钮 + 用量统计显示"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "assets", "shenlun.js")

s = open(P, encoding="utf-8").read()
orig = s

# ── 1. 设置弹窗：测试按钮 + 用量区 ──
OLD = '''      <p class="tiny" style="margin:0 0 12px 0;color:var(--text-3,#8b94a8)">
        OCR 识别与批改会消耗你账户的 token。
      </p>
      <div class="row" style="gap:8px">
        <button class="btn primary" id="btnSaveSettings">保存</button>
        <button class="btn" id="btnCloseSettings">取消</button>
      </div></div>`;'''

NEW = '''      <p class="tiny" style="margin:0 0 12px 0;color:var(--text-3,#8b94a8)">
        OCR 识别与批改会消耗你账户的 token。
      </p>
      <div id="slTestResult" class="tiny" style="margin:0 0 10px 0;min-height:18px"></div>
      <div class="row" style="gap:8px;flex-wrap:wrap">
        <button class="btn primary" id="btnSaveSettings">保存</button>
        <button class="btn" id="btnTestKey">测试 Key</button>
        <button class="btn" id="btnCloseSettings">取消</button>
      </div>
      ${usageBox()}
      </div>`;'''

if OLD in s:
    s = s.replace(OLD, NEW)
    print("[1] 设置弹窗已加测试按钮与用量区")
else:
    print("[1] 未匹配设置弹窗")

# ── 2. 加 usageBox() 函数 ──
ANCHOR = """  /** 测试当前 Key 是否可用 */"""
NEWFUNC = """  /** 设置页里的用量统计块 */
  function usageBox() {
    var u = getUsage();
    var total = u.prompt + u.completion;
    if (!u.calls) {
      return '<div class="tiny" style="margin-top:14px;padding-top:12px;' +
        'border-top:1px dashed var(--line,#e5e7eb);color:var(--text-3,#8b94a8)">' +
        '尚无调用记录</div>';
    }
    var last = u.lastAt ? new Date(u.lastAt).toLocaleString('zh-CN',
      { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-';
    return '<div style="margin-top:14px;padding-top:12px;border-top:1px dashed var(--line,#e5e7eb)">' +
      '<div class="tiny" style="font-weight:600;margin-bottom:6px">📊 本次设备用量</div>' +
      '<div class="tiny" style="line-height:1.9">' +
      '调用 <b>' + u.calls + '</b> 次　·　消耗 <b>' + total + '</b> tokens' +
      '　（输入 ' + u.prompt + ' / 输出 ' + u.completion + '）<br>' +
      '最近一次：' + last +
      '</div>' +
      '<button class="btn sm" id="btnResetUsage" style="margin-top:8px">清零统计</button>' +
      '</div>';
  }

  /** 测试当前 Key 是否可用 */"""

if ANCHOR in s and "function usageBox" not in s:
    s = s.replace(ANCHOR, NEWFUNC, 1)
    print("[2] 已加 usageBox()")
else:
    print("[2] 未匹配或不需插入")

# ── 3. 绑定测试按钮 + 清零按钮 ──
OLD3 = """    overlay.querySelector('#btnCloseSettings').onclick = () => overlay.remove();"""
NEW3 = """    var tk = overlay.querySelector('#btnTestKey');
    if (tk) tk.onclick = function () {
      var res = overlay.querySelector('#slTestResult');
      var key = (overlay.querySelector('#slApiKey').value || '').trim();
      if (!key) { res.innerHTML = '<span style="color:#dc2626">请先填入 Key</span>'; return; }
      // 先临时保存再测试，测完保留（用户点保存才真正生效，但测试需要当前值）
      res.innerHTML = '<span style="color:#d97706">测试中…</span>';
      tk.disabled = true;
      // 临时写入 localStorage 供 testCurrentKey 读取
      var old = getApiKey();
      setApiKey(key);
      testCurrentKey(function (r) {
        tk.disabled = false;
        if (r.ok) {
          res.innerHTML = '<span style="color:#16a34a">✓ ' + esc(r.msg) + '</span>';
        } else {
          res.innerHTML = '<span style="color:#dc2626">✗ ' + esc(r.msg) + '</span>';
          setApiKey(old);   // 失败则回滚
        }
      });
    };

    var ru = overlay.querySelector('#btnResetUsage');
    if (ru) ru.onclick = function () {
      resetUsage();
      var box = overlay.querySelector('#slTestResult');
      if (box) box.innerHTML = '<span style="color:#16a34a">用量统计已清零</span>';
    };

    overlay.querySelector('#btnCloseSettings').onclick = () => overlay.remove();"""

if OLD3 in s:
    s = s.replace(OLD3, NEW3)
    print("[3] 已绑定测试 / 清零按钮")
else:
    print("[3] 未匹配关闭按钮")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入")

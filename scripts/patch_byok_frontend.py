"""恢复前端 API Key 输入框（用户自带 Key）

要点：
  1. 设置弹窗恢复输入框，存 localStorage（仅本机，不上服务器）
  2. 调用 /api/ai/chat 时带 X-User-Api-Key 头
  3. 没填 Key 时给出明确提示
"""

import sys
import io
import os
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "assets", "shenlun.js")

s = open(P, encoding="utf-8").read()
orig = s

# ── 1. 设置弹窗：恢复输入框 ──
OLD = '''      <label style="display:block;margin-bottom:4px;font-weight:600">DeepSeek API Key</label>
      <div style="padding:8px 0;font-size:13px;color:var(--text-2,#5a6478)">AI 批改由服务器统一提供，无需填写 API Key。如提示「服务器未配置」，请联系站点管理员。</div>
      <p class="tiny" style="margin:6px 0 12px 0">Key 仅保存在浏览器本地，不上传到任何服务器。OCR 识别和批改均消耗 token。</p>'''

NEW = '''      <label style="display:block;margin-bottom:4px;font-weight:600">DeepSeek API Key</label>
      <input type="password" id="slApiKey"
        style="width:100%;box-sizing:border-box;padding:8px 10px;border:1.5px solid var(--line,#c5cddd);border-radius:8px;font-size:13px"
        value="${esc(getApiKey())}" placeholder="sk-xxxxxxxxxxxxxxxx">
      <p class="tiny" style="margin:6px 0 4px 0">
        在 <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener">platform.deepseek.com</a>
        申请（约 ¥1 起充）。Key 只保存在你自己的设备上，不会上传。
      </p>
      <p class="tiny" style="margin:0 0 12px 0;color:var(--text-3,#8b94a8)">
        OCR 识别与批改会消耗你账户的 token。
      </p>'''

if OLD in s:
    s = s.replace(OLD, NEW)
    print("[1] 已恢复 API Key 输入框")
else:
    print("[1] 未匹配设置弹窗")

# ── 2. 保存按钮：加校验与提示 ──
OLD2 = '''    overlay.querySelector('#btnSaveSettings').onclick = () => { setApiKey(overlay.querySelector('#slApiKey').value.trim()); overlay.remove(); window.toast ? window.toast('API Key 已保存') : alert('已保存'); };'''
NEW2 = '''    overlay.querySelector('#btnSaveSettings').onclick = () => {
      var v = (overlay.querySelector('#slApiKey').value || '').trim();
      if (v && !/^[\\w-]{8,}$/.test(v)) {
        alert('Key 格式不正确，应以 sk- 开头且无空格');
        return;
      }
      setApiKey(v);
      overlay.remove();
      window.toast ? window.toast(v ? 'API Key 已保存' : '已清空 API Key') : alert('已保存');
    };'''

if OLD2 in s:
    s = s.replace(OLD2, NEW2)
    print("[2] 保存按钮已加校验")
else:
    print("[2] 未匹配保存按钮")

# ── 3. 两处 fetch 加 X-User-Api-Key 头 ──
OLD3 = """      headers: { 'Content-Type': 'application/json' },"""
NEW3 = """      headers: buildAIHeaders(),"""

cnt = s.count(OLD3)
s = s.replace(OLD3, NEW3)
print(f"[3] 已替换 {cnt} 处 headers")

# ── 4. 新增 buildAIHeaders 与 Key 检查 ──
OLD4 = """  function getApiKey() {
    try { return localStorage.getItem(LS_KEY) || ''; }
    catch (e) { return ''; }
  }"""
NEW4 = """  function getApiKey() {
    try { return localStorage.getItem(LS_KEY) || ''; }
    catch (e) { return ''; }
  }

  /** 构造 AI 请求头：带上用户自己的 Key */
  function buildAIHeaders() {
    var h = { 'Content-Type': 'application/json' };
    var k = getApiKey().trim();
    if (k) h['X-User-Api-Key'] = k;
    return h;
  }

  /** 未填 Key 时抛出可读错误 */
  function requireApiKey() {
    var k = getApiKey().trim();
    if (!k) {
      throw new Error('请先在「⚙ 设置」里填入你的 DeepSeek API Key（platform.deepseek.com 免费申请）');
    }
    return k;
  }"""

if OLD4 in s:
    s = s.replace(OLD4, NEW4)
    print("[4] 已新增 buildAIHeaders / requireApiKey")
else:
    print("[4] 未匹配 getApiKey")

# ── 5. 两处调用前加 requireApiKey() ──
#    之前在 runOCR 和批改函数里都删掉了 key 检查，现在恢复
OLD5 = """    // API Key 由服务器端注入，前端无需检查
"""
NEW5 = """    requireApiKey();   // 未填 Key 时报错
"""
cnt5 = s.count(OLD5)
s = s.replace(OLD5, NEW5)
print(f"[5] 已恢复 {cnt5} 处 Key 前置检查")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入 shenlun.js")

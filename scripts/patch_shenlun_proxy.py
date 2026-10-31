"""前端改为调用本地服务器代理，不再直连 DeepSeek

改动：
  1. API_BASE 从 https://api.deepseek.com/v1 改为空（走同源 /api/）
  2. 两处 fetch(API_BASE + '/chat/completions') 改为 fetch('/api/ai/chat')
  3. 去掉 Authorization 头的拼接（key 由服务器注入）
  4. getApiKey / setApiKey 保留但只在服务器未配置时用于提示
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

# ── 1. 去掉直连地址 ──
OLD1 = "  const API_BASE = 'https://api.deepseek.com/v1';"
NEW1 = ("  // AI 请求走本地服务器代理（/api/ai/chat），\n"
        "  // API Key 保存在服务器端，前端不再接触，开源也不会泄漏。\n"
        "  const AI_ENDPOINT = '/api/ai/chat';")
if OLD1 in s:
    s = s.replace(OLD1, NEW1)
    print("[1] API_BASE 已改为本地代理")
else:
    print("[1] 未匹配 API_BASE")

# ── 2. 两处调用改为代理端点，去掉 Authorization ──
OLD2A = """    const resp = await fetch(API_BASE + '/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key },"""
NEW2A = """    const resp = await fetch(AI_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },"""

countA = s.count(OLD2A)
s = s.replace(OLD2A, NEW2A)
print(f"[2] 已替换 {countA} 处调用（headers 去掉 Authorization）")

# ── 3. 去掉「请先设置 API Key」的前置拦截 ──
#    key 现在由服务器管，前端不需要检查
OLD3A = """    const key = getApiKey().trim();
    if (!key) throw new Error('请先设置 API Key');
"""
NEW3A = """    // API Key 由服务器端注入，前端无需检查
"""
count3 = s.count(OLD3A)
s = s.replace(OLD3A, NEW3A)
print(f"[3] 已移除 {count3} 处前端 key 检查")

# ── 4. 设置页文案改为说明「服务器统一配置」 ──
OLD4 = """      <input type="password" id="slApiKey" """
if OLD4 in s:
    # 找到整个 input 行并替换为说明文字
    m = re.search(r'<input type="password" id="slApiKey"[^>]*>', s)
    if m:
        old_input = m.group(0)
        new_text = ('<div style="padding:8px 0;font-size:13px;color:var(--text-2,#5a6478)">'
                    'AI 批改由服务器统一提供，无需填写 API Key。'
                    '如提示「服务器未配置」，请联系站点管理员。</div>')
        s = s.replace(old_input, new_text)
        print("[4] 设置页已改为说明文案")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入 shenlun.js")
else:
    print("\n无改动")

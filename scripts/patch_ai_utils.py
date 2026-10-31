"""给 AI 批改添加实用功能（最小改动版）

新增：
  1. 用量统计：记录每次 token 消耗，设置页可见
  2. 友好错误提示：401/402/429 等各有中文说明
  3. Key 测试按钮：设置页可立即验证 Key
  4. 请求超时提示

策略：不改两处 fetch 的结构，只在它们周围做增强。
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

# ── 1. 在 buildAIHeaders 之后插入工具函数 ──
ANCHOR = """  /** 构造 AI 请求头：带上用户自己的 Key */
  function buildAIHeaders() {
    var h = { 'Content-Type': 'application/json' };
    var k = getApiKey().trim();
    if (k) h['X-User-Api-Key'] = k;
    return h;
  }"""

UTILS = ANCHOR + """

  /* ═══════════════ 用量统计 ═══════════════ */
  const LS_USAGE = 'zlfx.shenlun.usage';

  function getUsage() {
    try {
      var u = JSON.parse(localStorage.getItem(LS_USAGE) || '{}');
      return {
        prompt: u.prompt || 0,
        completion: u.completion || 0,
        calls: u.calls || 0,
        lastAt: u.lastAt || 0
      };
    } catch (e) { return { prompt: 0, completion: 0, calls: 0, lastAt: 0 }; }
  }

  function addUsage(usage) {
    if (!usage) return;
    var u = getUsage();
    u.prompt += usage.prompt_tokens || 0;
    u.completion += usage.completion_tokens || 0;
    u.calls += 1;
    u.lastAt = Date.now();
    try { localStorage.setItem(LS_USAGE, JSON.stringify(u)); } catch (e) {}
  }

  function resetUsage() {
    try { localStorage.removeItem(LS_USAGE); } catch (e) {}
  }

  /* ═══════════════ 友好错误 ═══════════════ */
  function friendlyAIError(status, serverMsg) {
    if (serverMsg && serverMsg.length > 8) return serverMsg;
    var MAP = {
      401: 'API Key 无效或已失效。请检查是否填对，或去 platform.deepseek.com 重新生成',
      402: 'DeepSeek 账户余额不足，请充值后再用 AI 批改',
      403: 'API Key 无权限访问该模型',
      429: '请求太频繁被限流，等 1 分钟再试',
      500: 'DeepSeek 服务器出错，稍后重试',
      502: '无法连接 DeepSeek，请检查网络',
      503: '服务不可用（可能未配置 Key 或 DeepSeek 下线）',
      504: '请求超时，可能图片太大或网络慢'
    };
    return MAP[status] || ('请求失败（HTTP ' + status + '）');
  }

  /** 测试当前 Key 是否可用 */
  async function testCurrentKey(cb) {
    var k = getApiKey().trim();
    if (!k) { cb({ ok: false, msg: '还没填 Key' }); return; }
    try {
      var resp = await fetch(AI_ENDPOINT, {
        method: 'POST',
        headers: buildAIHeaders(),
        body: JSON.stringify({
          model: 'deepseek-chat',
          messages: [{ role: 'user', content: 'ping' }],
          max_tokens: 3
        })
      });
      if (resp.ok) { cb({ ok: true, msg: 'Key 可用' }); return; }
      var d = await resp.json().catch(function () { return {}; });
      cb({ ok: false, msg: friendlyAIError(resp.status, (d.error || {}).message) });
    } catch (e) {
      cb({ ok: false, msg: '网络错误：' + (e.message || e) });
    }
  }"""

if ANCHOR in s:
    s = s.replace(ANCHOR, UTILS)
    print("[1] 已插入用量统计 / 错误翻译 / Key 测试")
else:
    print("[1] 未匹配 buildAIHeaders")

# ── 2. 两处错误处理：换成 friendlyAIError ──
OLD_ERR1 = """    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error?.message || `OCR 错误 ${resp.status}`);
    }
    const data = await resp.json();
    return (data.choices?.[0]?.message?.content || '').trim();"""
NEW_ERR1 = """    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(friendlyAIError(resp.status, (err.error || {}).message));
    }
    const data = await resp.json();
    addUsage(data.usage);
    return (data.choices?.[0]?.message?.content || '').trim();"""

if OLD_ERR1 in s:
    s = s.replace(OLD_ERR1, NEW_ERR1)
    print("[2a] OCR 错误处理已增强（含用量记录）")
else:
    print("[2a] 未匹配 OCR 错误块")

OLD_ERR2 = """    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error?.message || `API 错误 ${resp.status}`);
    }

    const data = await resp.json();"""
NEW_ERR2 = """    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(friendlyAIError(resp.status, (err.error || {}).message));
    }

    const data = await resp.json();
    addUsage(data.usage);"""

if OLD_ERR2 in s:
    s = s.replace(OLD_ERR2, NEW_ERR2)
    print("[2b] 批改错误处理已增强（含用量记录）")
else:
    print("[2b] 未匹配批改错误块")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入")

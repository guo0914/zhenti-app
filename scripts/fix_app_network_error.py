"""修复 App 内 AI 请求「网络错误」

根因：
  shenlun.js 用相对路径 '/api/ai/chat'。
  宿主是 capacitor://localhost，相对路径会打到 App 内部 → 必然失败。
  mobile/www-extras/api-base.js 会拦截 /api/ 开头的请求并加服务器地址，
  但前提是 localStorage['zlfx.apiBase'] 或 window.__API_BASE__ 已配置；
  未配置时拦截不生效，请求直接失败。

修复：
  1. 网络错误时给出可操作提示（告诉用户去设置服务器地址）
  2. 若 App 内未配置地址，明确区分「服务器地址没填」vs「网络不通」
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "site", "assets", "shenlun.js")

s = open(P, encoding="utf-8").read()
orig = s

# ── 1. 新增：检测是否处于 App 且未配置服务器 ──
ANCHOR = """  /* ═══════════════ 友好错误 ═══════════════ */"""
INSERT = """  /* ═══════════════ 环境诊断 ═══════════════ */

  /** 当前是否运行在 App 壳里（capacitor） */
  function isAppShell() {
    try {
      var p = location.protocol;
      return p === 'capacitor:' || p === 'ionic:' ||
             (window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
    } catch (e) { return false; }
  }

  /** App 内是否已配置服务器地址 */
  function hasServerBase() {
    try {
      var b = localStorage.getItem('zlfx.apiBase') || '';
      if (!b && window.__API_BASE_GET__) b = window.__API_BASE_GET__() || '';
      if (!b && window.__APP_CONFIG__ && window.__APP_CONFIG__.apiBase) {
        b = window.__APP_CONFIG__.apiBase || '';
      }
      return !!b;
    } catch (e) { return false; }
  }

  /** 网络失败时给出可操作的提示 */
  function networkErrorMessage(err) {
    var raw = (err && err.message) || String(err);
    if (isAppShell() && !hasServerBase()) {
      return '还没配置服务器地址。请到 App 首页的 ⚙ 设置，填写你的服务器地址' +
             '（例如 https://你的隧道地址 或 http://电脑IP:8000），再回来试。';
    }
    if (isAppShell()) {
      return '连不上服务器。请检查：① ⚙ 设置里的服务器地址是否正确；' +
             '② 电脑上的程序是否在运行；③ 手机是否和电脑通网。\\n原始错误：' + raw;
    }
    return '网络请求失败：' + raw;
  }

  /* ═══════════════ 友好错误 ═══════════════ */"""

if ANCHOR in s and "function isAppShell" not in s:
    s = s.replace(ANCHOR, INSERT, 1)
    print("[1] 已加环境诊断函数")
else:
    print("[1] 未匹配或已存在")

# ── 2. testCurrentKey 的 catch 用新提示 ──
OLD2 = """    } catch (e) {
      cb({ ok: false, msg: '网络错误：' + (e.message || e) });
    }"""
NEW2 = """    } catch (e) {
      cb({ ok: false, msg: networkErrorMessage(e) });
    }"""

if OLD2 in s:
    s = s.replace(OLD2, NEW2)
    print("[2] testCurrentKey 错误提示已改进")
else:
    print("[2] 未匹配 testCurrentKey catch")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入")

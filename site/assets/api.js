/* =========================================================
   资料分析刷题 · API 客户端
   在线模式走后端（server.py），离线模式自动降级到 localStorage
   ========================================================= */
(function () {
  'use strict';

  const TOKEN_KEY = 'zlfx.auth.token';
  const USER_KEY = 'zlfx.auth.user';

  const api = {
    online: false,
    token: '',
    user: null,
    base: '',
  };

  function safeGet(k) {
    try { return localStorage.getItem(k) || ''; } catch (e) { return ''; }
  }
  function safeSet(k, v) {
    try { localStorage.setItem(k, v); } catch (e) { /* ignore */ }
  }
  function safeDel(k) {
    try { localStorage.removeItem(k); } catch (e) { /* ignore */ }
  }

  api.loadToken = function () {
    api.token = safeGet(TOKEN_KEY);
    try {
      api.user = JSON.parse(safeGet(USER_KEY) || 'null');
    } catch (e) {
      api.user = null;
    }
    return api.token;
  };

  api.saveAuth = function (token, user) {
    api.token = token || '';
    api.user = user || null;
    if (token) safeSet(TOKEN_KEY, token); else safeDel(TOKEN_KEY);
    if (user) safeSet(USER_KEY, JSON.stringify(user)); else safeDel(USER_KEY);
  };

  api.clearAuth = function () {
    api.saveAuth('', null);
  };

  async function request(path, options) {
    const opt = options || {};
    const headers = { 'Content-Type': 'application/json' };
    if (api.token) headers.Authorization = 'Bearer ' + api.token;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), opt.timeout || 8000);
    try {
      const res = await fetch(api.base + path, {
        method: opt.method || (opt.body ? 'POST' : 'GET'),
        headers,
        body: opt.body ? JSON.stringify(opt.body) : undefined,
        signal: ctrl.signal,
        credentials: 'same-origin',
      });
      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
      if (!res.ok) {
        const msg = (data && data.error) || `请求失败（${res.status}）`;
        const err = new Error(msg);
        err.status = res.status;
        throw err;
      }
      api.online = true;
      // 空响应体保护：避免上层解构崩溃
      if (data === null || data === undefined) {
        const _e = new Error('服务器返回空数据（App 内请先在 ⚙ 设置页配置服务器地址）');
        _e.status = res.status;
        throw _e;
      }
      return data;
    } finally {
      clearTimeout(timer);
    }
  }

  /** 探测后端是否可用（仅 http/https 下探测，file:// 直接离线） */
  api.probe = async function () {
    if (location.protocol === 'file:') {
      api.online = false;
      return false;
    }
    try {
      await request('/api/health', { timeout: 2500 });
      api.online = true;
    } catch (e) {
      api.online = false;
    }
    return api.online;
  };

  api.register = async function (username, password, nickname) {
    const data = await request('/api/auth/register', {
      body: { username, password, nickname },
    });
    if (!data || !data.token) {
      throw new Error('注册失败：服务器返回数据异常（可能未配置服务器地址）');
    }
    api.saveAuth(data.token, data.user);
    return data.user;
  };

  api.login = async function (username, password) {
    const data = await request('/api/auth/login', { body: { username, password } });
    if (!data || !data.token) {
      throw new Error('登录失败：服务器返回数据异常（可能未配置服务器地址）');
    }
    api.saveAuth(data.token, data.user);
    return data.user;
  };

  api.logout = async function () {
    try {
      if (api.token) await request('/api/auth/logout', { body: {} });
    } catch (e) {
      /* 忽略 */
    }
    api.clearAuth();
  };

  api.me = async function () {
    const data = await request('/api/auth/me');
    api.user = data.user;
    safeSet(USER_KEY, JSON.stringify(data.user));
    return data.user;
  };

  api.getProgress = () => request('/api/progress');
  api.pushProgress = (payload) => request('/api/progress', { body: payload });

  api.answer = (payload) => request('/api/answer', { body: payload, timeout: 5000 })
    .catch(() => null);

  api.favorite = (qid, fav, bank) =>
    request('/api/favorite', { body: { qid, fav: !!fav, bank } }).catch(() => null);

  api.wrong = (qid, action, bank) =>
    request('/api/wrong', { body: { qid, action, bank } }).catch(() => null);

  api.timer = (setNo, elapsed, limit, submitted, bank) =>
    request('/api/timer', {
      body: { set: setNo, elapsed, limit, submitted: !!submitted, bank },
    }).catch(() => null);

  api.stats = () => request('/api/stats');
  api.resetProgress = () => request('/api/reset', { body: {} });

  api.loadToken();
  window.ZLFX_API = api;
})();

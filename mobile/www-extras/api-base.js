/* ===== API 基址注入（App 专用）=====
 *
 * 背景：站点前端用相对路径调用 /api/xxx，打包成 App 后
 * 页面位于 capacitor://localhost，相对路径会打到 App 内部而失败。
 *
 * 做法：
 *   在 XHR/fetch 层面拦截所有以 /api/ 开头的请求，
 *   改写成用户配置的服务器绝对地址。
 *
 * 服务器地址来源（优先级从高到低）：
 *   1. localStorage['zlfx.apiBase']（App 内设置页写入）
 *   2. window.__API_BASE__（构建时注入）
 *   3. 空（离线模式，只用本地题库）
 */
(function () {
  'use strict';

  function getBase() {
    var b = '';
    try { b = localStorage.getItem('zlfx.apiBase') || ''; } catch (e) {}
    if (!b && window.__API_BASE__) b = window.__API_BASE__;
    if (!b && window.__APP_CONFIG__ && window.__APP_CONFIG__.apiBase) {
      b = window.__APP_CONFIG__.apiBase;
    }
    return (b || '').replace(/\/+$/, '');
  }

  var BASE = getBase();

  if (!BASE) {
    // 没有配置服务器 → 离线模式，API 调用直接失败（前端会降级到 localStorage）
    console.log('[api-base] 未配置服务器，运行在离线模式');
  } else {
    console.log('[api-base] 服务器：' + BASE);
  }

  /* ---- 包装 fetch ---- */
  var _fetch = window.fetch;
  if (_fetch) {
    window.fetch = function (input, init) {
      try {
        var url = typeof input === 'string' ? input : (input && input.url) || '';
        if (BASE && url.indexOf('/api/') === 0) {
          url = BASE + url;
          if (typeof input === 'string') {
            input = url;
          } else {
            input = new Request(url, input);
          }
        }
      } catch (e) {}
      return _fetch.call(window, input, init);
    };
  }

  /* ---- 包装 XMLHttpRequest（部分旧代码可能用它）---- */
  if (window.XMLHttpRequest) {
    var _open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
      var args = Array.prototype.slice.call(arguments);
      try {
        if (BASE && typeof url === 'string' && url.indexOf('/api/') === 0) {
          args[1] = BASE + url;
        }
      } catch (e) {}
      return _open.apply(this, args);
    };
  }

  /* ---- 暴露给设置页使用 ---- */
  window.__API_BASE_GET__ = getBase;
  window.__API_BASE_SET__ = function (v) {
    v = (v || '').trim().replace(/\/+$/, '');
    try {
      if (v) localStorage.setItem('zlfx.apiBase', v);
      else localStorage.removeItem('zlfx.apiBase');
    } catch (e) {}
    BASE = v;
    console.log('[api-base] 已更新为：' + (v || '(空，离线模式)'));
    return v;
  };

  /* ---- 连通性测试 ---- */
  window.__API_TEST__ = function (cb) {
    if (!BASE) { cb && cb({ ok: false, msg: '未配置服务器地址' }); return; }
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, 8000);
    _fetch.call(window, BASE + '/api/health', { signal: ctrl.signal })
      .then(function (r) {
        clearTimeout(timer);
        return r.json().catch(function () { return { ok: r.ok }; });
      })
      .then(function (d) { cb && cb({ ok: true, msg: '连接成功', data: d }); })
      .catch(function (e) {
        clearTimeout(timer);
        cb && cb({ ok: false, msg: '连接失败：' + (e.message || e) });
      });
  };
})();

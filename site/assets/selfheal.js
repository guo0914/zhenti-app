/* ===== 自愈脚本 selfheal.js =====
 *
 * 存在的理由：
 *   如果旧 Service Worker 缓存了旧版 index.html，
 *   index.html 里内嵌的清理逻辑永远更新不到（死循环），
 *   用户会一直看到旧的 CSS/JS（布局崩坏）。
 *
 * 做法：
 *   1. 本文件用固定文件名 + 查询参数引用，尽量不被缓存
 *   2. 启动时读取当前页面声明的版本（index.html 里的 data-app-ver）
 *   3. 与本文件内置的版本比对，不一致则：
 *        注销所有 SW → 删除所有 Cache → 标记已修复 → 带时间戳重载
 *   4. 一致则什么都不做（零开销）
 *
 * 注意：本文件必须保持「小、无依赖」，避免自身被缓存出问题。
 */
(function () {
  'use strict';

  // 本版本号。每次需要强制客户端刷新时，把它 +1。
  var MY_VERSION = 'v5.0';

  // 存储键
  var FLAG = 'zlfx.selfheal.version';

  function getPageVersion() {
    // index.html 会在 <html> 或 <body> 上写 data-app-ver
    var el = document.documentElement.getAttribute('data-app-ver');
    if (el) return el;
    var b = document.body && document.body.getAttribute('data-app-ver');
    if (b) return b;
    // 兜底：从 VER 变量里取（index.html 内联脚本会设置）
    if (window.__APP_VER__) return window.__APP_VER__;
    return '';
  }

  function doHeal(reason) {
    var tasks = [];

    // 1) 注销所有 SW（同时查 window.navigator 与全局，兼容各种环境）
    var nav = (window.navigator && window.navigator.serviceWorker) ||
              (typeof navigator !== 'undefined' && navigator.serviceWorker);
    if (nav && nav.getRegistrations) {
      tasks.push(
        nav.getRegistrations()
          .then(function (rs) {
            return Promise.all(rs.map(function (r) { return r.unregister(); }));
          })
          .catch(function () {})
      );
    }

    // 2) 删除所有 Cache Storage
    var cstore = window.caches || (typeof caches !== 'undefined' ? caches : null);
    if (cstore && cstore.keys) {
      tasks.push(
        cstore.keys()
          .then(function (keys) {
            return Promise.all(keys.map(function (k) { return cstore.delete(k); }));
          })
          .catch(function () {})
      );
    }

    return Promise.all(tasks).then(function () {
      try { localStorage.setItem(FLAG, MY_VERSION); } catch (e) {}
      // 带时间戳重载，绕过一切中间缓存
      var u = location.href.split('#')[0].split('?')[0];
      location.replace(u + '?_heal=' + Date.now() + (location.hash || ''));
    }).catch(function () {
      try { localStorage.setItem(FLAG, MY_VERSION); } catch (e) {}
    });
  }

  function check() {
    var pageVer = getPageVersion();
    var lastHealed = '';
    try { lastHealed = localStorage.getItem(FLAG) || ''; } catch (e) {}

    // 情况 C（最重要）：样式表实际未加载 → 立即自愈
    //   判据：document.styleSheets 里没有 style.css，或有但规则数异常少
    var cssOk = false;
    try {
      for (var i = 0; i < document.styleSheets.length; i++) {
        var s = document.styleSheets[i];
        if (s.href && s.href.indexOf('style.css') >= 0) {
          var n = 0;
          try { n = s.cssRules ? s.cssRules.length : 0; } catch (e) { n = 0; }
          if (n > 150) { cssOk = true; }
        }
      }
    } catch (e) {}

    if (!cssOk) {
      // CSS 未生效 = 铁证，不管标记，强制治愈一次（同一版本只治一次防死循环）
      if (lastHealed !== 'cssfail-' + MY_VERSION) {
        doHeal('css-not-loaded');
        try { localStorage.setItem(FLAG, 'cssfail-' + MY_VERSION); } catch (e) {}
        return;
      }
    }

    // 情况 A：页面版本落后于脚本版本 → 页面是旧的，治病
    if (pageVer && pageVer !== MY_VERSION && lastHealed !== MY_VERSION) {
      doHeal('page-version-mismatch:' + pageVer + '->' + MY_VERSION);
      return;
    }

    // 情况 B：页面读不到版本（被旧 SW 缓存替换）→ 也要治一次
    if (!pageVer && lastHealed !== MY_VERSION) {
      doHeal('page-version-missing');
      return;
    }
  }

  // DOM 就绪后检查（要读 body 的 data-app-ver）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', check);
  } else {
    check();
  }
})();

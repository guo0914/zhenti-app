/* ===== App 设置页（服务器地址配置）=====
 *
 * 触发方式：首页右上角「？」按钮旁边会多出一个「⚙」按钮
 * 或者在地址栏加 #/appsettings 直接进入
 */
(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function render() {
    var cur = (window.__API_BASE_GET__ && window.__API_BASE_GET__()) || '';
    var host = 'http://' + (location.hostname || '127.0.0.1') + ':8000';

    var html =
      '<div class="view">' +
      '  <div class="spread" style="margin-bottom:14px">' +
      '    <div><h1>应用设置</h1>' +
      '    <p class="sub">配置数据服务器，或使用完全离线的本地题库</p></div>' +
      '    <button class="btn" id="backHome">返回首页</button>' +
      '  </div>' +

      '  <div class="card pad" style="margin-bottom:14px">' +
      '    <h3 style="margin:0 0 4px">数据服务器地址</h3>' +
      '    <p class="sub" style="margin:0 0 12px">' +
      '      填你电脑上运行的服务器地址。手机和电脑在同一 WiFi 时可填局域网地址；' +
      '      装了内网穿透时填 https://xxx.trycloudflare.com 这种公网地址。' +
      '    </p>' +
      '    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">' +
      '      <input id="apiInput" type="text" value="' + esc(cur) + '"' +
      '        placeholder="例如 http://192.168.1.5:8000 或 https://xxx.trycloudflare.com"' +
      '        style="flex:1;min-width:260px;padding:10px 12px;border:1.5px solid #c5cddd;' +
      '        border-radius:10px;font-size:14px">' +
      '      <button class="btn primary" id="btnSave">保存</button>' +
      '      <button class="btn" id="btnTest">测试连接</button>' +
      '      <button class="btn" id="btnClear">清空（离线）</button>' +
      '    </div>' +
      '    <div id="testResult" class="tiny" style="min-height:20px"></div>' +
      '  </div>' +

      '  <div class="card pad" style="margin-bottom:14px">' +
      '    <h3 style="margin:0 0 8px">常见地址示例</h3>' +
      '    <div style="font-size:13px;line-height:2">' +
      '      <div>· 同一 WiFi，本机：<code>' + esc(host) + '</code></div>' +
      '      <div>· 同一 WiFi，局域网：<code>http://192.168.x.x:8000</code>（在电脑上运行 <code>ipconfig</code> 查看）</div>' +
      '      <div>· 任意网络：<code>https://xxx.trycloudflare.com</code>（电脑上运行「穿透.cmd」生成）</div>' +
      '    </div>' +
      '  </div>' +

      '  <div class="card pad">' +
      '    <h3 style="margin:0 0 8px">离线模式说明</h3>' +
      '    <div style="font-size:13px;line-height:1.9">' +
      '      <div>✓ 题库已内置在 App 中（约 19MB），无网络也能刷题</div>' +
      '      <div>✓ 作答记录保存在手机本地</div>' +
      '      <div>✗ 不填服务器时：无法跨设备同步进度、无法获取实时资讯</div>' +
      '    </div>' +
      '  </div>' +
      '</div>';

    var view = document.getElementById('view');
    if (!view) return;
    view.innerHTML = html;

    var input = document.getElementById('apiInput');
    var result = document.getElementById('testResult');

    document.getElementById('backHome').onclick = function () {
      location.hash = '#/home';
    };

    document.getElementById('btnSave').onclick = function () {
      var v = input.value.trim();
      if (v && !/^https?:\/\//i.test(v)) {
        result.innerHTML = '<span style="color:#dc2626">地址要以 http:// 或 https:// 开头</span>';
        return;
      }
      window.__API_BASE_SET__(v);
      result.innerHTML = '<span style="color:#16a34a">已保存：' +
        esc(v || '（离线模式）') + '</span>';
    };

    document.getElementById('btnClear').onclick = function () {
      window.__API_BASE_SET__('');
      input.value = '';
      result.innerHTML = '<span style="color:#d97706">已切换为离线模式（仅本地题库）</span>';
    };

    document.getElementById('btnTest').onclick = function () {
      var v = input.value.trim().replace(/\/+$/, '');
      if (!v) {
        result.innerHTML = '<span style="color:#dc2626">请先填地址</span>';
        return;
      }
      // 临时设置再测试
      var old = window.__API_BASE_GET__();
      window.__API_BASE_SET__(v);
      result.innerHTML = '测试中…';
      window.__API_TEST__(function (r) {
        if (r.ok) {
          result.innerHTML = '<span style="color:#16a34a">✓ ' + esc(r.msg) + '</span>';
        } else {
          // 测试失败则回滚，避免存了坏地址
          window.__API_BASE_SET__(old);
          input.value = old;
          result.innerHTML = '<span style="color:#dc2626">✗ ' + esc(r.msg) + '</span>' +
            '<br><span style="color:#666">已回滚到原设置。检查服务器是否运行、地址是否正确。</span>';
        }
      });
    };
  }

  // 注册路由
  window.__APP_SETTINGS_RENDER__ = render;

  // 拦截 hash 变化
  function watchHash() {
    if (location.hash === '#/appsettings') {
      setTimeout(render, 50);
    }
  }
  window.addEventListener('hashchange', watchHash);
  if (location.hash === '#/appsettings') setTimeout(render, 200);

  // 在首页加齿轮按钮
  function addGearButton() {
    var actions = document.querySelector('.top-actions');
    if (!actions || document.getElementById('appSettingsBtn')) return;
    var b = document.createElement('button');
    b.id = 'appSettingsBtn';
    b.className = 'btn sm';
    b.title = '应用设置';
    b.textContent = '⚙';
    b.onclick = function () {
      location.hash = '#/appsettings';
    };
    actions.insertBefore(b, actions.firstChild);
  }

  window.addEventListener('load', function () {
    setTimeout(addGearButton, 300);
    setTimeout(addGearButton, 1200);
  });
})();

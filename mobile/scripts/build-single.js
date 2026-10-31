#!/usr/bin/env node
/**
 * build-single.js —— 打包成单个离线 HTML 文件
 *
 * 关键经验（都是踩坑得来的）：
 *
 *  1. 单块 <script> 内容过大（>1.6MB）会被浏览器截断 → 必须分块
 *  2. app.js 的 boot() 在闭包里，靠 DOMContentLoaded 启动；
 *     内联脚本执行时该事件已过，必须在 app.js 末尾直接调用 boot()
 *  3. boot() 第一件事是 bindChrome()，它要求页面存在
 *     #btnTheme / #sheetClose / #sheet / #btnMenu / #btnHelp / #scrim 等元素，
 *     少了任何一个都会抛 TypeError 导致中断 → 必须用真实骨架
 *  4. app.js 的 render() 里 await API.probe() 会卡 8 秒 → 必须中立化
 *
 * 用法：node scripts/build-single.js
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const SITE = path.join(ROOT, 'site');
const OUT = path.join(ROOT, 'dist-single');
const CHUNK_LIMIT = 1100000;

function log(m) { console.log('  ' + m); }
function read(rel) {
  const p = path.join(SITE, rel);
  return fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '';
}

console.log('='.repeat(62));
console.log('  打包单文件离线版');
console.log('='.repeat(62));

// ═══════════════ 1. CSS ═══════════════
const allCss = read('assets/style.css');
log('CSS: style.css  ' + Math.round(allCss.length / 1024) + ' KB');

// ═══════════════ 2. 数据块 ═══════════════
const shards = ['politics', 'common', 'verbal', 'quantity', 'judge', 'graph', 'data'];
const dataBlocks = [];
let totalData = 0;

for (const s of shards) {
  const p = path.join(SITE, 'data', 'zt', s + '.json');
  if (!fs.existsSync(p)) continue;
  const raw = fs.readFileSync(p, 'utf8');
  totalData += raw.length;
  dataBlocks.push({
    name: s + '.json',
    code: 'window.__EMBEDDED_DATA__=window.__EMBEDDED_DATA__||{};' +
          'window.__EMBEDDED_DATA__[' + JSON.stringify(s) + ']=' + raw + ';'
  });
  log('数据: ' + s + '.json  ' + (raw.length / 1024 / 1024).toFixed(2) + ' MB');
}

// 法律题库：按题目对象拆分
const lawPath = path.join(SITE, 'data', 'zt', 'law.js');
if (fs.existsSync(lawPath)) {
  const raw = fs.readFileSync(lawPath, 'utf8');
  totalData += raw.length;
  const m = raw.match(/window\.__LAW_QUESTIONS__\s*=\s*(\[[\s\S]*\])\s*;/);
  if (m) {
    const arr = m[1];
    log('法律题库  ' + (arr.length / 1024 / 1024).toFixed(2) + ' MB（拆分）');

    const objs = [];
    let depth = 0, start = -1, inStr = false, esc = false;
    for (let i = 0; i < arr.length; i++) {
      const ch = arr[i];
      if (inStr) {
        if (esc) esc = false;
        else if (ch === '\\') esc = true;
        else if (ch === '"') inStr = false;
        continue;
      }
      if (ch === '"') { inStr = true; continue; }
      if (ch === '{') { if (depth === 0) start = i; depth++; }
      else if (ch === '}') {
        depth--;
        if (depth === 0 && start >= 0) { objs.push(arr.slice(start, i + 1)); start = -1; }
      }
    }

    const parts = [];
    let cur = '';
    for (const o of objs) {
      if (cur.length && cur.length + o.length > CHUNK_LIMIT) { parts.push(cur); cur = ''; }
      cur += (cur ? ',' : '') + o;
    }
    if (cur) parts.push(cur);

    dataBlocks.push({
      name: 'law 1/' + parts.length,
      code: 'window.__LAW_QUESTIONS__=[' + parts[0] + '];'
    });
    for (let i = 1; i < parts.length; i++) {
      dataBlocks.push({
        name: 'law ' + (i + 1) + '/' + parts.length,
        code: 'window.__LAW_QUESTIONS__.push(' + parts[i] + ');'
      });
    }
    log('  ' + objs.length + ' 题 → ' + parts.length + ' 块');
  } else {
    dataBlocks.push({ name: 'law.js', code: raw });
  }
}

// 分类索引（ZLFX_ZHENTI 依赖 window.__ZHENTI__）
const zhentiJs = read('data/zhenti.js');
if (zhentiJs) {
  dataBlocks.push({ name: 'data/zhenti.js', code: zhentiJs });
  log('数据: data/zhenti.js  ' + Math.round(zhentiJs.length / 1024) + ' KB（分类索引）');
}

// 数据文件（data/news.js / shenlun.js 等，都是 window.XXX 赋值形式）
for (const f of ['data/news.js', 'data/shenlun.js', 'data/shenlun-2025-2026.js',
                 'data/cidian-curated.js', 'data/fanwen-curated.js']) {
  const c = read(f);
  if (!c) continue;
  dataBlocks.push({ name: f, code: c });
  log('数据: ' + f + '  ' + Math.round(c.length / 1024) + ' KB');
}

// 套卷索引
for (const f of ['zt-papers.json', 'zt-guokao-papers.json']) {
  const p = path.join(SITE, 'data', f);
  if (!fs.existsSync(p)) continue;
  const raw = fs.readFileSync(p, 'utf8');
  totalData += raw.length;
  const key = '__EMBEDDED_' + f.replace('.json', '').replace(/-/g, '_').toUpperCase() + '__';
  dataBlocks.push({ name: f, code: 'window.' + key + '=' + raw + ';' });
  log('数据: ' + f + '  ' + Math.round(raw.length / 1024) + ' KB');
}

// ═══════════════ 3. JS 模块（app.js 放最后）═══════════════
const jsFiles = [
  'assets/api.js',
  'assets/zhenti-v5.js',
  'assets/law-v5.js',
  'assets/papers-v5.js',
  'assets/news.js',
  'assets/shenlun.js',
  'assets/cidian.js',
  'assets/fanwen.js',
  'assets/layoutfix.js',
  'assets/app.js',
];

const jsBlocks = [];
for (const f of jsFiles) {
  let code = read(f);
  if (!code) continue;

  if (f === 'assets/app.js') {
    // 补丁：取代 DOMContentLoaded 启动，直接调用 boot()
    const oldLine = "document.addEventListener('DOMContentLoaded', boot);";
    if (code.indexOf(oldLine) >= 0) {
      code = code.replace(oldLine,
        "/* [offline-single] 立即启动 */\n" +
        "  if (window.ZLFX_API) {\n" +
        "    window.ZLFX_API.probe = function () { return Promise.resolve(false); };\n" +
        "    window.ZLFX_API.online = false;\n" +
        "  }\n" +
        "  setTimeout(function () {\n" +
        "    try { boot(); } catch (e) {\n" +
        "      console.error('[boot failed]', e);\n" +
        "      var v = document.getElementById('view');\n" +
        "      if (v) v.innerHTML = '<pre style=\"padding:20px;color:#c00;white-space:pre-wrap\">'\n" +
        "        + 'boot 失败: ' + (e && e.message ? e.message : e)\n" +
        "        + '\\n\\n' + (e && e.stack ? String(e.stack).slice(0, 800) : '') + '</pre>';\n" +
        "    }\n" +
        "  }, 60);\n" +
        "  document.addEventListener('DOMContentLoaded', function () { try { boot(); } catch (e) {} });");
      log('app.js: 已注入立即启动补丁');
    } else {
      log('app.js: 未找到启动语句');
    }
  }

  jsBlocks.push({ name: f, code: code });
  log('JS: ' + f + '  ' + Math.round(code.length / 1024) + ' KB');
}

// ═══════════════ 4. 离线垫片 ═══════════════
const shim = [
  '/* 离线数据垫片 */',
  '(function () {',
  '  var orig = window.fetch;',
  '  window.fetch = function (input, init) {',
  '    var url = typeof input === "string" ? input : (input && input.url) || "";',
  '    var m = url.match(/data\\/zt\\/([a-z0-9_-]+)\\.json/i);',
  '    if (m) {',
  '      var d = window.__EMBEDDED_DATA__ && window.__EMBEDDED_DATA__[m[1]];',
  '      if (d) return Promise.resolve(new Response(JSON.stringify(d),',
  '        { status: 200, headers: { "Content-Type": "application/json" } }));',
  '    }',
  '    if (/zt-papers\\.json/i.test(url) && window.__EMBEDDED_ZT_PAPERS__) {',
  '      return Promise.resolve(new Response(JSON.stringify(window.__EMBEDDED_ZT_PAPERS__),',
  '        { status: 200, headers: { "Content-Type": "application/json" } }));',
  '    }',
  '    if (/zt-guokao-papers\\.json/i.test(url) && window.__EMBEDDED_ZT_GUOKAO_PAPERS__) {',
  '      return Promise.resolve(new Response(JSON.stringify(window.__EMBEDDED_ZT_GUOKAO_PAPERS__),',
  '        { status: 200, headers: { "Content-Type": "application/json" } }));',
  '    }',
  '    if (/\\/api\\//.test(url)) return Promise.reject(new Error("offline"));',
  '    return orig.apply(window, arguments);',
  '  };',
  '})();'
].join('\n');

// ═══════════════ 5. 真实骨架（来自 site/index.html）═══════════════
const SHELL = `
<div id="app">
  <aside class="sidebar">
    <div class="brand">
      <div class="logo">测</div>
      <div class="brand-txt">
        <strong>行测刷题</strong>
        <span id="brandSub">离线版</span>
      </div>
    </div>
    <nav class="nav" id="nav">
      <a href="#/home" data-route="home"><i>▤</i><span>首页</span></a>
      <a href="#/cats" data-route="cats"><i>◈</i><span>分类刷题</span></a>
      <a href="#/wrong" data-route="wrong"><i>✦</i><span>错题本</span><b class="badge" id="badgeWrong">0</b></a>
      <a href="#/fav" data-route="fav"><i>★</i><span>我的收藏</span><b class="badge" id="badgeFav">0</b></a>
      <a href="#/search" data-route="search"><i>⌕</i><span>题库速查</span></a>
      <a href="#/stats" data-route="stats"><i>◔</i><span>学习统计</span></a>
      <a href="#/papers" data-route="papers"><i>▦</i><span>真题套卷</span></a>
      <a href="#/law" data-route="law"><i>⚖</i><span>法律专业</span></a>
    </nav>
    <div class="side-foot">
      <div class="user-chip" id="userChip"></div>
      <button class="ghost" id="btnTheme">🌗 深色</button>
      <div class="tiny" id="sideProgress">—</div>
    </div>
  </aside>

  <main class="main">
    <header class="topbar">
      <button class="icon-btn only-mobile" id="btnMenu">☰</button>
      <div class="crumb" id="crumb">首页</div>
      <div class="top-actions">
        <span class="timer hidden" id="timer">0:00</span>
        <button class="icon-btn" id="btnHelp" title="快捷键与帮助">?</button>
      </div>
    </header>
    <div class="view" id="view"></div>
  </main>
</div>
<div class="scrim" id="scrim"></div>

<div class="sheet hidden" id="sheet">
  <div class="sheet-box">
    <button class="sheet-x" id="sheetClose">×</button>
    <div id="sheetBody"></div>
  </div>
</div>

<div class="toast" id="toast"></div>
<div class="port-hint hidden" id="portHint"></div>
`;

// ═══════════════ 6. 拼装 ═══════════════
let scripts = '';
for (const b of dataBlocks) scripts += '<script>\n' + b.code + '\n</script>\n';
scripts += '<script>\n' + shim + '\n</script>\n';
for (const b of jsBlocks) scripts += '<script>\n/* ' + b.name + ' */\n' + b.code + '\n</script>\n';

const html = [
  '<!DOCTYPE html>',
  '<html lang="zh-CN">',
  '<head>',
  '<meta charset="utf-8">',
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover, user-scalable=no">',
  '<meta name="apple-mobile-web-app-capable" content="yes">',
  '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
  '<meta name="apple-mobile-web-app-title" content="行测刷题">',
  '<meta name="theme-color" content="#4f46e5">',
  '<title>行测刷题 · 离线版</title>',
  '<style>',
  allCss,
  'body{padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}',
  '.sidebar{padding-top:env(safe-area-inset-top)}',
  '*{-webkit-touch-callout:none}',
  'input,textarea,.txt,.opt-cell,.stem{-webkit-user-select:text;user-select:text}',
  'html{-webkit-text-size-adjust:100%}',
  '</style>',
  '</head>',
  '<body>',
  SHELL,
  scripts,
  '</body>',
  '</html>'
].join('\n');

if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });
const outPath = path.join(OUT, '行测刷题-离线版.html');
fs.writeFileSync(outPath, html, 'utf8');

const st = fs.statSync(outPath);
const maxBlock = Math.max.apply(null,
  dataBlocks.map(b => b.code.length).concat(jsBlocks.map(b => b.code.length)));

console.log('');
console.log('='.repeat(62));
log('输出: ' + outPath);
log('大小: ' + (st.size / 1024 / 1024).toFixed(1) + ' MB');
log('数据: ' + (totalData / 1024 / 1024).toFixed(1) + ' MB');
log('script 块: ' + (dataBlocks.length + jsBlocks.length + 1));
log('最大块: ' + Math.round(maxBlock / 1024) + ' KB');
console.log('='.repeat(62));

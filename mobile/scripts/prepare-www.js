#!/usr/bin/env node
/**
 * prepare-www.js
 * 把 ../site 复制成 www/，并做 App 化改造：
 *
 *  1. 复制静态资源（排除与 App 无关的调试页）
 *  2. 改写 index.html：
 *       - 注入 App 专用样式（安全区、禁用文本选择放大等）
 *       - 注入 API 基址配置（默认走公网地址，可在 App 内设置）
 *       - 移除 Service Worker 注册（App 内不需要，且会干扰更新）
 *  3. 生成 app-config.js，提供 <meta> 或 localStorage 的服务器地址
 *
 * 用法：node scripts/prepare-www.js [--api=https://xxx.trycloudflare.com]
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.resolve(ROOT, '..', 'site');
const DEST = path.resolve(ROOT, 'www');

// 从命令行取 API 基址
const apiArg = process.argv.find(a => a.startsWith('--api='));
const API_BASE = apiArg ? apiArg.split('=')[1] : '';

// 不复制到 App 的文件（调试用）
const SKIP = ['diag.html', 'minimal.html', 'manifest.webmanifest'];

// 不复制到 App 的文件名模式（脚本备份、临时产物）
// site/data/zt/ 下每个分片都留了 6-10 个 *.bak，加起来约 40MB，绝不能进安装包
const SKIP_RE = [
  /\.bak$/,                        // foo.json.bak
  /\.json\.[a-z0-9]+bak$/,         // foo.json.explimgbak / foo.json.stemhtmlbak
  /\.bak\d+$/,                     // foo.bak1
  /~$/, /\.swp$/,                  // 编辑器临时文件
  /\.tmp$/, /\.orig$/, /\.rej$/,   // 其它临时产物
  /^_/                             // _check1.txt 之类的临时报告
];

function log(msg) { console.log('  ' + msg); }

function rmrf(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}

function copyDir(src, dest, stats) {
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const s = path.join(src, name);
    const d = path.join(dest, name);
    if (SKIP.includes(name)) continue;
    if (SKIP_RE.some(re => re.test(name))) {
      if (stats) stats.skipped.push(path.relative(SRC, s));
      continue;
    }
    const st = fs.statSync(s);
    if (st.isDirectory()) copyDir(s, d, stats);
    else fs.copyFileSync(s, d);
  }
}

function main() {
  console.log('='.repeat(60));
  console.log('  构建 www/（Capacitor 静态资源）');
  console.log('='.repeat(60));

  if (!fs.existsSync(SRC)) {
    console.error('找不到源目录：' + SRC);
    process.exit(1);
  }

  // 1) 复制
  rmrf(DEST);
  const stats = { skipped: [] };
  copyDir(SRC, DEST, stats);

  const count = fs.readdirSync(DEST, { recursive: true }).length;
  log('已复制 ' + SRC + ' → www/');
  if (stats.skipped.length) {
    log('已跳过 ' + stats.skipped.length + ' 个备份/临时文件（不进安装包）');
  }

  // 2) 改写 index.html
  const idxPath = path.join(DEST, 'index.html');
  let html = fs.readFileSync(idxPath, 'utf8');

  // 2.1 App 专用样式 + viewport 安全区
  const appStyle = `
<!-- ===== iOS 壳应用注入 ===== -->
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover, user-scalable=no" />
<style id="app-inject">
  /* iOS 安全区：避开刘海和底部横条 */
  body { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }
  .sidebar { padding-top: env(safe-area-inset-top); }
  /* 禁用长按选中与放大，接近原生 App 手感 */
  * { -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; }
  /* 但输入框和选项文字要允许选中 */
  input, textarea, .txt, .opt-cell, .stem { -webkit-user-select: text; user-select: text; }
  /* 禁止双击缩放 */
  html { -webkit-text-size-adjust: 100%; touch-action: manipulation; }
  /* 滚动回弹 */
  body { overscroll-behavior-y: contain; }
</style>
`;
  // 替换原有 viewport（避免重复）
  html = html.replace(/<meta name="viewport"[^>]*>/, '');
  html = html.replace(/<head[^>]*>/i, function (m) { return m + appStyle; });

  // 2.2 注入 API 基址配置（在 app.js 之前）
  const apiConfig = `
<script>
/* 服务器地址（App 内可通过「设置」修改，存 localStorage） */
window.__API_BASE__ = (function () {
  try {
    var saved = localStorage.getItem('zlfx.apiBase');
    if (saved) return saved;
  } catch (e) {}
  return ${JSON.stringify(API_BASE)};
})();
</script>
`;
  html = html.replace(
    /<script src="assets\/app\.js/,
    apiConfig + '<script src="assets/app.js'
  );

  // 2.3 移除 Service Worker 注册（App 内自带完整资源，SW 会导致更新问题）
  html = html.replace(
    /if\s*\(\s*'serviceWorker'\s*in\s*navigator\s*\)[\s\S]*?\}\s*\)\s*\(\s*\)/g,
    '/* App 内不注册 Service Worker */'
  );
  // 兜底：干掉 navigator.serviceWorker.register 调用
  html = html.replace(/navigator\.serviceWorker\.register[\s\S]*?;\s*/g, '/* SW disabled in app */\n');

  fs.writeFileSync(idxPath, html, 'utf8');
  log('已改写 index.html（注入 iOS 样式 + API 配置 + 禁用 SW）');

  // 3) 生成 app-config.js —— 供前端读取服务器地址
  const cfg = `
/* 由 prepare-www.js 生成，不要手工编辑 */
window.__APP_CONFIG__ = {
  apiBase: ${JSON.stringify(API_BASE)},
  isNative: true,
  platform: 'capacitor',
  buildAt: ${JSON.stringify(new Date().toISOString())}
};
`;
  fs.writeFileSync(path.join(DEST, 'app-config.js'), cfg, 'utf8');
  log('已生成 app-config.js');

  // 3.5) 复制 App 扩展脚本（API 基址注入 + 设置页）
  const extras = path.resolve(ROOT, 'www-extras');
  let extraFiles = [];
  if (fs.existsSync(extras)) {
    for (const name of fs.readdirSync(extras)) {
      if (!name.endsWith('.js')) continue;
      fs.copyFileSync(path.join(extras, name), path.join(DEST, 'assets', name));
      extraFiles.push(name);
    }
    log('已复制扩展脚本：' + extraFiles.join(', '));
  }

  // 4) 在 index.html 里引用扩展脚本
  let html2 = fs.readFileSync(idxPath, 'utf8');

  // 4.1 app-config.js 放最前（提供构建期配置）
  if (!html2.includes('app-config.js')) {
    html2 = html2.replace(/<head[^>]*>/i, function (m) {
      return m + '\n<script src="app-config.js"></script>';
    });
    log('已引用 app-config.js');
  }

  // 4.2 api-base.js 紧随其后（必须早于 api.js 等所有业务脚本）
  if (!html2.includes('api-base.js')) {
    html2 = html2.replace(
      /<script src="app-config\.js"><\/script>/,
      '<script src="app-config.js"></script>\n' +
      '<script src="assets/api-base.js"></script>'
    );
    log('已引用 api-base.js（API 基址注入）');
  }

  // 4.3 app-settings.js 放最后（依赖所有业务脚本已就绪）
  if (!html2.includes('app-settings.js')) {
    html2 = html2.replace(/<\/body>/i,
      '<script src="assets/app-settings.js"></script>\n</body>');
    log('已引用 app-settings.js（设置页）');
  }

  if (html2 !== fs.readFileSync(idxPath, 'utf8')) {
    fs.writeFileSync(idxPath, html2, 'utf8');
  }

  // 5) 校验
  const finalHtml = fs.readFileSync(idxPath, 'utf8');
  console.log('');
  console.log('校验：');
  console.log('  viewport 含 viewport-fit: ' + /viewport-fit=cover/.test(finalHtml));
  console.log('  API 基址: ' + (API_BASE || '(未设置，App 内可配)'));
  console.log('  已禁用 SW: ' + (!finalHtml.includes('navigator.serviceWorker.register')));
  console.log('  www/ 文件数: ' + fs.readdirSync(DEST, { recursive: true }).length);
  console.log('');
  console.log('完成。下一步：npx cap sync');
}

main();

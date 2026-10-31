#!/usr/bin/env node
/**
 * verify-www.js —— 打包产物自检
 *
 * 检查 www/ 是否满足 App 运行条件：
 *  1. index.html 存在且含必要脚本
 *  2. API 基址注入脚本在最前面
 *  3. Service Worker 已禁用
 *  4. iOS 安全区样式已注入
 *  5. 题库数据完整（各科目分片齐全）
 *  6. 无遗留的调试页面
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const WWW = path.resolve(ROOT, 'www');

let pass = 0, fail = 0, warn = 0;

function ok(msg) { console.log('  ✓ ' + msg); pass++; }
function bad(msg) { console.log('  ✗ ' + msg); fail++; }
function wrn(msg) { console.log('  ⚠ ' + msg); warn++; }

function exists(rel) { return fs.existsSync(path.join(WWW, rel)); }
function read(rel) { return fs.readFileSync(path.join(WWW, rel), 'utf8'); }

console.log('='.repeat(62));
console.log('  www/ 打包产物自检');
console.log('='.repeat(62));

// ── 1. 基础文件 ──
console.log('\n[1] 基础文件');
if (exists('index.html')) ok('index.html 存在');
else bad('index.html 缺失');

const html = exists('index.html') ? read('index.html') : '';

// ── 2. 脚本注入顺序 ──
console.log('\n[2] 脚本注入');
const posConfig = html.indexOf('app-config.js');
const posApiBase = html.indexOf('api-base.js');
const posAppJs = html.indexOf('app.js');
const posSettings = html.indexOf('app-settings.js');

if (posConfig >= 0) ok('app-config.js 已引用'); else bad('app-config.js 未引用');
if (posApiBase >= 0) ok('api-base.js 已引用'); else bad('api-base.js 未引用');
if (posSettings >= 0) ok('app-settings.js 已引用'); else bad('app-settings.js 未引用');

// api-base 必须在 app.js 之前
if (posApiBase >= 0 && posAppJs >= 0) {
  if (posApiBase < posAppJs) ok('api-base.js 早于 app.js（顺序正确）');
  else bad('api-base.js 晚于 app.js，API 拦截会失效');
}

// ── 3. Service Worker ──
console.log('\n[3] Service Worker');
if (!html.includes('navigator.serviceWorker.register')) ok('SW 注册已移除');
else wrn('仍存在 SW 注册代码');

// ── 4. iOS 适配 ──
console.log('\n[4] iOS 适配');
if (html.includes('viewport-fit=cover')) ok('viewport 含 viewport-fit=cover（刘海适配）');
else bad('缺少 viewport-fit=cover');

if (html.includes('safe-area-inset')) ok('已注入安全区 padding');
else wrn('未注入安全区 padding');

if (html.includes('user-scalable=no')) ok('已禁用用户缩放');
else wrn('未禁用用户缩放');

if (html.includes('-webkit-touch-callout')) ok('已禁用长按菜单');
else wrn('未禁用长按菜单');

if (html.includes('apple-mobile-web-app-capable')) ok('含 iOS WebApp meta');
else wrn('缺少 iOS WebApp meta');

// ── 5. 题库数据完整性 ──
console.log('\n[5] 题库数据');
// 行测 8 科是 .json 分片
const shards = ['politics', 'common', 'verbal', 'quantity', 'judge', 'graph', 'data', 'guokao'];
let missing = [];
for (const s of shards) {
  if (exists('data/zt/' + s + '.json')) {
    const st = fs.statSync(path.join(WWW, 'data/zt/' + s + '.json'));
    ok(s + '.json  ' + (st.size / 1024 / 1024).toFixed(1) + ' MB');
  } else {
    missing.push(s);
  }
}
if (missing.length) bad('缺少分片：' + missing.join(', '));

// 法律题库以 .js 形式打包（不是 json）
if (exists('data/zt/law.js')) {
  const st = fs.statSync(path.join(WWW, 'data/zt/law.js'));
  ok('law.js  ' + (st.size / 1024 / 1024).toFixed(1) + ' MB（法律题库）');
} else {
  bad('缺少 data/zt/law.js（法律题库）');
}

// 法律索引
if (exists('data/zt/zt-law-index.json')) ok('zt-law-index.json 存在');
else wrn('zt-law-index.json 缺失');

for (const f of ['zt-papers.json', 'zt-guokao-papers.json']) {
  if (exists('data/' + f)) ok(f + ' 存在');
  else wrn(f + ' 缺失（套卷功能可能不可用）');
}

// ── 6. 调试页面清理 ──
console.log('\n[6] 调试页面');
for (const f of ['diag.html', 'minimal.html']) {
  if (exists(f)) bad(f + ' 仍在包内（应排除）');
  else ok(f + ' 已排除');
}

// ── 7. 扩展脚本 ──
console.log('\n[7] App 扩展脚本');
for (const f of ['assets/api-base.js', 'assets/app-settings.js']) {
  if (exists(f)) {
    const st = fs.statSync(path.join(WWW, f));
    ok(f + '  ' + Math.round(st.size / 1024) + ' KB');
  } else {
    bad(f + ' 缺失');
  }
}

// ── 8. 体积 ──
console.log('\n[8] 包体积');
const all = fs.readdirSync(WWW, { recursive: true })
  .map(f => path.join(WWW, f))
  .filter(f => fs.statSync(f).isFile());
const total = all.reduce((s, f) => s + fs.statSync(f).size, 0);
const mb = total / 1024 / 1024;
ok(all.length + ' 个文件，共 ' + mb.toFixed(1) + ' MB');
if (mb > 200) wrn('体积偏大，iOS 安装包会超过 100MB，建议压缩图片');
else ok('体积在合理范围');

// ── 汇总 ──
console.log('\n' + '='.repeat(62));
console.log('  通过 ' + pass + ' 项，失败 ' + fail + ' 项，警告 ' + warn + ' 项');
console.log('='.repeat(62));

if (fail > 0) {
  console.log('\n有失败项，需修复后再打包。');
  process.exit(1);
} else {
  console.log('\n全部关键项通过，可以进入 Xcode 打包。');
}

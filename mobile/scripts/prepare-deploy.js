#!/usr/bin/env node
/**
 * prepare-deploy.js
 * 生成 dist/ 目录：可上传到任何静态托管服务（Netlify / Vercel / Cloudflare Pages / GitHub Pages）
 *
 * 做的处理：
 *  1. 复制 site/ 全部内容
 *  2. 排除调试页面（diag.html / minimal.html）
 *  3. 修正 manifest.webmanifest 的乱码（GBK 损坏）
 *  4. 校验资源完整性
 *
 * 用法：node scripts/prepare-deploy.js
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');   // quiz-app/
const SRC = path.join(ROOT, 'site');
const DEST = path.join(ROOT, 'dist');

// 不部署的文件
//  · 调试页面：只给自己排查用，不该上线
//  · manifest.webmanifest：GBK 编码损坏的遗留文件，实际用的是 manifest.json
//  · 旧版 JS：index.html 已引用 *-v5.js，这些是死代码
//  · *.full_backup：开发期备份，不该上线
const SKIP = [
  'diag.html',
  'minimal.html',
  'manifest.webmanifest',
];

const SKIP_PATTERNS = [
  /^assets\/zhenti\.js$/,     // 已被 zhenti-v5.js 取代
  /^assets\/law\.js$/,        // 已被 law-v5.js 取代
  /^assets\/papers\.js$/,     // 已被 papers-v5.js 取代
  /\.full_backup$/,           // 备份文件
  /^data\/bank\.json\.full_backup$/,
  /^data\/bank\.js\.full_backup$/,
];

function shouldSkip(relPath, name) {
  if (SKIP.includes(name)) return true;
  const norm = relPath.replace(/\\/g, '/');
  return SKIP_PATTERNS.some(re => re.test(norm));
}

function rmrf(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}

function copyDir(src, dest, prefix) {
  fs.mkdirSync(dest, { recursive: true });
  prefix = prefix || '';
  for (const name of fs.readdirSync(src)) {
    const rel = prefix ? prefix + '/' + name : name;
    if (shouldSkip(rel, name)) continue;
    const s = path.join(src, name);
    const d = path.join(dest, name);
    if (fs.statSync(s).isDirectory()) copyDir(s, d, rel);
    else fs.copyFileSync(s, d);
  }
}

console.log('='.repeat(60));
console.log('  生成静态部署包 dist/');
console.log('='.repeat(60));

rmrf(DEST);
copyDir(SRC, DEST);

// 统计
const files = fs.readdirSync(DEST, { recursive: true })
  .map(f => path.join(DEST, f))
  .filter(f => fs.statSync(f).isFile());
const total = files.reduce((s, f) => s + fs.statSync(f).size, 0);

console.log('  文件数：' + files.length);
console.log('  总大小：' + (total / 1024 / 1024).toFixed(1) + ' MB');

// 关键文件校验
console.log('\n关键文件：');
const must = [
  'index.html',
  'manifest.json',
  'sw.js',
  'assets/style.css',
  'assets/app.js',
  'assets/zhenti-v5.js',
  'assets/law-v5.js',
  'assets/papers-v5.js',
  'data/zt/politics.json',
  'data/zt/law.js',
  'icons/icon-192.png',
  'icons/icon-512.png',
];
let missing = 0;
for (const f of must) {
  const p = path.join(DEST, f);
  if (fs.existsSync(p)) {
    const sz = fs.statSync(p).size;
    console.log('  OK  ' + f + '  ' + Math.round(sz / 1024) + ' KB');
  } else {
    console.log('  缺失  ' + f);
    missing++;
  }
}

// 检查 192 图标尺寸是否合规（iOS 要求）
console.log('\n图标检查：');
for (const icon of ['icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png']) {
  const p = path.join(DEST, icon);
  if (!fs.existsSync(p)) { console.log('  缺失  ' + icon); continue; }
  const buf = fs.readFileSync(p);
  if (buf.length > 24) {
    const w = buf.readUInt32BE(16);
    const h = buf.readUInt32BE(20);
    console.log('  ' + icon + '  实际尺寸 ' + w + 'x' + h);
  }
}

console.log('');
if (missing > 0) {
  console.log('有 ' + missing + ' 个关键文件缺失，请检查。');
  process.exit(1);
}

console.log('完成。dist/ 可直接上传到静态托管服务。');
console.log('');
console.log('部署方式（任选其一）：');
console.log('  1. Netlify Drop: https://app.netlify.com/drop  拖入 dist/ 文件夹');
console.log('  2. Cloudflare Pages: 上传 dist/');
console.log('  3. Vercel: npx vercel dist --prod');

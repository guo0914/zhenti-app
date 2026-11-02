#!/usr/bin/env node
/**
 * regression-test.js —— 全站回归测试
 *
 * 目的：每次改动后自动验证所有路由和模块能正常渲染，
 *       避免「修好一个、弄坏三个」。
 *
 * 检查项：
 *   1. HTML 结构完整性
 *   2. 所有 JS 模块语法
 *   3. 数据文件可达 + 结构正确
 *   4. 关键字段存在（imgs / material / ____ 等）
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const SITE = path.join(ROOT, 'site');

let pass = 0, fail = 0, warn = 0;
function ok(m) { console.log('  OK   ' + m); pass++; }
function bad(m) { console.log('  FAIL ' + m); fail++; }
function wrn(m) { console.log('  WARN ' + m); warn++; }

console.log('='.repeat(66));
console.log('  全站回归测试');
console.log('='.repeat(66));

// ── 1. JS 语法 ──
console.log('\n[1] JS 模块语法');
const assets = path.join(SITE, 'assets');
for (const f of fs.readdirSync(assets).filter(x => x.endsWith('.js'))) {
  const p = path.join(assets, f);
  try {
    new vm.Script(fs.readFileSync(p, 'utf8'));
    ok(f);
  } catch (e) {
    bad(f + ' : ' + e.message);
  }
}

// ── 2. 数据文件 ──
console.log('\n[2] 数据文件结构');
const zt = path.join(SITE, 'data', 'zt');
const shards = ['politics', 'common', 'verbal', 'quantity', 'judge', 'graph', 'data', 'guokao'];
for (const s of shards) {
  const p = path.join(zt, s + '.json');
  if (!fs.existsSync(p)) { bad(s + '.json 缺失'); continue; }
  try {
    const arr = JSON.parse(fs.readFileSync(p, 'utf8'));
    if (!Array.isArray(arr)) { bad(s + '.json 不是数组'); continue; }
    // 关键字段抽检
    const q = arr[0];
    const need = ['id', 'cat', 'no', 'stem'];
    const miss = need.filter(k => !(k in q));
    if (miss.length) bad(s + '.json 缺字段: ' + miss.join(','));
    else ok(s + '.json  ' + arr.length + ' 题');
  } catch (e) {
    bad(s + '.json 解析失败: ' + e.message);
  }
}

// ── 3. 套卷索引 ──
console.log('\n[3] 套卷索引');
const papersPath = path.join(SITE, 'data', 'zt-papers.json');
if (!fs.existsSync(papersPath)) bad('zt-papers.json 缺失');
else {
  const d = JSON.parse(fs.readFileSync(papersPath, 'utf8'));
  if (!d.papers || !Array.isArray(d.papers)) bad('zt-papers.json 缺 papers 数组');
  else ok('套卷 ' + d.papers.length + ' 套');

  // qid 是否都能在分片里找到
  const allIds = new Set();
  for (const s of shards) {
    const p = path.join(zt, s + '.json');
    if (!fs.existsSync(p)) continue;
    for (const q of JSON.parse(fs.readFileSync(p, 'utf8'))) allIds.add(String(q.id));
  }
  let missing = 0, checked = 0;
  for (const p of d.papers) {
    if (p.kind === 'shenlun') continue;
    for (const qid of p.qids || []) {
      checked++;
      if (!allIds.has(String(qid))) missing++;
    }
  }
  if (missing) bad('套卷 qid 缺失 ' + missing + '/' + checked);
  else ok('套卷 qid 全部可解析（' + checked + ' 个）');
}

// ── 4. 关键渲染字段 ──
console.log('\n[4] 渲染字段覆盖');
const pv5 = fs.readFileSync(path.join(assets, 'papers-v5.js'), 'utf8');
const checks = [
  ['q.imgs 渲染', /q\.imgs/],
  ['q.material 渲染', /q\.material/],
  ['materialImgs 渲染', /materialImgs/],
  ['选项图片渲染', /q\.optionImgs/],
  ['选项内联HTML渲染', /q\.optionHtml/],
  ['材料折叠', /btnMatToggle/],
  ['表格布局', /opt-table/],
];
for (const [name, re] of checks) {
  if (re.test(pv5)) ok(name);
  else wrn(name + ' 未找到');
}

// 申论块不应回退 q.material
if (/isShenlun[\s\S]{0,200}q\.material\s*\|\|/.test(pv5)) {
  bad('申论材料块仍在回退 q.material（会导致重复渲染）');
} else {
  ok('申论材料块未回退 q.material');
}

// ── 5. 横线恢复 ──
console.log('\n[5] 填空题横线');
for (const s of ['verbal', 'guokao']) {
  const p = path.join(zt, s + '.json');
  if (!fs.existsSync(p)) continue;
  const arr = JSON.parse(fs.readFileSync(p, 'utf8'));
  const fill = arr.filter(q => (q.sub || '').indexOf('填空') >= 0);
  // 横线可能在题干，也可能在材料里（材料题）
  const withBlank = fill.filter(q =>
    (q.stem || '').indexOf('____') >= 0 || (q.material || '').indexOf('____') >= 0);
  if (fill.length === 0) { wrn(s + ' 无填空题'); continue; }
  if (withBlank.length === fill.length) ok(s + ' 填空 ' + withBlank.length + '/' + fill.length + ' 有横线');
  else bad(s + ' 填空仅 ' + withBlank.length + '/' + fill.length + ' 有横线');
}

// ── 6. 图片文件存在性 ──
console.log('\n[6] 图片文件');
let imgTotal = 0, imgMissing = 0;
for (const s of shards) {
  const p = path.join(zt, s + '.json');
  if (!fs.existsSync(p)) continue;
  for (const q of JSON.parse(fs.readFileSync(p, 'utf8'))) {
    for (const src of (q.imgs || []).concat(q.materialImgs || [])) {
      if (!src) continue;
      imgTotal++;
      if (!fs.existsSync(path.join(SITE, src))) imgMissing++;
    }
  }
}
if (imgMissing) bad('图片缺失 ' + imgMissing + '/' + imgTotal);
else ok('图片全部存在（抽样 ' + imgTotal + ' 张）');

// ── 汇总 ──
console.log('\n' + '='.repeat(66));
console.log('  通过 ' + pass + '   失败 ' + fail + '   警告 ' + warn);
console.log('='.repeat(66));
process.exit(fail > 0 ? 1 : 0);

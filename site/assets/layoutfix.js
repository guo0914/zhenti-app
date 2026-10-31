/* ===== 运行时布局修正器 layoutfix.js =====
 *
 * 背景：
 *   用户浏览器（Edge + 150% 缩放）中，flex/grid/百分比宽度的计算不可靠，
 *   导致答题页的选项区横跨全屏、盖住侧栏。CSS 层面的各种尝试均无效。
 *
 * 做法：
 *   不信任 CSS 引擎的宽度计算，改用 JS 实测卡片宽度，
 *   然后把选项表格的宽度写成**固定的像素值**。
 *   像素值是硬约束，不受任何父级百分比计算影响。
 *
 * 触发时机：
 *   · DOM 变化（答题页每次切题都重建 DOM）
 *   · 窗口尺寸变化
 *   · 定时兜底（应对异步渲染）
 *
 * 开销：仅在检测到 .q-card 存在时执行，正常情况几乎零成本。
 */
(function () {
  'use strict';

  var FIX_ATTR = 'data-layoutfixed';

  function px(n) {
    return Math.max(0, Math.round(n)) + 'px';
  }

  // 找出可作为「宽度基准」的容器：题目卡片
  function findAnchor() {
    return document.querySelector('.q-card') ||
           document.querySelector('.card.pad') ||
           document.querySelector('.view');
  }

  function fix() {
    var anchor = findAnchor();
    if (!anchor) return;

    var ar = anchor.getBoundingClientRect();
    if (!ar.width || ar.width < 200) return;

    // 可用宽度：必须以「表格所在的那个 .options」为准。
    // 之前从 anchor.querySelector('.options') 取，但套卷页的 .options
    // 与 .card.pad 不是父子关系，导致算出的宽度偏大 40px，表格溢出。
    var tables0 = document.querySelectorAll('.opt-table');
    var optsEl = null;
    if (tables0.length) {
      optsEl = tables0[0].parentElement;
      // 若父级不是 .options，向上找
      while (optsEl && !optsEl.classList.contains('options') && optsEl !== document.body) {
        optsEl = optsEl.parentElement;
      }
    }
    var avail = ar.width;
    if (optsEl && optsEl !== document.body) {
      var orr = optsEl.getBoundingClientRect();
      if (orr.width > 100) avail = orr.width;
    } else {
      var bodyEl = anchor.querySelector('.q-body');
      if (bodyEl) {
        var bcs = getComputedStyle(bodyEl);
        var pl = parseFloat(bcs.paddingLeft) || 0;
        var pr = parseFloat(bcs.paddingRight) || 0;
        var bbr = bodyEl.getBoundingClientRect();
        if (bbr.width > 100) avail = bbr.width;
        else avail = ar.width - pl - pr;
      }
    }
    // 留 2px 余量，吸收亚像素误差
    avail = avail - 2;

    // 屏幕宽度兜底（防止在极小视口下算出怪值）
    var maxAllow = Math.min(avail, window.innerWidth - 40);
    if (maxAllow < 200) return;

    var tables = document.querySelectorAll('.opt-table');
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      var cur = t.getBoundingClientRect().width;

      // 只在「明显不对」时修正：超出可用宽度，或比可用宽度小太多
      if (Math.abs(cur - maxAllow) > 2) {
        t.style.width = px(maxAllow);
        t.style.maxWidth = px(maxAllow);
        t.style.tableLayout = 'fixed';
        t.setAttribute(FIX_ATTR, '1');
      }
    }

    // 同时限制 .options 容器，避免它自身撑宽
    var opts = document.querySelectorAll('.options');
    for (var j = 0; j < opts.length; j++) {
      var o = opts[j];
      var or = o.getBoundingClientRect();
      if (or.width > maxAllow + 2) {
        o.style.width = px(maxAllow);
        o.style.maxWidth = px(maxAllow);
      }
    }
  }

  // 节流：避免 MutationObserver 高频触发
  var pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    setTimeout(function () {
      pending = false;
      try { fix(); } catch (e) {}
    }, 60);
  }

  // 1) DOM 变化时修正（答题页切题会整块重建）
  if (window.MutationObserver) {
    var mo = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.addedNodes && m.addedNodes.length) { schedule(); return; }
      }
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  // 2) 窗口尺寸变化
  window.addEventListener('resize', schedule);

  // 3) 页面加载完成后修正
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', schedule);
  } else {
    schedule();
  }

  // 4) 定时兜底（应对延时渲染/异步数据）
  setTimeout(fix, 300);
  setTimeout(fix, 900);
  window.addEventListener('load', function () { setTimeout(fix, 200); });
})();

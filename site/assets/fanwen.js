/* =========================================================
   申论范文 · 单页应用
   数据: window.__FANWEN_CURATED__（精讲范文，带段评）
         window.__FANWEN_MINED__（自动抓取的时评范文）
   功能: 标签筛选 / 搜索 / 精读模式 / 结构拆解 / 收藏
   ========================================================= */
(function () {
  'use strict';

  var FW = window.ZLFX_FANWEN = {};
  var LS_FAV = 'zlfx.fanwen.favs';
  var LS_READ = 'zlfx.fanwen.read';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function getFavs() {
    try { return JSON.parse(localStorage.getItem(LS_FAV) || '[]'); } catch (e) { return []; }
  }
  function setFavs(a) { try { localStorage.setItem(LS_FAV, JSON.stringify(a)); } catch (e) {} }
  function toggleFav(id) {
    var f = getFavs(), i = f.indexOf(id);
    if (i >= 0) f.splice(i, 1); else f.push(id);
    setFavs(f); return i < 0;
  }
  function getRead() {
    try { return JSON.parse(localStorage.getItem(LS_READ) || '[]'); } catch (e) { return []; }
  }
  function markRead(id) {
    var a = getRead();
    if (a.indexOf(id) < 0) { a.push(id); try { localStorage.setItem(LS_READ, JSON.stringify(a)); } catch (e) {} }
  }

  /* 合并增补篇目（ext 系列在 data 里单独成文件，便于维护） */
  (function mergeExt() {
    var C = window.__FANWEN_CURATED__;
    if (!C || !C.articles) return;
    var pools = [
      window.__FANWEN_CURATED_EXT__,
      window.__FANWEN_CURATED_EXT2__,
      window.__FANWEN_CURATED_EXT3__,
      window.__FANWEN_CURATED_EXT4__
    ];
    var seen = {};
    C.articles.forEach(function (a) { seen[a.id] = true; });
    pools.forEach(function (pool) {
      if (!pool || !pool.articles) return;
      pool.articles.forEach(function (a) {
        if (!seen[a.id]) { seen[a.id] = true; C.articles.push(a); }
      });
    });
    C.total = C.articles.length;
  })();

  function curated() {
    var d = window.__FANWEN_CURATED__ || { articles: [] };
    return d.articles || [];
  }
  function bingwen() {
    var d = window.__FANWEN_BINGWEN__ || { articles: [] };
    return d.articles || [];
  }
  function duojie() {
    var d = window.__FANWEN_DUOJIE__ || { articles: [] };
    return d.articles || [];
  }
  function mined() {
    var d = window.__FANWEN_MINED__ || { articles: [] };
    return d.articles || [];
  }

  /* 时评范文 2.3MB，按需加载：只在切到「时评范文」时才拉取 */
  var _minedLoaded = false, _minedLoading = false, _minedError = '';
  function loadMined(cb) {
    if (_minedLoaded || window.__FANWEN_MINED__) { _minedLoaded = true; cb && cb(); return; }
    if (_minedLoading) return;
    _minedLoading = true;
    var s = document.createElement('script');
    s.src = 'data/fanwen-mined.js';
    s.onload = function () {
      _minedLoaded = true; _minedLoading = false; cb && cb();
    };
    s.onerror = function () {
      _minedLoading = false;
      _minedError = '时评范文数据加载失败';
      cb && cb();
    };
    document.body.appendChild(s);
  }

  function countWords(paras) {
    var s = (paras || []).map(function (p) { return typeof p === 'string' ? p : (p.text || ''); }).join('');
    return s.replace(/\s/g, '').length;
  }

  FW._state = { tab: 'curated', topic: 'all', q: '', fav: false, page: 1, src: 'all' };

  /* ═══════════════ 列表页 ═══════════════ */
  FW.view = function () {
    var v = document.getElementById('view');
    if (!v) return;
    var st = FW._state;

    // 时评范文按需加载
    if (st.tab === 'mined' && !window.__FANWEN_MINED__ && !_minedError) {
      loadMined(function () { FW.view(); });
      v.innerHTML = '<div class="empty"><div class="big">⏳</div><p>正在加载时评范文…</p>' +
        '<p class="tiny">共 320 篇，首次加载约 2MB</p></div>';
      return;
    }

    var C = curated(), M = mined();
    var BW = bingwen(), DJ = duojie();
    var favs = getFavs(), read = getRead();

    // 合并话题统计
    var topics = {};
    C.forEach(function (a) { if (a.topic) topics[a.topic] = (topics[a.topic] || 0) + 1; });
    M.forEach(function (a) { (a.topics || []).forEach(function (t) { topics[t] = (topics[t] || 0) + 1; }); });

    v.innerHTML = [
      '<div class="spread" style="margin-bottom:14px">',
      '  <div><h1>申论范文</h1>',
      '    <p class="sub">精讲 ' + C.length + ' 篇 · 病文批改 ' + BW.length + ' 篇 · 一题多解 ' + DJ.length + ' 篇 · 时评 ' + M.length + ' 篇</p></div>',
      '  <div class="row" style="gap:6px">',
      '    <button class="btn sm' + (st.fav ? ' primary' : '') + '" id="fwFav">⭐ 收藏 ' + favs.length + '</button>',
      '  </div>',
      '</div>',

      '<div class="card pad" style="margin-bottom:12px">',
      '  <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:10px">',
      '    <button class="btn sm' + (st.tab === 'curated' ? ' primary' : '') + '" data-tab="curated">📝 精讲范文 ' + C.length + '</button>',
      '    <button class="btn sm' + (st.tab === 'bingwen' ? ' primary' : '') + '" data-tab="bingwen">🔧 病文批改 ' + BW.length + '</button>',
      '    <button class="btn sm' + (st.tab === 'duojie' ? ' primary' : '') + '" data-tab="duojie">🔀 一题多解 ' + DJ.length + '</button>',
      '    <button class="btn sm' + (st.tab === 'mined' ? ' primary' : '') + '" data-tab="mined">📰 时评范文 ' + M.length + '</button>',
      '  </div>',
      '  <input id="fwSearch" placeholder="🔍 搜索范文标题、内容、话题…" value="' + esc(st.q) + '"',
      '    style="width:100%;box-sizing:border-box;padding:9px 14px;border:1px solid var(--line);border-radius:8px;font-size:14px;background:var(--bg-1);color:var(--text-1)">',
      '  <div id="fwTopics" style="margin-top:10px"></div>',
      '</div>',

      '<div id="fwBody"></div>'
    ].join('');

    $$('[data-tab]', v).forEach(function (b) {
      b.onclick = function () {
        st.tab = b.dataset.tab;
        st.q = ''; st.topic = 'all'; st.page = 1; st.src = 'all';
        FW.view();
      };
    });
    var fb = $('#fwFav', v);
    if (fb) fb.onclick = function () { st.fav = !st.fav; st.page = 1; FW.view(); };

    var se = $('#fwSearch', v);
    if (se) {
      var timer = null;
      se.oninput = function () {
        clearTimeout(timer);
        timer = setTimeout(function () { st.q = se.value.trim(); st.page = 1; FW.paintBody(); }, 300);
      };
    }

    FW.paintTopics(topics);
    FW.paintBody();
  };

  FW.paintTopics = function (topics) {
    var box = document.getElementById('fwTopics');
    if (!box) return;
    var st = FW._state;
    var keys = Object.keys(topics).sort(function (a, b) { return topics[b] - topics[a]; });
    if (!keys.length) { box.innerHTML = ''; return; }

    var h = ['<div class="tiny" style="margin-bottom:6px">按话题</div>',
      '<div class="row" style="gap:5px;flex-wrap:wrap">',
      '<button class="btn sm' + (st.topic === 'all' ? ' primary' : '') + '" data-tp="all">全部</button>'];
    keys.forEach(function (k) {
      h.push('<button class="btn sm' + (st.topic === k ? ' primary' : '') + '" data-tp="' + esc(k) + '">' +
        esc(k) + ' <span class="tiny">' + topics[k] + '</span></button>');
    });
    h.push('</div>');
    box.innerHTML = h.join('');
    $$('[data-tp]', box).forEach(function (b) {
      b.onclick = function () { st.topic = b.dataset.tp; FW.paintBody(); };
    });
  };

  FW.paintBody = function () {
    var box = document.getElementById('fwBody');
    if (!box) return;
    var st = FW._state;

    // 病文批改 / 一题多解 独立渲染
    if (st.tab === 'bingwen') return paintBingwen(box);
    if (st.tab === 'duojie') return paintDuojie(box);

    var list = st.tab === 'curated' ? curated() : mined();
    var favs = getFavs(), read = getRead();

    if (st.fav) list = list.filter(function (a) { return favs.indexOf(a.id || a.url) >= 0; });
    if (st.topic !== 'all') {
      list = list.filter(function (a) {
        if (st.tab === 'curated') return a.topic === st.topic;
        return (a.topics || []).indexOf(st.topic) >= 0;
      });
    }
    if (st.q) {
      var q = st.q.toLowerCase();
      list = list.filter(function (a) {
        var text = (a.title || '') + ' ' + (a.subtitle || '') + ' ' +
          (a.paras || []).map(function (p) { return typeof p === 'string' ? p : (p.text || ''); }).join(' ');
        return text.toLowerCase().indexOf(q) >= 0;
      });
    }

    if (!list.length) {
      box.innerHTML = '<div class="empty"><div class="big">📄</div><p>' +
        (st.fav ? '还没有收藏范文' : '没有匹配的范文') + '</p></div>';
      return;
    }

    if (st.tab === 'curated') {
      box.innerHTML = '<div class="tiny" style="margin-bottom:8px">共 ' + list.length + ' 篇 · 点击展开全文精读</div>' +
        list.map(function (a) {
          var isFav = favs.indexOf(a.id) >= 0;
          var wc = countWords(a.paras);
          return [
            '<div class="card pad" style="margin-bottom:10px">',
            '  <div class="spread" style="margin-bottom:8px">',
            '    <div style="flex:1;min-width:0">',
            '      <div style="font-weight:700;font-size:16px;margin-bottom:3px">' + esc(a.title) + '</div>',
            '      <div class="tiny" style="color:var(--text-2);margin-bottom:6px">' + esc(a.subtitle || '') + '</div>',
            '      <div class="row" style="gap:5px;flex-wrap:wrap">',
            '        <span class="pill ok" style="font-size:11px">' + esc(a.level) + ' ' + esc(a.score) + '</span>',
            '        <span class="pill" style="font-size:11px">' + esc(a.type) + '</span>',
            '        <span class="pill" style="font-size:11px">' + esc(a.topic) + '</span>',
            '        <span class="tiny">' + wc + ' 字 · ' + (a.paras || []).length + ' 段</span>',
            '      </div>',
            '    </div>',
            '    <div class="row" style="gap:4px;flex-shrink:0">',
            '      <button class="btn sm" data-fav="' + esc(a.id) + '" style="padding:2px 7px">' + (isFav ? '★' : '☆') + '</button>',
            '      <button class="btn sm primary" data-read="' + esc(a.id) + '">精读</button>',
            '    </div>',
            '  </div>',
            '  <div class="tiny" style="line-height:1.7;color:var(--text-2)">结构：' +
                 (a.structure || []).map(function (s) { return esc(s); }).join(' → ') + '</div>',
            '</div>'
          ].join('');
        }).join('');

      $$('[data-read]', box).forEach(function (b) {
        b.onclick = function () { FW.detail(b.dataset.read, 'curated'); };
      });
      $$('[data-fav]', box).forEach(function (b) {
        b.onclick = function (e) {
          e.stopPropagation();
          var now = toggleFav(b.dataset.fav);
          b.textContent = now ? '★' : '☆';
          var fb = document.getElementById('fwFav');
          if (fb) fb.textContent = '⭐ 收藏 ' + getFavs().length;
          if (window.toast) window.toast(now ? '已收藏' : '已取消');
        };
      });
    } else {
      // 时评范文列表（分页 + 来源筛选）
      var PAGE = 30;
      var pg = FW._state.page || 1;
      var srcFilter = FW._state.src || 'all';
      var allMined = mined();

      // 来源统计
      var srcCount = {};
      allMined.forEach(function (a) { srcCount[a.source] = (srcCount[a.source] || 0) + 1; });

      if (srcFilter !== 'all') {
        list = list.filter(function (a) { return a.source === srcFilter; });
      }

      var pages = Math.max(1, Math.ceil(list.length / PAGE));
      if (pg > pages) pg = 1;
      var slice = list.slice((pg - 1) * PAGE, pg * PAGE);

      var bar = ['<div class="row" style="gap:5px;flex-wrap:wrap;margin-bottom:10px">',
        '<button class="btn sm' + (srcFilter === 'all' ? ' primary' : '') + '" data-src="all">全部 ' + allMined.length + '</button>'];
      Object.keys(srcCount).sort(function (a, b) { return srcCount[b] - srcCount[a]; }).forEach(function (s) {
        bar.push('<button class="btn sm' + (srcFilter === s ? ' primary' : '') + '" data-src="' + esc(s) + '">' +
          esc(s.replace('求是网 · ', '').replace('人民网 · ', '')) + ' <span class="tiny">' + srcCount[s] + '</span></button>');
      });
      bar.push('</div>');

      var pager = '';
      if (pages > 1) {
        pager = ['<div class="row" style="gap:6px;justify-content:center;margin-top:14px">',
          '<button class="btn sm" data-pg="' + (pg - 1) + '"' + (pg <= 1 ? ' disabled' : '') + '>上一页</button>',
          '<span class="tiny" style="align-self:center">' + pg + ' / ' + pages + '</span>',
          '<button class="btn sm" data-pg="' + (pg + 1) + '"' + (pg >= pages ? ' disabled' : '') + '>下一页</button>',
          '</div>'].join('');
      }

      box.innerHTML = bar.join('') +
        '<div class="tiny" style="margin-bottom:8px">共 ' + list.length + ' 篇' +
        (pages > 1 ? ' · 第 ' + pg + '/' + pages + ' 页' : '') + ' · 点击展开全文</div>' +
        '<div class="rows">' + slice.map(function (a, i) {
          var isFav = favs.indexOf(a.url) >= 0;
          var srcShort = (a.source || '').replace('求是网 · ', '').replace('人民网 · ', '');
          return [
            '<div class="rowitem" style="cursor:pointer;align-items:flex-start" data-open="' + i + '">',
            '  <span class="rno" style="margin-top:2px">' + (a.date ? a.date.slice(4, 6) + '/' + a.date.slice(6) : '') + '</span>',
            '  <div style="flex:1;min-width:0">',
            '    <div class="rtxt" style="margin-bottom:3px;line-height:1.5">' + esc(a.title) + '</div>',
            '    <span class="tiny">' + esc(srcShort) + ' · ' + a.words + ' 字' +
                 ((a.topics || []).length ? ' · ' + a.topics.slice(0, 2).map(function (t) { return esc(t); }).join(' / ') : '') +
            '    </span>',
            '  </div>',
            '  <div class="row" style="gap:4px;flex-shrink:0">',
            '    <button class="btn sm" data-fav="' + esc(a.url) + '" style="padding:2px 7px">' + (isFav ? '★' : '☆') + '</button>',
            '  </div>',
            '</div>'
          ].join('');
        }).join('') + '</div>' + pager;

      $$('[data-src]', box).forEach(function (b) {
        b.onclick = function () {
          FW._state.src = b.dataset.src;
          FW._state.page = 1;
          FW.paintBody();
        };
      });
      $$('[data-pg]', box).forEach(function (b) {
        b.onclick = function () {
          FW._state.page = parseInt(b.dataset.pg);
          FW.paintBody();
          box.scrollIntoView({ block: 'start', behavior: 'smooth' });
        };
      });

      $$('[data-open]', box).forEach(function (el) {
        el.onclick = function (e) {
          if (e.target.dataset.fav) return;
          var a = slice[parseInt(el.dataset.open)];
          showInline(el, a);
        };
      });
      $$('[data-fav]', box).forEach(function (b) {
        b.onclick = function (e) {
          e.stopPropagation();
          var now = toggleFav(b.dataset.fav);
          b.textContent = now ? '★' : '☆';
          var fb = document.getElementById('fwFav');
          if (fb) fb.textContent = '⭐ 收藏 ' + getFavs().length;
          if (window.toast) window.toast(now ? '已收藏' : '已取消');
        };
      });
    }
  };

  /* ═══════════════ 精读模式（精讲范文） ═══════════════ */
  FW.detail = function (id, kind) {
    var list = kind === 'curated' ? curated() : mined();
    var a = null;
    for (var i = 0; i < list.length; i++) {
      if ((list[i].id || list[i].url) === id) { a = list[i]; break; }
    }
    if (!a) return;

    markRead(id);

    var v = document.getElementById('view');
    if (!v) return;
    var wc = countWords(a.paras);
    var showNote = true;

    function render() {
      v.innerHTML = [
        '<div class="spread" style="margin-bottom:14px">',
        '  <div><h1 style="font-size:22px;margin-bottom:4px">' + esc(a.title) + '</h1>',
        '    <p class="sub">' + esc(a.subtitle || '') + '</p></div>',
        '  <div class="row" style="gap:6px">',
        '    <button class="btn sm' + (showNote ? ' primary' : '') + '" id="fwToggleNote">💬 段评</button>',
        '    <button class="btn sm" id="fwBack">← 返回列表</button>',
        '  </div>',
        '</div>',

        '<div class="card pad" style="margin-bottom:12px">',
        '  <div class="row" style="gap:6px;flex-wrap:wrap">',
        '    <span class="pill ok">' + esc(a.level) + ' ' + esc(a.score) + '</span>',
        '    <span class="pill">' + esc(a.type) + '</span>',
        '    <span class="pill">' + esc(a.topic) + '</span>',
        '    <span class="tiny" style="align-self:center">' + wc + ' 字</span>',
        '  </div>',
        (a.structure || []).length
          ? '  <div class="tiny" style="margin-top:10px;line-height:1.8"><b>结构脉络：</b>' +
            a.structure.map(function (s, i) {
              return '<span style="color:var(--brand)">' + esc(s) + '</span>' +
                (i < a.structure.length - 1 ? ' → ' : '');
            }).join('') + '</div>'
          : '',
        '</div>',

        '<div id="fwParas">',
        (a.paras || []).map(function (p, i) {
          var text = typeof p === 'string' ? p : p.text;
          var role = typeof p === 'string' ? '' : (p.role || '');
          var note = typeof p === 'string' ? '' : (p.note || '');
          return [
            '<div class="card pad" style="margin-bottom:10px">',
            role ? '  <div class="tiny" style="margin-bottom:8px"><span class="pill" style="font-size:11px">' +
                   esc(role) + '</span></div>' : '',
            '  <div style="font-size:15px;line-height:2;text-indent:2em;white-space:pre-wrap">' +
                 esc(text) + '</div>',
            (showNote && note)
              ? '  <div style="margin-top:10px;padding:10px 12px;background:var(--bg-0);border-left:3px solid var(--brand);border-radius:4px;font-size:13px;line-height:1.8;color:var(--text-2)">' +
                '<b>💬 点评：</b>' + esc(note) + '</div>'
              : '',
            '</div>'
          ].join('');
        }).join(''),
        '</div>',

        ((a.highlights || []).length || (a.pitfalls || []).length) ? [
          '<div class="card pad" style="margin-bottom:12px">',
          (a.highlights || []).length
            ? '  <h3 style="margin:0 0 8px 0;font-size:15px">✅ 这篇范文好在哪</h3>' +
              '<ul style="margin:0 0 14px 0;padding-left:20px;line-height:1.9;font-size:14px">' +
              a.highlights.map(function (h) { return '<li>' + esc(h) + '</li>'; }).join('') + '</ul>'
            : '',
          (a.pitfalls || []).length
            ? '  <h3 style="margin:0 0 8px 0;font-size:15px">⚠️ 常见失分点</h3>' +
              '<ul style="margin:0;padding-left:20px;line-height:1.9;font-size:14px;color:var(--text-2)">' +
              a.pitfalls.map(function (h) { return '<li>' + esc(h) + '</li>'; }).join('') + '</ul>'
            : '',
          '</div>'
        ].join('') : '',

        '<div class="row" style="gap:8px;margin-bottom:20px">',
        '  <button class="btn primary" id="fwBack2">← 返回列表</button>',
        '</div>'
      ].join('');

      $('#fwBack', v).onclick = function () { FW.view(); };
      var b2 = $('#fwBack2', v);
      if (b2) b2.onclick = function () { FW.view(); };
      var tn = $('#fwToggleNote', v);
      if (tn) tn.onclick = function () { showNote = !showNote; render(); };
    }

    render();
  };

  /* ═══════════════ 病文批改列表 ═══════════════ */
  function paintBingwen(box) {
    var list = bingwen();
    if (!list.length) {
      box.innerHTML = '<div class="empty"><div class="big">🔧</div><p>暂无病文案例</p></div>';
      return;
    }
    box.innerHTML = [
      '<div class="card pad" style="margin-bottom:12px;background:var(--bg-0)">',
      '  <div style="font-size:14px;line-height:1.9">',
      '    <b>💡 什么是病文批改？</b><br>',
      '    给出典型低分答案原文，逐处标出问题并说明扣分原因，再给出改写后的高分版本。',
      '    看别人错在哪，比自己盲目练十篇更有效。',
      '  </div>',
      '</div>',
      '<div class="tiny" style="margin-bottom:8px">共 ' + list.length + ' 篇 · 点击查看批改</div>',
      list.map(function (a) {
        return [
          '<div class="card pad" style="margin-bottom:10px">',
          '  <div class="spread" style="margin-bottom:8px">',
          '    <div style="flex:1;min-width:0">',
          '      <div style="font-weight:700;font-size:15px;margin-bottom:3px">' + esc(a.title) + '</div>',
          '      <div class="tiny" style="color:var(--text-2);margin-bottom:6px">' + esc(a.subtitle || '') + '</div>',
          '      <div class="row" style="gap:5px;flex-wrap:wrap">',
          '        <span class="pill" style="background:#fee2e2;color:#991b1b;font-size:11px">原文 ' + esc(a.scoreBefore) + '</span>',
          '        <span class="pill ok" style="font-size:11px">改后 ' + esc(a.scoreAfter) + '</span>',
          '        <span class="pill" style="font-size:11px">' + a.annotations.length + ' 处批注</span>',
          '      </div>',
          '    </div>',
          '    <button class="btn sm primary" data-bw="' + esc(a.id) + '">查看批改</button>',
          '  </div>',
          '</div>'
        ].join('');
      }).join('')
    ].join('');

    $$('[data-bw]', box).forEach(function (b) {
      b.onclick = function () { FW.bingwenDetail(b.dataset.bw); };
    });
  }

  FW.bingwenDetail = function (id) {
    var list = bingwen(), a = null;
    for (var i = 0; i < list.length; i++) { if (list[i].id === id) { a = list[i]; break; } }
    if (!a) return;
    markRead(id);

    var v = document.getElementById('view');
    var showFixed = false;

    function render() {
      var html = [
        '<div class="spread" style="margin-bottom:14px">',
        '  <div><h1 style="font-size:21px;margin-bottom:4px">' + esc(a.title) + '</h1>',
        '    <p class="sub">' + esc(a.subtitle || '') + '</p></div>',
        '  <button class="btn sm" id="bwBack">← 返回</button>',
        '</div>',

        // 分数对比
        '<div class="card pad" style="margin-bottom:12px;display:flex;gap:20px;align-items:center;flex-wrap:wrap">',
        '  <div style="text-align:center">',
        '    <div class="tiny" style="color:var(--text-2)">原文得分</div>',
        '    <div style="font-size:24px;font-weight:700;color:#dc2626">' + esc(a.scoreBefore) + '</div>',
        '  </div>',
        '  <div style="font-size:22px;color:var(--text-2)">→</div>',
        '  <div style="text-align:center">',
        '    <div class="tiny" style="color:var(--text-2)">改写后</div>',
        '    <div style="font-size:24px;font-weight:700;color:#16a34a">' + esc(a.scoreAfter) + '</div>',
        '  </div>',
        '  <div style="flex:1;min-width:180px" class="tiny">',
        '    原文问题：' + a.annotations.length + ' 处需要改进',
        '  </div>',
        '</div>',

        // 原文
        '<h3 style="font-size:16px;margin:0 0 8px 0;color:#991b1b">❌ 低分原文</h3>',
        '<div class="card pad" style="margin-bottom:14px;background:#fef2f2;border:1px solid #fecaca">',
        '  <div style="font-size:14.5px;line-height:2;white-space:pre-wrap">' + esc(a.original) + '</div>',
        '</div>',

        // 逐处批注
        '<h3 style="font-size:16px;margin:0 0 8px 0">🔍 逐处批注</h3>'
      ];

      a.annotations.forEach(function (an, i) {
        html = html.concat([
          '<div class="card pad" style="margin-bottom:10px;border-left:3px solid #dc2626">',
          '  <div style="margin-bottom:8px">',
          '    <span class="pill" style="background:#fee2e2;color:#991b1b;font-size:11px">第' + (i + 1) + '处</span>',
          '    <span class="tiny" style="margin-left:6px;color:var(--text-2)">' + esc(an.pos) + '</span>',
          '  </div>',
          '  <div style="font-weight:600;margin-bottom:6px;font-size:14.5px">问题：' + esc(an.problem) + '</div>',
          '  <div class="tiny" style="line-height:1.9;color:var(--text-2);margin-bottom:8px">' + esc(an.detail) + '</div>',
          '  <div style="padding:8px 12px;background:var(--bg-0);border-radius:4px;font-size:13.5px;line-height:1.8">',
          '    <b style="color:#16a34a">✓ 改法：</b>' + esc(an.fix),
          '  </div>',
          '</div>'
        ]);
      });

      // 改写后
      html = html.concat([
        '<div class="spread" style="margin:16px 0 8px 0">',
        '  <h3 style="font-size:16px;margin:0;color:#16a34a">✅ 改写后范文</h3>',
        '  <button class="btn sm" id="bwToggle">' + (showFixed ? '收起' : '展开全文') + '</button>',
        '</div>'
      ]);

      if (showFixed) {
        html = html.concat([
          '<div class="card pad" style="margin-bottom:14px;background:#f0fdf4;border:1px solid #bbf7d0">',
          '  <div style="font-size:14.5px;line-height:2;white-space:pre-wrap">' + esc(a.revised) + '</div>',
          '</div>'
        ]);
      }

      // 对比表
      html = html.concat([
        '<h3 style="font-size:16px;margin:16px 0 8px 0">📊 前后对比</h3>',
        '<div class="card pad" style="margin-bottom:14px">',
        '  <div style="display:grid;gap:8px">',
        a.comparison.map(function (c) {
          return [
            '<div style="padding:10px;background:var(--bg-0);border-radius:6px">',
            '  <div style="font-weight:600;margin-bottom:6px;font-size:13.5px">' + esc(c.aspect) + '</div>',
            '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13px;line-height:1.7">',
            '    <div><span class="tiny" style="color:#991b1b">原文：</span>' + esc(c.before) + '</div>',
            '    <div><span class="tiny" style="color:#16a34a">改后：</span>' + esc(c.after) + '</div>',
            '  </div>',
            '</div>'
          ].join('');
        }).join(''),
        '  </div>',
        '</div>',

        // 启示
        '<h3 style="font-size:16px;margin:16px 0 8px 0">💡 这篇病文教给我们什么</h3>',
        '<div class="card pad" style="margin-bottom:20px">',
        '  <ol style="margin:0;padding-left:22px;line-height:2;font-size:14px">',
        a.lesson.map(function (l) { return '<li>' + esc(l) + '</li>'; }).join(''),
        '  </ol>',
        '</div>',

        '<div class="row" style="gap:8px;margin-bottom:20px">',
        '  <button class="btn primary" id="bwBack2">← 返回列表</button>',
        '</div>'
      ]);

      v.innerHTML = html.join('');
      $('#bwBack', v).onclick = function () { FW.view(); };
      var b2 = $('#bwBack2', v);
      if (b2) b2.onclick = function () { FW.view(); };
      var tg = $('#bwToggle', v);
      if (tg) tg.onclick = function () { showFixed = !showFixed; render(); };
    }

    render();
  };

  /* ═══════════════ 一题多解列表 ═══════════════ */
  function paintDuojie(box) {
    var list = duojie();
    if (!list.length) {
      box.innerHTML = '<div class="empty"><div class="big">🔀</div><p>暂时没有一题多解</p></div>';
      return;
    }
    box.innerHTML = [
      '<div class="card pad" style="margin-bottom:12px;background:var(--bg-0)">',
      '  <div style="font-size:14px;line-height:1.9">',
      '    <b>💡 同一道题，不同解法</b><br>',
      '    展示同一题目下的两种（或三种）立意路径、结构安排，并对比各自的优势与风险，帮你找到最适合自己的写法。',
      '  </div>',
      '</div>',
      '<div class="tiny" style="margin-bottom:8px">共 ' + list.length + ' 组</div>',
      list.map(function (a) {
        return [
          '<div class="card pad" style="margin-bottom:10px">',
          '  <div class="spread" style="margin-bottom:8px">',
          '    <div style="flex:1;min-width:0">',
          '      <div style="font-weight:700;font-size:15px;margin-bottom:3px">' + esc(a.title) + '</div>',
          '      <div class="tiny" style="color:var(--text-2);margin-bottom:6px">' + esc(a.subtitle || '') + '</div>',
          '      <div class="row" style="gap:5px;flex-wrap:wrap">',
          '        <span class="pill" style="font-size:11px">' + a.solutions.length + ' 种解法</span>',
          a.solutions.map(function (s, i) {
            return '<span class="pill" style="font-size:11px">' + esc(s.name.split('：')[0]) + '</span>';
          }).join(''),
          '      </div>',
          '    </div>',
          '    <button class="btn sm primary" data-dj="' + esc(a.id) + '">对比查看</button>',
          '  </div>',
          '</div>'
        ].join('');
      }).join('')
    ].join('');

    $$('[data-dj]', box).forEach(function (b) {
      b.onclick = function () { FW.duojieDetail(b.dataset.dj); };
    });
  }

  FW.duojieDetail = function (id) {
    var list = duojie(), a = null;
    for (var i = 0; i < list.length; i++) { if (list[i].id === id) { a = list[i]; break; } }
    if (!a) return;

    var v = document.getElementById('view');
    var html = [
      '<div class="spread" style="margin-bottom:14px">',
      '  <div><h1 style="font-size:20px;margin-bottom:4px">' + esc(a.title) + '</h1>',
      '    <p class="sub">' + esc(a.subtitle || '') + '</p></div>',
      '  <button class="btn sm" id="djBack">← 返回</button>',
      '</div>',

      // 原题
      '<div class="card pad" style="margin-bottom:14px;border-left:3px solid var(--brand)">',
      '  <div class="tiny" style="margin-bottom:6px;color:var(--text-2)">📋 原题</div>',
      '  <div style="font-size:14px;line-height:1.9">' + esc(a.question) + '</div>',
      '</div>'
    ];

    // 各解法
    a.solutions.forEach(function (s, i) {
      html = html.concat([
        '<div class="card pad" style="margin-bottom:14px">',
        '  <div class="spread" style="margin-bottom:10px">',
        '    <h3 style="margin:0;font-size:16px">' + esc(s.name) + '</h3>',
        '    <span class="pill ok" style="font-size:11px">' + esc(s.score) + '</span>',
        '  </div>',
        '  <div style="margin-bottom:10px;padding:8px 12px;background:var(--bg-0);border-radius:4px;font-size:13.5px;line-height:1.8">',
        '    <b>拟题：</b>' + esc(s.title) + '<br>',
        '    <b>切入角度：</b>' + esc(s.angle),
        '  </div>',
        '  <div class="tiny" style="margin-bottom:6px;color:var(--text-2)">结构：' +
             s.structure.map(function (x, j) {
               return esc(x) + (j < s.structure.length - 1 ? ' → ' : '');
             }).join('') + '</div>',
        '  <div style="margin:10px 0">',
        s.outline.map(function (o) {
          return '<div style="padding:8px 12px;margin-bottom:6px;background:var(--bg-0);border-radius:4px;font-size:13.5px;line-height:1.85">' +
            esc(o) + '</div>';
        }).join(''),
        '  </div>',
        '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px">',
        '    <div style="padding:10px;background:#f0fdf4;border-radius:6px">',
        '      <div class="tiny" style="color:#16a34a;font-weight:600;margin-bottom:4px">✓ 优势</div>',
        '      <ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.8">',
        s.pros.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join(''),
        '      </ul>',
        '    </div>',
        '    <div style="padding:10px;background:#fef2f2;border-radius:6px">',
        '      <div class="tiny" style="color:#991b1b;font-weight:600;margin-bottom:4px">⚠ 风险</div>',
        '      <ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.8">',
        s.cons.map(function (c) { return '<li>' + esc(c) + '</li>'; }).join(''),
        '      </ul>',
        '    </div>',
        '  </div>',
        '</div>'
      ]);
    });

    // 对比表
    html = html.concat([
      '<h3 style="font-size:16px;margin:16px 0 8px 0">📊 两种解法对比</h3>',
      '<div class="card pad" style="margin-bottom:14px;overflow-x:auto">',
      '  <table style="width:100%;border-collapse:collapse;font-size:13px">',
      '    <thead><tr style="border-bottom:2px solid var(--line)">',
      '      <th style="text-align:left;padding:8px">对比维度</th>'
    ]);
    a.solutions.forEach(function (s) {
      html.push('<th style="text-align:left;padding:8px">' + esc(s.name.split('：')[0]) + '</th>');
    });
    html.push('    </tr></thead><tbody>');
    a.comparison.forEach(function (c) {
      html.push('<tr style="border-bottom:1px solid var(--line)">');
      html.push('<td style="padding:8px;font-weight:600">' + esc(c.aspect) + '</td>');
      html.push('<td style="padding:8px;line-height:1.7">' + esc(c.A) + '</td>');
      if (c.B !== undefined) html.push('<td style="padding:8px;line-height:1.7">' + esc(c.B) + '</td>');
      if (c.C !== undefined) html.push('<td style="padding:8px;line-height:1.7">' + esc(c.C) + '</td>');
      html.push('</tr>');
    });
    html = html.concat(['  </tbody></table>', '</div>']);

    // 建议
    html = html.concat([
      '<h3 style="font-size:16px;margin:16px 0 8px 0">🎯 怎么选</h3>',
      '<div class="card pad" style="margin-bottom:20px">',
      '  <ol style="margin:0;padding-left:22px;line-height:2;font-size:14px">',
      a.advice.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join(''),
      '  </ol>',
      '</div>',
      '<div class="row" style="margin-bottom:20px">',
      '  <button class="btn primary" id="djBack2">← 返回列表</button>',
      '</div>'
    ]);

    v.innerHTML = html.join('');
    $('#djBack', v).onclick = function () { FW.view(); };
    var b2 = $('#djBack2', v);
    if (b2) b2.onclick = function () { FW.view(); };
  };

  /* ═══════════════ 时评范文内联展开 ═══════════════ */
  function showInline(row, a) {
    var next = row.nextElementSibling;
    if (next && next.classList.contains('fw-inline')) { next.remove(); return; }

    var div = document.createElement('div');
    div.className = 'card pad fw-inline';
    div.style.cssText = 'margin:0 0 8px 0;font-size:14.5px;line-height:2;max-height:520px;overflow:auto';

    var html = [
      '<div class="spread" style="margin-bottom:10px">',
      '  <div><b style="font-size:15px">' + esc(a.title) + '</b>',
      '    <div class="tiny" style="color:var(--text-2);margin-top:3px">' +
           esc(a.source || '') + ' · ' + esc(a.date || '') + ' · ' + a.words + ' 字</div></div>',
      '  <button class="btn sm" data-go="' + esc(a.url) + '">↗ 原文</button>',
      '</div>'
    ];
    (a.paras || []).forEach(function (p) {
      html.push('<p style="margin:0 0 12px 0;text-indent:2em">' + esc(p) + '</p>');
    });
    div.innerHTML = html.join('');
    div.querySelector('[data-go]').onclick = function (e) {
      e.stopPropagation();
      window.open(a.url, '_blank');
    };
    row.insertAdjacentElement('afterend', div);
  }

})();

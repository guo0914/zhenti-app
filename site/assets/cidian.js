/* =========================================================
   国省考常考词汇 · 单页应用
   数据: window.__CIDIAN_CURATED__ (精选 + 真题挖掘合并)
   功能: 成语库 / 实词辨析 / 易错辨析 / 搜索 / 收藏 / 随机测
   ========================================================= */
(function () {
  'use strict';

  var CD = window.ZLFX_CIDIAN = {};
  var LS_FAV = 'zlfx.cidian.favs';
  var LS_LEARN = 'zlfx.cidian.learned';

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
  function toggleFav(w) {
    var f = getFavs(), i = f.indexOf(w);
    if (i >= 0) f.splice(i, 1); else f.push(w);
    setFavs(f);
    return i < 0;
  }
  function getLearned() {
    try { return JSON.parse(localStorage.getItem(LS_LEARN) || '[]'); } catch (e) { return []; }
  }
  function markLearned(w) {
    var a = getLearned();
    if (a.indexOf(w) < 0) { a.push(w); try { localStorage.setItem(LS_LEARN, JSON.stringify(a)); } catch (e) {} }
  }

  function data() { return window.__CIDIAN_CURATED__ || { allIdioms: [], groups: [], traps: [] }; }

  CD._state = { tab: 'idiom', topic: 'all', gtopic: 'all', ttopic: 'all', q: '', fav: false, page: 1, expanded: null };

  var PAGE_SIZE = 40;

  /* ═══════════════ 主视图 ═══════════════ */
  CD.view = function () {
    var v = document.getElementById('view');
    if (!v) return;
    var D = data();
    var st = CD._state;
    var favs = getFavs();
    var learned = getLearned();

    v.innerHTML = [
      '<div class="spread" style="margin-bottom:14px">',
      '  <div><h1>常考词汇</h1>',
      '    <p class="sub">成语 ' + (D.allIdioms || []).length + ' 条 · 实词辨析 ' +
             (D.groups || []).length + ' 组 · 易错 ' + (D.traps || []).length +
             ' 条 · 已学 ' + learned.length + '</p></div>',
      '  <div class="row" style="gap:6px">',
      '    <button class="btn sm" id="cdRandom">🎲 随机</button>',
      '    <button class="btn sm' + (st.fav ? ' primary' : '') + '" id="cdFav">⭐ 收藏 ' + favs.length + '</button>',
      '  </div>',
      '</div>',
      '<div class="card pad" style="margin-bottom:12px">',
      '  <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:10px">',
      '    <button class="btn sm' + (st.tab === 'idiom' ? ' primary' : '') + '" data-tab="idiom">📖 成语库</button>',
      '    <button class="btn sm' + (st.tab === 'word' ? ' primary' : '') + '" data-tab="word">🔤 实词辨析</button>',
      '    <button class="btn sm' + (st.tab === 'trap' ? ' primary' : '') + '" data-tab="trap">⚠ 易错辨析</button>',
      '  </div>',
      '  <input id="cdSearch" placeholder="🔍 搜索成语、释义、辨析…" value="' + esc(st.q) + '"',
      '    style="width:100%;box-sizing:border-box;padding:9px 14px;border:1px solid var(--line);border-radius:8px;font-size:14px;background:var(--bg-1);color:var(--text-1)">',
      st.tab === 'idiom' ? '  <div id="cdTopics" style="margin-top:10px"></div>' : '',
      '</div>',
      '<div id="cdBody"></div>'
    ].join('');

    // Tab 切换
    $$('[data-tab]', v).forEach(function (b) {
      b.onclick = function () { st.tab = b.dataset.tab; st.page = 1; st.q = ''; CD.view(); };
    });

    var searchEl = $('#cdSearch', v);
    if (searchEl) {
      var timer = null;
      searchEl.oninput = function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
          st.q = searchEl.value.trim();
          st.page = 1;
          CD.paintBody();
        }, 300);
      };
    }

    var rb = $('#cdRandom', v);
    if (rb) rb.onclick = CD.randomPick;

    var fb = $('#cdFav', v);
    if (fb) fb.onclick = function () { st.fav = !st.fav; st.page = 1; CD.view(); };

    CD.paintTopics();
    CD.paintBody();
  };

  /* ═══════════════ 主题筛选条 ═══════════════ */
  CD.paintTopics = function () {
    var box = document.getElementById('cdTopics');
    if (!box) return;
    var D = data(), st = CD._state;
    var counts = {};
    (D.allIdioms || []).forEach(function (x) { counts[x.topic] = (counts[x.topic] || 0) + 1; });
    var topics = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; });

    var html = ['<div class="tiny" style="margin-bottom:6px">按考点分组</div>',
      '<div class="row" style="gap:5px;flex-wrap:wrap">',
      '<button class="btn sm' + (st.topic === 'all' ? ' primary' : '') + '" data-topic="all">全部 ' +
        (D.allIdioms || []).length + '</button>'];
    topics.forEach(function (t) {
      html.push('<button class="btn sm' + (st.topic === t ? ' primary' : '') + '" data-topic="' +
        esc(t) + '">' + esc(t) + ' <span class="tiny">' + counts[t] + '</span></button>');
    });
    html.push('</div>');
    box.innerHTML = html.join('');

    $$('[data-topic]', box).forEach(function (b) {
      b.onclick = function () { st.topic = b.dataset.topic; st.page = 1; CD.view(); };
    });
  };

  /* ═══════════════ 主体列表 ═══════════════ */
  CD.paintBody = function () {
    var box = document.getElementById('cdBody');
    if (!box) return;
    var D = data(), st = CD._state;

    if (st.tab === 'idiom') return paintIdioms(box, D, st);
    if (st.tab === 'word') return paintGroups(box, D, st);
    if (st.tab === 'trap') return paintTraps(box, D, st);
  };

  function paintIdioms(box, D, st) {
    var favs = getFavs();
    var list = D.allIdioms || [];

    if (st.fav) list = list.filter(function (x) { return favs.indexOf(x.word) >= 0; });
    if (st.topic !== 'all') list = list.filter(function (x) { return x.topic === st.topic; });
    if (st.q) {
      var q = st.q.toLowerCase();
      list = list.filter(function (x) {
        return (x.word || '').toLowerCase().indexOf(q) >= 0 ||
               (x.def || '').toLowerCase().indexOf(q) >= 0 ||
               (x.conf || '').toLowerCase().indexOf(q) >= 0 ||
               (x.topic || '').toLowerCase().indexOf(q) >= 0;
      });
    }

    if (!list.length) {
      box.innerHTML = '<div class="empty"><div class="big">📖</div><p>' +
        (st.fav ? '还没有收藏' : '没有匹配的词条') + '</p></div>';
      return;
    }

    var total = list.length;
    var pages = Math.ceil(total / PAGE_SIZE);
    if (st.page > pages) st.page = 1;
    var slice = list.slice((st.page - 1) * PAGE_SIZE, st.page * PAGE_SIZE);

    var html = ['<div class="tiny" style="margin-bottom:8px">共 ' + total + ' 条' +
      (pages > 1 ? '（第 ' + st.page + '/' + pages + ' 页）' : '') + '</div>',
      '<div class="rows">'];

    slice.forEach(function (x, i) {
      var isFav = favs.indexOf(x.word) >= 0;
      var badges = '';
      if (x.source === 'mined') badges += '<span class="pill dim" style="font-size:10px">真题</span>';
      if (x.freq > 1) badges += '<span class="pill" style="font-size:10px">考' + x.freq + '次</span>';
      if (x.ansCount > 0) badges += '<span class="pill ok" style="font-size:10px">答案' + x.ansCount + '</span>';

      html.push(
        '<div class="rowitem" style="cursor:pointer;align-items:flex-start" data-idx="' + i + '">',
        '  <span class="rno" style="margin-top:2px">' + esc(x.topic || '') + '</span>',
        '  <div style="flex:1;min-width:0">',
        '    <div class="rtxt" style="font-weight:600;margin-bottom:2px">' + esc(x.word) + ' ' + badges + '</div>',
        '    <div class="tiny" style="line-height:1.6;color:var(--text-2)">' + esc((x.def || '').slice(0, 60)) + '</div>',
        '  </div>',
        '  <button class="btn sm" data-fav="' + esc(x.word) + '" style="padding:2px 7px">' + (isFav ? '★' : '☆') + '</button>',
        '</div>'
      );
    });
    html.push('</div>');

    // 分页
    if (pages > 1) {
      html.push('<div class="row" style="gap:6px;justify-content:center;margin-top:14px">',
        '<button class="btn sm" data-page="' + (st.page - 1) + '"' + (st.page <= 1 ? ' disabled' : '') + '>上一页</button>',
        '<span class="tiny" style="align-self:center">' + st.page + ' / ' + pages + '</span>',
        '<button class="btn sm" data-page="' + (st.page + 1) + '"' + (st.page >= pages ? ' disabled' : '') + '>下一页</button>',
        '</div>');
    }

    box.innerHTML = html.join('');

    // 事件
    $$('[data-idx]', box).forEach(function (el) {
      el.onclick = function (e) {
        if (e.target.dataset.fav) return;
        showDetail(el, slice[parseInt(el.dataset.idx)]);
      };
    });
    $$('[data-fav]', box).forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation();
        var now = toggleFav(b.dataset.fav);
        b.textContent = now ? '★' : '☆';
        var fb = document.getElementById('cdFav');
        if (fb) fb.textContent = '⭐ 收藏 ' + getFavs().length;
        if (window.toast) window.toast(now ? '已收藏' : '已取消');
      };
    });
    $$('[data-page]', box).forEach(function (b) {
      b.onclick = function () {
        st.page = parseInt(b.dataset.page);
        CD.paintBody();
        box.scrollIntoView({ block: 'start', behavior: 'smooth' });
      };
    });
  }

  function showDetail(row, x) {
    var next = row.nextElementSibling;
    if (next && next.classList.contains('cd-detail')) { next.remove(); return; }

    markLearned(x.word);

    var parts = [
      '<div class="card pad cd-detail" style="margin:0 0 8px 0;font-size:14px;line-height:1.85">',
      '  <div style="margin-bottom:10px">',
      '    <span style="font-size:20px;font-weight:700">' + esc(x.word) + '</span>',
      x.color ? '  <span class="pill" style="margin-left:8px">' + esc(x.color) + '</span>' : '',
      '    <span class="tiny" style="color:var(--text-2);margin-left:8px">' + esc(x.topic || '') + '</span>',
      '  </div>'
    ];

    if (x.def) parts.push('<p style="margin:0 0 10px 0"><b>释义：</b>' + esc(x.def) + '</p>');
    if (x.use) parts.push('<p style="margin:0 0 10px 0"><b>用法：</b>' + esc(x.use) + '</p>');
    if (x.conf) parts.push('<p style="margin:0 0 10px 0;padding:8px 12px;background:var(--bg-0);border-left:3px solid var(--brand);border-radius:4px"><b>辨析：</b>' + esc(x.conf) + '</p>');
    if (x.ex) parts.push('<p style="margin:0 0 10px 0"><b>例句：</b>' + esc(x.ex) + '</p>');

    // 真题语境
    if (x.contexts && x.contexts.length) {
      parts.push('<div style="margin-top:12px"><b>📝 真题语境（' + x.contexts.length + ' 题）</b></div>');
      x.contexts.forEach(function (c, i) {
        parts.push('<div style="margin:8px 0;padding:10px;background:var(--bg-0);border-radius:6px;font-size:13px">');
        parts.push('<div class="tiny" style="color:var(--text-2);margin-bottom:6px">' +
          esc(c.paper || '') + (c.year ? ' · ' + esc(c.year) : '') + '</div>');
        parts.push('<div style="line-height:1.7;margin-bottom:6px">' + esc(c.stem) + '</div>');
        if (c.options && c.options.length) {
          parts.push('<div class="tiny" style="margin-bottom:6px">' +
            c.options.map(function (o, k) {
              var letter = String.fromCharCode(65 + k);
              var isAns = letter === c.answer;
              var isThis = o === x.word;
              var style = isAns ? 'color:var(--ok,#16a34a);font-weight:700' :
                          (isThis ? 'color:var(--danger)' : '');
              return '<span style="margin-right:10px;' + style + '">' + letter + '. ' + esc(o) +
                     (isAns ? ' ✓' : '') + '</span>';
            }).join('') + '</div>');
        }
        if (c.explain) {
          parts.push('<div class="tiny" style="line-height:1.7;color:var(--text-2);border-top:1px dashed var(--line);padding-top:6px">' +
            esc(c.explain.slice(0, 300)) + '</div>');
        }
        parts.push('</div>');
      });
    }

    parts.push('<div class="row" style="gap:8px;margin-top:12px">',
      '<button class="btn sm" data-copy="' + esc(x.word + '：' + (x.def || '')) + '">📋 复制</button>',
      '</div>');
    parts.push('</div>');

    var div = document.createElement('div');
    div.innerHTML = parts.join('');
    var node = div.firstElementChild;
    node.querySelector('[data-copy]').onclick = function (e) {
      e.stopPropagation();
      var t = e.target.dataset.copy;
      if (navigator.clipboard) navigator.clipboard.writeText(t);
      if (window.toast) window.toast('已复制');
    };
    row.insertAdjacentElement('afterend', node);
  }

  function paintGroups(box, D, st) {
    var all = D.groups || [];
    var groups = all;

    // 分类筛选
    var gt = st.gtopic || 'all';
    if (gt !== 'all') groups = groups.filter(function (g) { return g.topic === gt; });

    if (st.q) {
      var q = st.q.toLowerCase();
      groups = groups.filter(function (g) {
        return (g.title || '').toLowerCase().indexOf(q) >= 0 ||
               (g.diff || '').toLowerCase().indexOf(q) >= 0 ||
               (g.words || []).some(function (w) {
                 return (w.w || '').toLowerCase().indexOf(q) >= 0 ||
                        (w.def || '').toLowerCase().indexOf(q) >= 0;
               });
      });
    }

    // 分类统计
    var cats = {};
    all.forEach(function (g) { cats[g.topic] = (cats[g.topic] || 0) + 1; });

    var bar = ['<div class="row" style="gap:5px;flex-wrap:wrap;margin-bottom:12px">',
      '<button class="btn sm' + (gt === 'all' ? ' primary' : '') + '" data-gtopic="all">全部 ' + all.length + '</button>'];
    Object.keys(cats).forEach(function (c) {
      bar.push('<button class="btn sm' + (gt === c ? ' primary' : '') + '" data-gtopic="' + esc(c) + '">' +
        esc(c) + ' <span class="tiny">' + cats[c] + '</span></button>');
    });
    bar.push('</div>');

    if (!groups.length) {
      box.innerHTML = bar.join('') + '<div class="empty"><div class="big">🔤</div><p>没有匹配的辨析组</p></div>';
      bindGtopic(box);
      return;
    }

    box.innerHTML = bar.join('') + groups.map(function (g) {
      return [
        '<div class="card pad" style="margin-bottom:12px">',
        '  <div class="spread" style="margin-bottom:10px">',
        '    <h3 style="margin:0;font-size:16px">' + esc(g.title) + '</h3>',
        '    <span class="pill" style="font-size:11px">' + esc(g.topic) + '</span>',
        '  </div>',
        '  <div style="display:grid;gap:8px;margin-bottom:12px">',
        (g.words || []).map(function (w) {
          return '<div style="padding:10px;background:var(--bg-0);border-radius:6px">' +
            '<div style="font-weight:600;margin-bottom:3px">' + esc(w.w) + '</div>' +
            '<div class="tiny" style="line-height:1.7"><b>释义：</b>' + esc(w.def) + '</div>' +
            '<div class="tiny" style="line-height:1.7;color:var(--brand)"><b>侧重：</b>' + esc(w.focus) + '</div>' +
            '</div>';
        }).join(''),
        '  </div>',
        g.diff ? '<p style="margin:0 0 8px 0;padding:8px 12px;background:var(--bg-0);border-left:3px solid var(--brand);border-radius:4px;font-size:13px;line-height:1.7"><b>辨析：</b>' + esc(g.diff) + '</p>' : '',
        g.tip ? '<p style="margin:0;font-size:13px;line-height:1.7;color:var(--text-2)"><b>💡 技巧：</b>' + esc(g.tip) + '</p>' : '',
        '</div>'
      ].join('');
    }).join('');

    bindGtopic(box);
  }

  function bindGtopic(box) {
    $$('[data-gtopic]', box).forEach(function (b) {
      b.onclick = function () {
        CD._state.gtopic = b.dataset.gtopic;
        CD.paintBody();
      };
    });
  }

  function paintTraps(box, D, st) {
    var all = D.traps || [];
    var traps = all;

    // 自动归类：按顺序区间划分为 6 类
    function catOf(i) {
      if (i < 14) return '易混词对';
      if (i < 30) return '望文生义';
      if (i < 42) return '对象误用';
      if (i < 50) return '感情色彩';
      return '语法搭配';
    }
    all = all.map(function (t, i) { return Object.assign({}, t, { _cat: t.cat || catOf(i) }); });

    var tt = st.ttopic || 'all';
    if (tt !== 'all') traps = all.filter(function (t) { return t._cat === tt; });
    else traps = all;

    if (st.q) {
      var q = st.q.toLowerCase();
      traps = traps.filter(function (t) {
        return (t.pair || '').toLowerCase().indexOf(q) >= 0 ||
               (t.tip || '').toLowerCase().indexOf(q) >= 0;
      });
    }

    var cats = {};
    all.forEach(function (t) { cats[t._cat] = (cats[t._cat] || 0) + 1; });

    var bar = ['<div class="row" style="gap:5px;flex-wrap:wrap;margin-bottom:12px">',
      '<button class="btn sm' + (tt === 'all' ? ' primary' : '') + '" data-ttopic="all">全部 ' + all.length + '</button>'];
    Object.keys(cats).forEach(function (c) {
      bar.push('<button class="btn sm' + (tt === c ? ' primary' : '') + '" data-ttopic="' + esc(c) + '">' +
        esc(c) + ' <span class="tiny">' + cats[c] + '</span></button>');
    });
    bar.push('</div>');

    if (!traps.length) {
      box.innerHTML = bar.join('') + '<div class="empty"><div class="big">⚠</div><p>没有匹配的辨析</p></div>';
    } else {
      // 按类别分组显示
      var grouped = {};
      traps.forEach(function (t) {
        if (!grouped[t._cat]) grouped[t._cat] = [];
        grouped[t._cat].push(t);
      });

      var html = bar.join('');
      Object.keys(grouped).forEach(function (c) {
        html += '<h3 style="font-size:15px;margin:16px 0 10px 0;color:var(--text-2);border-left:3px solid var(--danger,#dc2626);padding-left:8px">' +
          esc(c) + ' <span class="tiny">' + grouped[c].length + ' 条</span></h3>';
        html += grouped[c].map(function (t) {
          return [
            '<div class="card pad" style="margin-bottom:10px;border-left:3px solid var(--danger,#dc2626)">',
            '  <div style="font-weight:700;font-size:15px;margin-bottom:6px">' + esc(t.pair) + '</div>',
            '  <p style="margin:0;font-size:13.5px;line-height:1.8;color:var(--text-2)">' + esc(t.tip) + '</p>',
            '</div>'
          ].join('');
        }).join('');
      });
      box.innerHTML = html;
    }

    $$('[data-ttopic]', box).forEach(function (b) {
      b.onclick = function () {
        CD._state.ttopic = b.dataset.ttopic;
        CD.paintBody();
      };
    });
  }

  /* ═══════════════ 随机抽词（自测模式）═══════════════ */
  // 池：优先未学过的词，学完一轮后全池随机
  function pickWord() {
    var D = data();
    var all = D.allIdioms || [];
    if (!all.length) return null;
    var learned = getLearned();
    var fresh = all.filter(function (x) { return learned.indexOf(x.word) < 0; });
    var pool = fresh.length ? fresh : all;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  CD.randomPick = function () {
    var x = pickWord();
    if (!x) return;

    var revealed = false;
    var ov = document.createElement('div');
    ov.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;padding:20px';

    function render() {
      var head = [
        '<div class="card pad" style="max-width:520px;width:100%;max-height:82vh;overflow:auto">',
        '  <div style="text-align:center;margin-bottom:16px">',
        '    <div class="tiny" style="color:var(--text-2);margin-bottom:8px">🎲 随机自测 · 先想清楚再看</div>',
        '    <div style="font-size:30px;font-weight:700;letter-spacing:3px;margin-bottom:8px">' + esc(x.word) + '</div>',
        '  </div>'
      ].join('');

      if (!revealed) {
        return head + [
          '<div style="text-align:center;padding:22px 0;border-top:1px dashed var(--line);border-bottom:1px dashed var(--line);margin-bottom:16px">',
          '  <div style="font-size:15px;color:var(--text-2);line-height:2">',
          '    请先在心中说出它的<br><b>① 释义　② 感情色彩　③ 适用对象</b>',
          '  </div>',
          '</div>',
          '<div class="row" style="gap:8px;justify-content:center;flex-wrap:wrap">',
          '  <button class="btn primary" id="cdReveal" style="min-width:150px">👁 显示释义</button>',
          '  <button class="btn" id="cdSkip">换一个</button>',
          '  <button class="btn" id="cdClose">关闭</button>',
          '</div>',
          '<p class="tiny" style="text-align:center;margin-top:14px;color:var(--text-2)">快捷键：回车显示释义 · 空格换一个 · Esc 关闭</p>',
          '</div>'
        ].join('');
      }

      // 已揭示
      return head + [
        '  <div style="margin-bottom:8px">',
        x.color ? '    <span class="pill">' + esc(x.color) + '</span>' : '',
        x.topic ? '    <span class="tiny" style="color:var(--text-2);margin-left:6px">' + esc(x.topic) + '</span>' : '',
        '  </div>',
        x.def ? '<p style="line-height:1.85;margin:0 0 10px 0;padding:10px 14px;background:var(--bg-0);border-radius:6px"><b>释义：</b>' + esc(x.def) + '</p>' : '',
        x.use ? '<p style="line-height:1.8;margin:0 0 10px 0"><b>用法：</b>' + esc(x.use) + '</p>' : '',
        x.conf ? '<p style="line-height:1.8;margin:0 0 10px 0;padding:8px 12px;background:var(--bg-0);border-left:3px solid var(--brand);border-radius:4px"><b>辨析：</b>' + esc(x.conf) + '</p>' : '',
        x.ex ? '<p style="line-height:1.8;margin:0 0 10px 0"><b>例句：</b>' + esc(x.ex) + '</p>' : '',
        (x.contexts && x.contexts.length)
          ? '<p class="tiny" style="line-height:1.7;color:var(--text-2);margin:0 0 10px 0">📝 真题中出现 ' +
            x.freq + ' 次' + (x.ansCount ? '，其中 ' + x.ansCount + ' 次为正确答案' : '') + '</p>'
          : '',
        '  <div class="row" style="gap:8px;justify-content:center;margin-top:16px;flex-wrap:wrap">',
        '    <button class="btn primary" id="cdNext">下一个 →</button>',
        '    <button class="btn" id="cdAgain">重看</button>',
        '    <button class="btn" id="cdClose">关闭</button>',
        '  </div>',
        '  <p class="tiny" style="text-align:center;margin-top:14px;color:var(--text-2)">快捷键：回车下一个 · Esc 关闭</p>',
        '</div>'
      ].join('');
    }

    function bind() {
      var rv = ov.querySelector('#cdReveal');
      if (rv) rv.onclick = function () { revealed = true; markLearned(x.word); paint(); };
      var sk = ov.querySelector('#cdSkip');
      if (sk) sk.onclick = function () { ov.remove(); CD.randomPick(); };
      var ag = ov.querySelector('#cdAgain');
      if (ag) ag.onclick = function () { revealed = false; paint(); };
      var nx = ov.querySelector('#cdNext');
      if (nx) nx.onclick = function () { ov.remove(); CD.randomPick(); };
      var cl = ov.querySelector('#cdClose');
      if (cl) cl.onclick = close;
    }

    function paint() {
      ov.innerHTML = render();
      bind();
    }

    function close() {
      document.removeEventListener('keydown', onKey);
      ov.remove();
    }

    function onKey(e) {
      if (e.key === 'Escape') { close(); return; }
      if (!revealed && e.key === 'Enter') { e.preventDefault(); revealed = true; markLearned(x.word); paint(); return; }
      if (!revealed && e.key === ' ') { e.preventDefault(); ov.remove(); document.removeEventListener('keydown', onKey); CD.randomPick(); return; }
      if (revealed && e.key === 'Enter') { e.preventDefault(); ov.remove(); document.removeEventListener('keydown', onKey); CD.randomPick(); }
    }

    document.body.appendChild(ov);
    paint();
    document.addEventListener('keydown', onKey);
    ov.onclick = function (e) { if (e.target === ov) close(); };
  };

})();

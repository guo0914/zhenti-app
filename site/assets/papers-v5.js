/* =========================================================
   行测真题套卷 · 完整模拟 + 分模块练习
   数据: site/data/zt-papers.json（套卷索引）
         site/data/zt/*.json（题目，通过 ZLFX_ZH 的加载器按需拉取）

   路由: #/papers  套卷列表
         #/paperrun?p=<卷名URL编码>&m=<模块或all>&time=1
   ========================================================= */
(function () {
  'use strict';

  var P = window.ZLFX_PAPERS = {};
  var LS_WRONG = 'zlfx.papers.wrong';
  var LS_HIST = 'zlfx.papers.history';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function fmtSec(s) {
    s = Math.max(0, Math.round(s));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return (h ? h + ':' + pad2(m) : m) + ':' + pad2(x);
  }

  /* ── 本地存储 ── */
  function getWrong() {
    try { return JSON.parse(localStorage.getItem(LS_WRONG) || '[]'); } catch (e) { return []; }
  }
  function addWrong(id) {
    var w = getWrong();
    if (w.indexOf(id) < 0) { w.push(id); try { localStorage.setItem(LS_WRONG, JSON.stringify(w.slice(-800))); } catch (e) {} }
  }
  function removeWrong(id) {
    var w = getWrong(), i = w.indexOf(id);
    if (i >= 0) { w.splice(i, 1); try { localStorage.setItem(LS_WRONG, JSON.stringify(w)); } catch (e) {} }
  }
  function getHist() {
    try { return JSON.parse(localStorage.getItem(LS_HIST) || '[]'); } catch (e) { return []; }
  }
  function addHist(rec) {
    var h = getHist();
    h.push(rec);
    try { localStorage.setItem(LS_HIST, JSON.stringify(h.slice(-60))); } catch (e) {}
  }

  /* ── 索引缓存 ── */
  var _idx = null, _idxLoading = false;

  function loadIndex(cb) {
    if (_idx) { cb(_idx); return; }
    if (window.__ZT_PAPERS__) { _idx = window.__ZT_PAPERS__; cb(_idx); return; }
    if (_idxLoading) return;
    _idxLoading = true;
    var s = document.createElement('script');
    s.src = 'data/zt-papers.js';
    s.onload = function () {
      _idxLoading = false;
      _idx = window.__ZT_PAPERS__ || { papers: [] };
      cb(_idx);
    };
    s.onerror = function () {
      _idxLoading = false;
      // 回退：直接 fetch JSON
      fetch('data/zt-papers.json').then(function (r) { return r.json(); })
        .then(function (d) { _idx = d; cb(d); })
        .catch(function () { _idx = { papers: [] }; cb(_idx); });
    };
    document.body.appendChild(s);
  }

  /* ═══════════════ 套卷列表页 ═══════════════ */
  P.view = function () {
    var v = document.getElementById('view');
    if (!v) return;
    v.innerHTML = '<div class="empty"><div class="big">⏳</div><p>正在加载套卷索引…</p></div>';

    loadIndex(function (idx) {
      var papers = (idx && idx.papers) || [];
      if (!papers.length) {
        v.innerHTML = '<div class="empty"><div class="big">📄</div><p>暂无套卷数据</p>' +
          '<p class="tiny">请运行 scripts/build_paper_index.py 生成索引</p></div>';
        return;
      }
      renderList(v, idx, papers);
    });
  };

  /* 状态：当前筛选 */
  var filter = { year: 'all', region: 'all', grade: 'A' };

  function renderList(v, idx, papers) {
    var meta = idx.meta || {};
    var years = (meta.years || []).slice();
    var regions = {};
    papers.forEach(function (p) { regions[p.region] = (regions[p.region] || 0) + 1; });
    var regionKeys = Object.keys(regions).sort(function (a, b) { return regions[b] - regions[a]; });

    // 应用筛选
    var list = papers.filter(function (p) {
      if (filter.year !== 'all' && p.year !== filter.year) return false;
      if (filter.region !== 'all' && p.region !== filter.region) return false;
      if (filter.grade !== 'all' && p.grade !== filter.grade) return false;
      return true;
    });

    var hist = getHist();
    var doneMap = {};
    hist.forEach(function (r) { doneMap[r.paper] = r; });

    var html = [];
    html.push('<div class="spread" style="margin-bottom:14px">');
    html.push('  <div><h1>真题套卷</h1>');
    html.push('    <p class="sub">' + papers.length + ' 套 · ' +
      (meta.totalQuestions || 0) + ' 题 · ' + (years.join(' / ') || '') + '</p></div>');
    html.push('</div>');

    // 筛选栏
    html.push('<div class="card pad" style="margin-bottom:14px">');

    html.push('  <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:10px">');
    html.push('    <span class="tiny" style="min-width:44px">年份</span>');
    html.push('    <button class="btn sm' + (filter.year === 'all' ? ' primary' : '') +
      '" data-fy="all">全部</button>');
    years.forEach(function (y) {
      html.push('    <button class="btn sm' + (filter.year === y ? ' primary' : '') +
        '" data-fy="' + esc(y) + '">' + esc(y) + '</button>');
    });
    html.push('  </div>');

    html.push('  <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:10px">');
    html.push('    <span class="tiny" style="min-width:44px">地区</span>');
    html.push('    <button class="btn sm' + (filter.region === 'all' ? ' primary' : '') +
      '" data-fr="all">全部</button>');
    regionKeys.forEach(function (r) {
      html.push('    <button class="btn sm' + (filter.region === r ? ' primary' : '') +
        '" data-fr="' + esc(r) + '">' + esc(r) + ' <span class="tiny">' + regions[r] + '</span></button>');
    });
    html.push('  </div>');

    html.push('  <div class="row" style="gap:6px;flex-wrap:wrap">');
    html.push('    <span class="tiny" style="min-width:44px">完整度</span>');
    [['A', 'A级·可模拟'], ['B', 'B级·中等'], ['C', 'C级·片段'], ['all', '全部']].forEach(function (g) {
      html.push('    <button class="btn sm' + (filter.grade === g[0] ? ' primary' : '') +
        '" data-fg="' + g[0] + '">' + g[1] + '</button>');
    });
    html.push('  </div>');

    html.push('</div>');

    // 套卷列表
    if (!list.length) {
      html.push('<div class="empty"><p>当前筛选下没有套卷</p></div>');
    } else {
      html.push('<div class="tiny" style="margin-bottom:8px;color:var(--text-2)">共 ' +
        list.length + ' 套</div>');
      html.push('<div class="rows">');
      list.forEach(function (p) {
        var done = doneMap[p.paper];
        var mods = (p.modules || []).map(function (m) {
          return '<span class="pill" style="font-size:10px;padding:1px 6px">' +
            esc(m.name) + ' ' + m.count + '</span>';
        }).join(' ');

        html.push([
          '<div class="rowitem" style="cursor:pointer;align-items:flex-start" data-paper="' + esc(p.paper) + '">',
          '  <span class="rno" style="margin-top:2px">' + esc(p.grade) + '</span>',
          '  <div style="flex:1;min-width:0">',
          '    <div class="rtxt" style="margin-bottom:4px;line-height:1.5">' + esc(p.paper) + '</div>',
          '    <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:4px">',
          '      <span class="tiny">' + esc(p.year) + ' · ' + esc(p.region) +
                 (p.subtype ? ' · ' + esc(p.subtype) : '') + '</span>',
          '      <span class="tiny">' + p.total + ' 题 · ' + p.moduleCount + ' 模块' +
                 (p.noGaps ? ' · 缺' + p.noGaps + '题' : '') + '</span>',
          done ? '      <span class="tiny" style="color:#16a34a">上次 ' + done.score + '/' + done.total + '</span>' : '',
          '    </div>',
          '    <div style="line-height:1.8">' + mods + '</div>',
          '  </div>',
          '  <span class="pill">进入</span>',
          '</div>'
        ].join(''));
      });
      html.push('</div>');
    }

    v.innerHTML = html.join('');

    // 绑定筛选
    $$('[data-fy]', v).forEach(function (b) {
      b.onclick = function () { filter.year = b.dataset.fy; renderList(v, idx, papers); };
    });
    $$('[data-fr]', v).forEach(function (b) {
      b.onclick = function () { filter.region = b.dataset.fr; renderList(v, idx, papers); };
    });
    $$('[data-fg]', v).forEach(function (b) {
      b.onclick = function () { filter.grade = b.dataset.fg; renderList(v, idx, papers); };
    });
    // 绑定套卷点击
    $$('[data-paper]', v).forEach(function (el) {
      el.onclick = function () { P.viewPaper(idx, el.dataset.paper); };
    });
  }

  /* ═══════════════ 单套卷详情：选择模式 ═══════════════ */
  P.viewPaper = function (idx, paperName) {
    var v = document.getElementById('view');
    var p = (idx.papers || []).filter(function (x) { return x.paper === paperName; })[0];
    if (!p) { P.view(); return; }

    var mods = p.modules || [];
    var html = [];
    html.push('<div class="spread" style="margin-bottom:14px">');
    html.push('  <div><h1 style="font-size:17px;line-height:1.5">' + esc(p.paper) + '</h1>');
    html.push('    <p class="sub">' + esc(p.year) + ' · ' + esc(p.region) +
      (p.subtype ? ' · ' + esc(p.subtype) : '') + ' · ' + p.total + ' 题 · ' +
      p.moduleCount + ' 模块</p></div>');
    html.push('  <button class="btn sm" id="backList">← 返回</button>');
    html.push('</div>');

    // 完整模拟
    html.push('<div class="card pad" style="margin-bottom:14px;border-left:4px solid var(--brand)">');
    html.push('  <div class="spread" style="margin-bottom:8px">');
    html.push('    <b>🕐 完整模拟</b>');
    html.push('    <span class="tiny">按原卷题序 · 限时</span>');
    html.push('  </div>');
    html.push('  <p class="tiny" style="margin:0 0 10px 0;line-height:1.7">' +
      '从第 1 题做到第 ' + p.total + ' 题，还原真实考试节奏。' +
      '交卷后出分模块成绩报告。</p>');
    html.push('  <div class="row" style="gap:8px;flex-wrap:wrap">');
    var _wholeSec = examSeconds(p.total, true, p.kind, p.region);
    html.push('    <button class="btn primary" data-mode="timed">限时模拟（' +
      Math.round(_wholeSec / 60) + ' 分钟）</button>');
    html.push('    <button class="btn" data-mode="free">不限时（练习模式）</button>');
    html.push('  </div>');
    html.push('</div>');

    // 分模块
    html.push('<h3 style="font-size:15px;margin:0 0 10px 0">分模块练习</h3>');
    html.push('<div class="rows">');
    mods.forEach(function (m) {
      html.push([
        '<div class="rowitem" style="cursor:pointer" data-mod="' + esc(m.cat) + '">',
        '  <span class="rno">' + esc(m.name.slice(0, 4)) + '</span>',
        '  <div style="flex:1;min-width:0">',
        '    <div class="rtxt" style="margin-bottom:2px">' + esc(m.name) + '</div>',
        '    <span class="tiny">' + m.count + ' 题</span>',
        '  </div>',
        '  <span class="pill">练习</span>',
        '</div>'
      ].join(''));
    });
    // 全模块（除完整模拟外的另一种入口）
    html.push([
      '<div class="rowitem" style="cursor:pointer" data-mod="all">',
      '  <span class="rno">全部</span>',
      '  <div style="flex:1;min-width:0">',
      '    <div class="rtxt" style="margin-bottom:2px">全部模块（练习模式）</div>',
      '    <span class="tiny">' + p.total + ' 题，不计时</span>',
      '  </div>',
      '  <span class="pill">练习</span>',
      '</div>'
    ].join(''));
    html.push('</div>');

    v.innerHTML = html.join('');

    $('#backList', v).onclick = function () { P.view(); };
    $$('[data-mode]', v).forEach(function (b) {
      b.onclick = function () {
        P.start(idx, p, 'all', b.dataset.mode === 'timed');
      };
    });
    $$('[data-mod]', v).forEach(function (el) {
      el.onclick = function () { P.start(idx, p, el.dataset.mod, false); };
    });
  };

  /* ═══════════════ 答题界面 ═══════════════ */
  P.start = function (idx, paperMeta, moduleCat, timed) {
    var v = document.getElementById('view');
    v.innerHTML = '<div class="empty"><div class="big">⏳</div><p>正在加载题目…</p></div>';

    // 需要从各分片里取出该卷的题目
    var needCats = moduleCat === 'all'
      ? paperMeta.modules.map(function (m) { return m.cat; })
      : [moduleCat];

    // 关键：必须把卷类型传给加载器，否则会从普通分片里按 qid 匹配，
    // 因同源数据 qid 相同，会把别的卷的题也捞进来（实测 130 题变成 209 题）。
    var kind = paperMeta.kind || '';

    loadQuestions(paperMeta.qids, needCats, function (pool) {
      if (!pool.length) {
        v.innerHTML = '<div class="empty"><div class="big">⚠</div><p>题目加载失败</p></div>';
        return;
      }
      // 严格按本卷 qid 集合过滤，双保险
      var want = {};
      paperMeta.qids.forEach(function (id) { want[String(id)] = true; });
      pool = pool.filter(function (q) { return want[String(q.id)]; });

      // 卷面顺序：先按模块顺序分组，组内再按模块内题号递增。
      // 不能先按 no 排序——no 是「模块内编号」，
      // 政治第1题与常识第1题都是 no=1，会交错成
      // 「政治1, 常识1, 言语1, ... 政治2, 常识2」的错乱卷面。
      var CAT_ORDER = ['politics', 'common', 'verbal', 'quantity', 'judge', 'graph', 'data', 'shenlun'];
      pool.sort(function (a, b) {
        var ia = CAT_ORDER.indexOf(a.cat), ib = CAT_ORDER.indexOf(b.cat);
        if (ia < 0) ia = 99;
        if (ib < 0) ib = 99;
        if (ia !== ib) return ia - ib;          // 模块顺序优先
        var na = parseInt(a.no) || 0, nb = parseInt(b.no) || 0;
        return na - nb;                          // 同模块内按题号
      });
      runSession(v, paperMeta, moduleCat, timed, pool);
    }, kind);
  };

  /* 按需加载题目：行测走 zt 分片，申论走 shenlun 数据，国考走 guokao 分片 */
  function loadQuestions(qids, cats, cb, paperKind) {
    var want = {};
    qids.forEach(function (id) { want[String(id)] = true; });
    var out = [];

    // 国考卷：从 zt/guokao.json 里取（带原卷题序）
    if (paperKind === 'guokao' || String((qids[0] || '')).indexOf('gk-') === 0) {
      loadShardJson('guokao', function (qs) {
        var got = (qs || []).filter(function (q) { return want[String(q.id)]; });
        cb(got);
      });
      return;
    }

    // 申论卷：从 shenlun 数据里取
    if (cats.length === 1 && cats[0] === 'shenlun') {
      loadShenlun(function (qs) {
        var got = (qs || []).filter(function (q) { return want[String(q.id)]; });
        got.sort(function (a, b) {
          var na = parseInt(a.no) || 0, nb = parseInt(b.no) || 0;
          return na - nb;
        });
        cb(got);
      });
      return;
    }

    var remain = cats.length;
    if (!remain) { cb([]); return; }

    var cached = window.ZLFX_ZHENTI && window.ZLFX_ZHENTI._shardOf;

    cats.forEach(function (cat) {
      var done = function (qs) {
        (qs || []).forEach(function (q) {
          if (want[String(q.id)]) out.push(q);
        });
        remain--;
        if (remain === 0) cb(out);
      };

      if (cached) {
        var have = cached(cat);
        if (have && have.length) { done(have); return; }
      }

      loadShardJson(cat, done);
    });
  }

  /* 加载一个 zt 分片 */
  var _shardCache = {};
  function loadShardJson(cat, cb) {
    if (_shardCache[cat]) { cb(_shardCache[cat]); return; }
    fetch('data/zt/' + cat + '.json')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (d) {
        var qs = d && d.questions ? d.questions : (Array.isArray(d) ? d : []);
        _shardCache[cat] = qs;
        cb(qs);
      })
      .catch(function (e) {
        console.warn('[papers] 加载分片失败', cat, e);
        cb([]);
      });
  }

  /* 加载申论数据（两个文件，按需注入） */
  var _slLoaded = false, _slCbs = [];
  function loadShenlun(cb) {
    // 已加载（页面可能已引入）
    if (window.__SHENLUN__ && window.__SHENLUN__.length) {
      cb(window.__SHENLUN__);
      return;
    }
    if (_slLoaded) { cb([]); return; }
    _slCbs.push(cb);

    var files = ['data/shenlun.js', 'data/shenlun-2025-2026.js'];
    var remain = files.length;

    files.forEach(function (src) {
      var s = document.createElement('script');
      s.src = src;
      s.onload = s.onerror = function () {
        remain--;
        if (remain === 0) {
          _slLoaded = true;
          // 第二个文件会合并进 __SHENLUN__
          var all = window.__SHENLUN__ || [];
          _slCbs.forEach(function (f) { f(all); });
          _slCbs = [];
        }
      };
      document.body.appendChild(s);
    });
  }

  /* 计算考试时长（秒）
   * 整卷模拟：优先用官方时长（国考行测固定 120 分钟），
   *           其他卷按题量 × 0.9 分钟估算；
   * 分模块练习：按该模块题量 × 0.9 分钟。
   * 按钮文案与实际倒计时都调用它，避免显示与倒计时不一致。 */
  function examSeconds(poolLen, isWholePaper, kind, region) {
    if (!poolLen) return 0;
    if (isWholePaper) {
      // 国考行测（kind 可能是 guokao 或 xingce，用 region 判断更可靠）：
      // 无论 130 题还是 135 题，考试时间都是 120 分钟
      if (kind === 'guokao' || region === '国考') return 120 * 60;
      // 其他省考按 0.9 分/题，但不低于 100 分钟
      return Math.max(100, Math.round(poolLen * 0.9)) * 60;
    }
    // 分模块：按模块题量
    return Math.round(poolLen * 0.9 * 60);
  }

  /* 答题会话 */
  function runSession(v, paperMeta, moduleCat, timed, pool) {
    var idx = 0;
    var answers = {};              // qid -> { sel:[], ok:bool }
    var startTs = Date.now();
    // 限时：统一走 examSeconds()，保证按钮显示与实际倒计时一致
    var limitSec = timed
      ? examSeconds(pool.length, !moduleCat, paperMeta && paperMeta.kind, paperMeta && paperMeta.region)
      : 0;
    var timerId = null;
    var finished = false;

    // 模块标签映射
    var CAT_LABEL = {
      politics: '政治', common: '常识', verbal: '言语', quantity: '数量',
      judge: '判断', graph: '图形', data: '资料', law: '法律'
    };

    function render() {
      var q = pool[idx];
      var a = answers[q.id];
      var show = !!a;
      var isShenlun = !!(q.refAnswer !== undefined || q.refPoints ||
                         q.materials !== undefined || q.title !== undefined ||
                         String(q.id || '').indexOf('sl-') === 0);
      var keys = q.optionKeys && q.optionKeys.length ? q.optionKeys : ['A', 'B', 'C', 'D'];
      var opts = q.options || [];
      var answeredN = Object.keys(answers).length;
      var okN = Object.keys(answers).filter(function (k) { return answers[k].ok; }).length;
      var elapsed = Math.floor((Date.now() - startTs) / 1000);
      var left = limitSec ? Math.max(0, limitSec - elapsed) : 0;

      // 选项：用 <table> 布局（flex 在部分浏览器环境宽度计算异常）
      var optHtml = '<table class="opt-table" style="width:100%;' +
        'max-width:100%;' +
        'border-collapse:separate;' +
        'border-spacing:0 9px;' +
        'table-layout:fixed;' +
        'box-sizing:border-box;' +
        'margin:0;' +
        'padding:0;' +
        '">' +
        opts.map(function (text, i) {
          var key = keys[i] || 'ABCD'[i];
          var isAns = String(q.answer || '').indexOf(key) >= 0;
          var picked = a && a.sel && a.sel.indexOf(key) >= 0;
          var bg = '#fff', bd = '#c5cddd', lbg = '#d8dfec', lfg = '#46506a';
          if (show) {
            if (isAns) { bg = '#e7f8f0'; bd = '#37c98b'; lbg = '#37c98b'; lfg = '#fff'; }
            else if (picked) { bg = '#fdecef'; bd = '#e0405a'; lbg = '#e0405a'; lfg = '#fff'; }
          } else if (picked) { bg = '#eef0ff'; bd = '#4f46e5'; lbg = '#4f46e5'; lfg = '#fff'; }
          return '<tr>' +
            '<td style="width:24px;padding:0;vertical-align:top;">' +
              '<span style="display:block;width:24px;height:24px;line-height:24px;' +
              'text-align:center;border-radius:7px;background:' + lbg + ';color:' + lfg + ';' +
              'font-size:12.5px;font-weight:700;margin-top:11px;box-sizing:border-box;">' + key + '</span>' +
            '</td>' +
            '<td class="opt-cell" data-k="' + key + '" style="vertical-align:top;background:' + bg + ';' +
              'border:1.5px solid ' + bd + ';border-radius:11px;padding:10px 13px;' +
              'font-size:14.5px;line-height:1.7;color:#1c2333;cursor:pointer;' +
              'overflow-wrap:anywhere;word-break:break-word;">' +
              (String(text || '').indexOf('缺失') >= 0
                ? '<span style="color:#d97706;font-size:13px">⚠ 源数据缺失，无法作答</span>'
                : (String(text || '').trim()
                    ? esc(text)
                    : '<span style="color:var(--text-3,#8b94a8);font-size:13px">（选项见上方原图）</span>')) +
              (show && isAns ? '<span style="float:right;font-size:11px;color:#16a34a;margin-left:8px;">✓</span>' : '') +
            '</td>' +
          '</tr>';
        }).join('') + '</table>';

      var title = moduleCat === 'all'
        ? (timed ? '完整模拟' : '全卷练习')
        : (CAT_LABEL[moduleCat] || moduleCat) + '专项';

      var html = [];
      // 顶部信息
      html.push('<div class="spread" style="margin-bottom:12px">');
      html.push('  <div><h1 style="font-size:16px">' + esc(title) + '</h1>');
      html.push('    <p class="sub"><span id="progText">' + (idx + 1) + ' / ' + pool.length +
        ' · 已答 ' + answeredN + (answeredN ? ' · 对 ' + okN : '') + '</span>' +
        (limitSec ? '<span id="timeText"> · 剩余 ' + fmtSec(left) + '</span>' : '') +
        '</p></div>');
      html.push('  <div class="row" style="gap:6px">');
      html.push('    <button class="btn sm" id="btnCard">答题卡</button>');
      html.push('    <button class="btn sm" id="quit">交卷</button>');
      html.push('  </div>');
      html.push('</div>');

      // 倒计时提醒
      if (limitSec && left <= 300) {
        html.push('<div class="tiny" style="margin-bottom:10px;padding:6px 10px;background:#fef2f2;' +
          'border-left:3px solid #dc2626;border-radius:4px;color:#991b1b">' +
          '⏰ 剩余时间不足 5 分钟，请尽快作答</div>');
      }

      // 题目卡
      html.push('<div class="card pad" style="margin-bottom:12px">');
      html.push('  <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:10px">');
      html.push('    <span class="pill brand">' + esc(CAT_LABEL[q.cat] || q.cat || '申论') + '</span>');
      html.push('    <span class="pill">第 ' + esc(q.no) + ' 题</span>');
      if (q.sub) html.push('    <span class="pill" style="font-size:11px">' + esc(q.sub) + '</span>');
      if ((q.flags || []).indexOf('dataMissing') >= 0) {
        html.push('    <span class="pill" style="background:#fef3c7;color:#92400e;font-size:11px">源数据缺失</span>');
      }
      html.push('    <span class="tiny" style="margin-left:auto">' + esc(paperMeta.year) +
        ' ' + esc(paperMeta.region) + '</span>');
      html.push('  </div>');

      // 申论材料（只取申论专用字段 materials；
      // 不回退 q.material，那是行测材料题字段，否则会与下面的行测材料块重复渲染）
      if (isShenlun) {
        var matText = q.materials || '';
        if (matText) {
          html.push('  <div style="margin-bottom:12px">');
          html.push('    <div class="tiny" style="margin-bottom:6px;color:var(--text-2)">给定资料</div>');
          html.push('    <div style="padding:12px;background:var(--bg-2,#f8fafc);border-radius:6px;' +
            'max-height:300px;overflow:auto;font-size:13px;line-height:1.85;' +
            'white-space:pre-wrap;border-left:3px solid #94a3b8">' + esc(matText) + '</div>');
          html.push('  </div>');
        }
      }

      // 材料（资料分析/言语材料题自带文字，缺了没法作答）
      // 长材料默认折叠到 190px 高，可点「展开」，避免把题干和选项挤到屏幕外
      if (q.material || (q.materialImgs || []).length) {
        var matLen = (q.material || '').length;
        var collapse = matLen > 150;          // 超过 260 字就折叠
        html.push('  <div style="margin-bottom:14px;border:1px solid var(--line,#e5e7eb);' +
          'border-radius:8px;overflow:hidden">');
        html.push('    <div style="padding:8px 12px;background:var(--bg-soft,#f1f5f9);' +
          'font-size:12.5px;color:var(--text-2,#5a6478);display:flex;gap:8px;align-items:center">');
        html.push('      <b>材料' + (q.matNo ? ' ' + esc(String(q.matNo)) : '') + '</b>');
        if (q.sub) html.push('      <span>' + esc(q.sub) + '</span>');
        if (collapse) {
          html.push('      <button type="button" id="btnMatToggle" ' +
            'style="margin-left:auto;padding:2px 10px;font-size:12px;border:1px solid var(--line,#c5cddd);' +
            'border-radius:6px;background:var(--card,#fff);color:var(--text-2,#5a6478);cursor:pointer">展开材料</button>');
        }
        html.push('    </div>');
        html.push('    <div id="matBody" style="padding:12px;' +
          (collapse ? 'max-height:120px;overflow:hidden;position:relative' : '') + '">');
        (q.materialImgs || []).forEach(function (src) {
          if (!src) return;                       // 跳过空值
          var isFormula = String(src).indexOf('公式图') >= 0;
          var style = isFormula
            ? 'height:auto;max-width:none;vertical-align:middle;display:inline-block;margin:2px'
            : 'max-width:100%;height:auto;display:block;margin-bottom:10px';
          html.push('      <img src="' + esc(String(src)) + '" alt="材料图表"' +
            ' loading="lazy"' +
            ' onerror="this.style.display=\'none\'"' +
            ' style="' + style + '">');
        });
        if (q.material) {
          html.push('      <div style="font-size:13.5px;line-height:1.9;' +
            'white-space:pre-wrap;color:var(--text,#1c2333)">' + esc(q.material) + '</div>');
        }
        html.push('    </div>');
        html.push('  </div>');
      }

      // 题干（申论用 title，行测用 stem）
      var stemText = q.stem || q.title || '';
      html.push('  <div style="font-size:15px;line-height:1.9;white-space:pre-wrap">' +
        esc(stemText) + '</div>');

      // 题目配图（图形推理、资料分析图表、数量关系公式图等）
      // 这些题的 options 是空的，内容全在图里，不渲染就等于题目不完整。
      if ((q.imgs || []).length) {
        var _imgs = q.imgs.filter(function (x) { return x; });
        if (_imgs.length) {
          html.push('  <div style="margin-top:12px;display:flex;flex-direction:column;gap:8px">');
          _imgs.forEach(function (src) {
            var isFormula = String(src).indexOf('公式图') >= 0;
            // 公式图是 15x33 这类小片段，放大就会糊；
            // 按原始尺寸显示，不设 max-width:100%
            var style = isFormula
              ? 'height:auto;max-width:none;vertical-align:middle;display:inline-block;margin:2px'
              : 'max-width:100%;height:auto;border-radius:8px;' +
                'border:1px solid var(--line,#e5e7eb)';
            html.push('    <img src="' + esc(String(src)) + '" alt="题目图"' +
              ' loading="lazy"' +
              ' onerror="this.style.display=\'none\'"' +
              ' style="' + style + '">');
          });
          html.push('  </div>');
        }
      }
      if (isShenlun && q.requirements) {
        html.push('  <div class="tiny" style="margin-top:8px;line-height:1.8;color:var(--text-2)">' +
          esc(q.requirements) + '</div>');
      }
      html.push('</div>');

      // 选项区
      if (isShenlun) {
        var metaBits = [];
        if (q.type) metaBits.push(q.type);
        if (q.score) metaBits.push(q.score + ' 分');
        if (q.wordLimit && q.wordLimit.length === 2) {
          metaBits.push(q.wordLimit[0] + '-' + q.wordLimit[1] + ' 字');
        }
        html.push('<div class="card pad" style="margin-bottom:12px">');
        html.push('  <div class="row" style="gap:6px;margin-bottom:10px;flex-wrap:wrap">');
        metaBits.forEach(function (t) {
          html.push('    <span class="pill" style="font-size:11px">' + esc(t) + '</span>');
        });
        html.push('  </div>');
        html.push('  <div class="tiny" style="margin-bottom:10px;color:var(--text-2)">' +
          '本题为主观题，请对照参考答案自评</div>');
        html.push('  <button class="btn primary" id="revealRef">显示参考答案</button>');
        html.push('  <div id="refBox" style="display:none;margin-top:12px">');
        if (q.refPoints && q.refPoints.length) {
          html.push('    <div class="tiny" style="margin-bottom:8px"><b>评分要点</b></div>');
          html.push('    <div style="font-size:13px;line-height:1.9;padding:10px 12px;' +
            'background:#eff6ff;border-radius:6px;border-left:3px solid #3b82f6">');
          q.refPoints.forEach(function (pt, i) {
            html.push('      <div style="margin-bottom:4px">' + (i + 1) + '. ' + esc(pt) + '</div>');
          });
          html.push('    </div>');
        }
        var refA = q.refAnswer || q.explain || '';
        if (refA) {
          html.push('    <div style="font-size:14px;line-height:1.9;white-space:pre-wrap;' +
            'padding:12px;background:#f0fdf4;border-radius:6px;border-left:3px solid #16a34a;' +
            'margin-top:10px">' + esc(refA) + '</div>');
        }
        html.push('  </div>');
        html.push('</div>');
      } else {
        html.push('<div class="card pad" style="margin-bottom:12px">');
        html.push('  <div class="options" style="display:grid;gap:8px">' + optHtml + '</div>');
        html.push('</div>');
      }

      // 解析（交卷后或已答后）
      if (show) {
        html.push('<div class="card pad" style="margin-bottom:12px;border-left:4px solid ' +
          (a.ok ? '#16a34a' : '#dc2626') + '">');
        html.push('  <div style="margin-bottom:8px"><b>' +
          (a.ok ? '✅ 正确' : '❌ 错误') + '</b> <span class="tiny">答案：' +
          esc(q.answer || '?') + '</span></div>');
        html.push('  <div style="font-size:14px;line-height:1.9;white-space:pre-wrap">' +
          esc(q.explain || '（无解析）') + '</div>');
        html.push('</div>');
      }

      // 底部导航
      html.push('<div class="row" style="gap:8px;margin-bottom:20px">');
      html.push('  <button class="btn" id="prevQ"' + (idx === 0 ? ' disabled' : '') + '>← 上一题</button>');
      if (isShenlun) {
        html.push('  <span style="flex:1"></span>');
        html.push('  <button class="btn" id="nextQ"' +
          (idx === pool.length - 1 ? ' disabled' : '') + '>下一题 →</button>');
      } else {
        html.push(show ? '<button class="btn" id="nextQ2">下一题 →</button>'
          : '<button class="btn primary" id="checkQ">对答案</button>');
        html.push('  <span style="flex:1"></span>');
        html.push('  <button class="btn" id="nextQ"' +
          (idx === pool.length - 1 ? ' disabled' : '') + '>跳过 →</button>');
      }
      html.push('</div>');

      // 答题卡浮层
      html.push('<div id="cardPanel" style="display:none;position:fixed;inset:0;z-index:9000;' +
        'background:rgba(0,0,0,.5)" onclick="if(event.target===this)this.style.display=\'none\'">');
      html.push('  <div style="position:absolute;right:0;top:0;bottom:0;width:min(420px,92vw);' +
        'background:var(--bg,#fff);overflow:auto;padding:16px">');
      html.push('    <div class="spread" style="margin-bottom:12px">');
      html.push('      <b>答题卡</b>');
      html.push('      <button class="btn sm" id="closeCard">关闭</button>');
      html.push('    </div>');
      html.push('    <div class="tiny" style="margin-bottom:10px;color:var(--text-2)">' +
        '已答 ' + answeredN + ' / ' + pool.length + '</div>');
      html.push('    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(46px,1fr));gap:6px">');
      pool.forEach(function (q2, i) {
        var aa = answers[q2.id];
        var bg = aa ? (aa.ok ? '#16a34a' : '#dc2626') : '#e5e7eb';
        var fg = aa ? '#fff' : '#374151';
        html.push('      <button data-jump="' + i + '" style="padding:8px 0;border-radius:6px;' +
          'border:1px solid var(--line);background:' + bg + ';color:' + fg + ';font-size:12px">' +
          (i + 1) + '</button>');
      });
      html.push('    </div>');
      html.push('  </div>');
      html.push('</div>');

      v.innerHTML = html.join('');

      // ── 事件绑定 ──
      // 材料折叠开关（长材料默认折叠，避免把题干挤到屏幕外）
      var mt = document.getElementById('btnMatToggle');
      if (mt) mt.onclick = function () {
        var mb = document.getElementById('matBody');
        if (!mb) return;
        var expanded = mb.style.maxHeight === 'none';
        mb.style.maxHeight = expanded ? '120px' : 'none';
        mb.style.overflow = expanded ? 'hidden' : 'visible';
        mt.textContent = expanded ? '展开材料' : '收起材料';
      };

      // 申论：显示参考答案
      var rv = $('#revealRef', v);
      if (rv) rv.onclick = function () {
        var rb = $('#refBox', v);
        if (rb) rb.style.display = rb.style.display === 'block' ? 'none' : 'block';
      };

      // 选项点击（表格布局下选择器是 .opt-cell）
      $$('.opt-cell', v).forEach(function (b) {
        b.onclick = function () {
          if (answers[q.id]) return;
          var key = b.dataset.k;
          var multi = String(q.answer || '').length > 1;
          var cur = (answers[q.id] && answers[q.id].sel) || [];
          if (multi) {
            var i2 = cur.indexOf(key);
            if (i2 >= 0) cur.splice(i2, 1); else cur.push(key);
          } else {
            cur = [key];
          }
          answers[q.id] = { sel: cur.slice(), ok: false };
          if (!multi) judge(q);
          render();
        };
      });

      var cq = $('#checkQ', v);
      if (cq) cq.onclick = function () { judge(q); render(); };

      $('#prevQ', v).onclick = function () { if (idx > 0) { idx--; render(); } };
      var nx = $('#nextQ', v);
      if (nx) nx.onclick = function () {
        if (idx < pool.length - 1) { idx++; render(); }
      };
      var nx2 = $('#nextQ2', v);
      if (nx2) nx2.onclick = function () {
        if (idx < pool.length - 1) { idx++; render(); }
        else finish();
      };

      $('#btnCard', v).onclick = function () {
        var cp = $('#cardPanel', v);
        if (cp) cp.style.display = 'block';
      };
      var cc = $('#closeCard', v);
      if (cc) cc.onclick = function () {
        var cp = $('#cardPanel', v);
        if (cp) cp.style.display = 'none';
      };
      $$('[data-jump]', v).forEach(function (b) {
        b.onclick = function () {
          idx = parseInt(b.dataset.jump);
          render();
        };
      });

      $('#quit', v).onclick = function () { finish(); };
    }

    function judge(q) {
      var a = answers[q.id];
      if (!a) return;
      var sel = a.sel.slice().sort().join('');
      var ans = String(q.answer || '').split('').sort().join('');
      a.ok = sel === ans;
      if (a.ok) removeWrong(q.id); else addWrong(q.id);
    }

    function finish() {
      if (finished) return;
      finished = true;
      if (timerId) clearInterval(timerId);

      var ids = Object.keys(answers);
      var okN = ids.filter(function (k) { return answers[k].ok; }).length;
      var elapsed = Math.round((Date.now() - startTs) / 1000);

      // 分模块统计
      var byMod = {};
      pool.forEach(function (q) {
        var c = q.cat || 'other';
        if (!byMod[c]) byMod[c] = { total: 0, answered: 0, ok: 0 };
        byMod[c].total++;
        var a = answers[q.id];
        if (a) {
          byMod[c].answered++;
          if (a.ok) byMod[c].ok++;
        }
      });

      // 记录历史
      addHist({
        paper: paperMeta.paper,
        year: paperMeta.year,
        region: paperMeta.region,
        moduleCat: moduleCat,
        total: pool.length,
        answered: ids.length,
        score: okN,
        elapsed: elapsed,
        ts: Date.now()
      });

      var CAT_LABEL2 = {
        politics: '政治理论', common: '常识判断', verbal: '言语理解',
        quantity: '数量关系', judge: '判断推理', graph: '图形推理', data: '资料分析'
      };

      var rows = Object.keys(byMod).map(function (c) {
        var m = byMod[c];
        var rate = m.answered ? Math.round(m.ok / m.answered * 100) : 0;
        return '<div class="spread" style="padding:8px 0;border-bottom:1px solid var(--line)">' +
          '<span>' + esc(CAT_LABEL2[c] || c) + '</span>' +
          '<span class="tiny">' + m.ok + '/' + m.answered +
          '（共' + m.total + '）<b style="margin-left:8px;color:' +
          (rate >= 80 ? '#16a34a' : rate >= 60 ? '#d97706' : '#dc2626') + '">' +
          rate + '%</b></span></div>';
      }).join('');

      var h = [];
      h.push('<div class="card pad" style="padding:28px 20px">');
      h.push('  <div style="text-align:center;margin-bottom:18px">');
      h.push('    <div style="font-size:40px">' +
        (ids.length && okN / ids.length >= 0.8 ? '🎉' : '💪') + '</div>');
      h.push('    <h2 style="margin:8px 0 4px 0">交卷完成</h2>');
      h.push('    <p class="sub">' + esc(paperMeta.paper) + '</p>');
      h.push('  </div>');
      h.push('  <div style="display:flex;gap:24px;justify-content:center;margin:20px 0;flex-wrap:wrap">');
      h.push('    <div style="text-align:center"><div class="tiny">得分</div>' +
        '<div style="font-size:26px;font-weight:700;color:#16a34a">' + okN + '</div></div>');
      h.push('    <div style="text-align:center"><div class="tiny">已答</div>' +
        '<div style="font-size:26px;font-weight:700">' + ids.length + '</div></div>');
      h.push('    <div style="text-align:center"><div class="tiny">总题数</div>' +
        '<div style="font-size:26px;font-weight:700">' + pool.length + '</div></div>');
      h.push('    <div style="text-align:center"><div class="tiny">正确率</div>' +
        '<div style="font-size:26px;font-weight:700">' +
        (ids.length ? Math.round(okN / ids.length * 100) + '%' : '—') + '</div></div>');
      h.push('    <div style="text-align:center"><div class="tiny">用时</div>' +
        '<div style="font-size:26px;font-weight:700">' + fmtSec(elapsed) + '</div></div>');
      h.push('  </div>');
      h.push('  <h3 style="font-size:14px;margin:18px 0 8px 0">分模块成绩</h3>');
      h.push('  <div>' + rows + '</div>');
      h.push('  <div class="row" style="gap:10px;justify-content:center;margin-top:22px">');
      h.push('    <button class="btn primary" id="againBtn">再练一次</button>');
      h.push('    <button class="btn" id="wrongBtn">看错题</button>');
      h.push('    <button class="btn" id="backList2">返回套卷</button>');
      h.push('  </div>');
      h.push('</div>');

      v.innerHTML = h.join('');

      $('#againBtn', v).onclick = function () { P.start(null, paperMeta, moduleCat, timed); };
      $('#backList2', v).onclick = function () { P.view(); };
      $('#wrongBtn', v).onclick = function () {
        var wrongIds = Object.keys(answers).filter(function (k) { return !answers[k].ok; });
        if (!wrongIds.length) { alert('本次没有错题 🎉'); return; }
        var wp = pool.filter(function (q) { return wrongIds.indexOf(q.id) >= 0; });
        runSession(v, paperMeta, moduleCat, false, wp);
      };
    }

    // 计时器
    if (limitSec) {
      timerId = setInterval(function () {
        if (finished) { clearInterval(timerId); return; }
        var elapsed = Math.floor((Date.now() - startTs) / 1000);
        if (elapsed >= limitSec) {
          clearInterval(timerId);
          alert('时间到，自动交卷');
          finish();
        } else {
          // 只更新倒计时文字，不整页重绘
          var tt = $('#timeText', v);
          if (tt) tt.textContent = ' · 剩余 ' + fmtSec(limitSec - elapsed);
        }
      }, 1000);
    }

    render();
  }

})();

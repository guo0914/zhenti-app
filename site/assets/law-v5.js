/* =========================================================
   法律专业科目 · 单页应用
   数据: site/data/zt/law.json（与 verbal 等同构，兼容现有题库格式）
   功能: 专项练习（按科目/章节）/ 综合练习（单科随机/跨科配比）/ 错题复习
   ========================================================= */
(function () {
  'use strict';

  var LAW = window.ZLFX_LAW = {};
  var LS_WRONG = 'zlfx.law.wrong';
  var LS_STATS = 'zlfx.law.stats';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  /* ── 数据缓存 ── */
  var _data = null, _loading = false, _error = '';

  function getWrong() {
    try { return JSON.parse(localStorage.getItem(LS_WRONG) || '[]'); } catch (e) { return []; }
  }
  function setWrong(a) { try { localStorage.setItem(LS_WRONG, JSON.stringify(a.slice(-500))); } catch (e) {} }
  function addWrong(id) {
    var w = getWrong();
    if (w.indexOf(id) < 0) { w.push(id); setWrong(w); }
  }
  function removeWrong(id) {
    var w = getWrong(), i = w.indexOf(id);
    if (i >= 0) { w.splice(i, 1); setWrong(w); }
  }
  function getStats() {
    try { return JSON.parse(localStorage.getItem(LS_STATS) || '{}'); } catch (e) { return {}; }
  }
  function addStat(id, ok) {
    var s = getStats();
    if (!s[id]) s[id] = { n: 0, ok: 0 };
    s[id].n++;
    if (ok) s[id].ok++;
    try { localStorage.setItem(LS_STATS, JSON.stringify(s)); } catch (e) {}
  }

  /* ── 加载题库 ── */
  function loadData(cb) {
    // 已内联或已加载
    if (_data) { cb && cb(_data); return; }
    if (window.__LAW_QUESTIONS__) {
      _data = window.__LAW_QUESTIONS__;
      cb && cb(_data);
      return;
    }
    if (_loading) return;
    _loading = true;
    var s = document.createElement('script');
    s.src = 'data/zt/law.js';
    s.onload = function () {
      _loading = false;
      _data = window.__LAW_QUESTIONS__ || [];
      cb && cb(_data);
    };
    s.onerror = function () {
      _loading = false;
      _error = '法律题库加载失败';
      cb && cb([]);
    };
    document.body.appendChild(s);
  }

  /* ═══════════════ 首页：专项 / 综合 ═══════════════ */
  LAW.view = function () {
    var v = document.getElementById('view');
    if (!v) return;

    v.innerHTML = '<div class="empty"><div class="big">⏳</div><p>正在加载法律题库…</p></div>';

    loadData(function (data) {
      if (!data.length) {
        v.innerHTML = '<div class="empty"><div class="big">⚖</div><p>' +
          (_error || '暂无法律题目') + '</p>' +
          '<p class="tiny">请先运行 scripts/ocr_law.py 与 parse_law.py 生成题库</p></div>';
        return;
      }
      renderHome(v, data);
    });
  };

  function renderHome(v, data) {
    // 按科目分组
    var bySubject = {};
    data.forEach(function (q) {
      var s = q.region || '其他';
      if (!bySubject[s]) bySubject[s] = { total: 0, subs: {}, years: {} };
      bySubject[s].total++;
      var sub = q.sub || '综合';
      bySubject[s].subs[sub] = (bySubject[s].subs[sub] || 0) + 1;
      bySubject[s].years[q.year] = (bySubject[s].years[q.year] || 0) + 1;
    });

    var subjects = Object.keys(bySubject).sort(function (a, b) {
      return bySubject[b].total - bySubject[a].total;
    });
    var wrong = getWrong();
    var stats = getStats();
    var done = Object.keys(stats).length;
    var okN = Object.keys(stats).reduce(function (s, k) { return s + (stats[k].ok || 0); }, 0);
    var allN = Object.keys(stats).reduce(function (s, k) { return s + (stats[k].n || 0); }, 0);

    v.innerHTML = [
      '<div class="spread" style="margin-bottom:14px">',
      '  <div><h1>法律专业科目</h1>',
      '    <p class="sub">' + data.length + ' 题 · ' + subjects.length + ' 个科目 · 法考真金题</p></div>',
      '</div>',

      // 总览
      '<div class="card pad" style="margin-bottom:14px">',
      '  <div class="row" style="gap:18px;flex-wrap:wrap">',
      '    <div><div class="tiny">总题数</div><div style="font-size:20px;font-weight:700">' + data.length + '</div></div>',
      '    <div><div class="tiny">已练</div><div style="font-size:20px;font-weight:700">' + done + '</div></div>',
      '    <div><div class="tiny">正确率</div><div style="font-size:20px;font-weight:700">' +
           (allN ? Math.round(okN / allN * 100) + '%' : '—') + '</div></div>',
      '    <div><div class="tiny">错题</div><div style="font-size:20px;font-weight:700;color:#dc2626">' +
           wrong.length + '</div></div>',
      '  </div>',
      '</div>',

      // 两种模式
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">',
      '  <div class="card pad" style="cursor:pointer;border-left:4px solid var(--brand)" id="modeZhuanxiang">',
      '    <div style="font-size:20px;margin-bottom:6px">🎯</div>',
      '    <div style="font-weight:700;font-size:15px;margin-bottom:4px">专项练习</div>',
      '    <div class="tiny" style="line-height:1.6">按科目、章节逐项攻克<br>适合查漏补缺</div>',
      '  </div>',
      '  <div class="card pad" style="cursor:pointer;border-left:4px solid #16a34a" id="modeZonghe">',
      '    <div style="font-size:20px;margin-bottom:6px">🎲</div>',
      '    <div style="font-weight:700;font-size:15px;margin-bottom:4px">综合练习</div>',
      '    <div class="tiny" style="line-height:1.6">单科随机或跨科组卷<br>模拟真实考试</div>',
      '  </div>',
      '</div>',

      // 错题本入口
      wrong.length ? [
        '<div class="card pad" style="margin-bottom:16px;cursor:pointer" id="modeWrong">',
        '  <div class="spread">',
        '    <div><b>❌ 错题复习</b> <span class="pill" style="font-size:11px;background:#fee2e2;color:#991b1b">' +
             wrong.length + ' 题</span></div>',
        '    <span class="tiny">点击开始 →</span>',
        '  </div>',
        '</div>'
      ].join('') : '',

      // 科目列表
      '<h3 style="font-size:15px;margin:0 0 10px 0">按科目练习</h3>',
      '<div class="rows">',
      subjects.map(function (s) {
        var info = bySubject[s];
        var subCount = Object.keys(info.subs).length;
        return [
          '<div class="rowitem" style="cursor:pointer" data-subject="' + esc(s) + '">',
          '  <span class="rno">' + esc(s) + '</span>',
          '  <div style="flex:1;min-width:0">',
          '    <div class="rtxt" style="margin-bottom:2px">' + subCount + ' 个章节</div>',
          '    <span class="tiny">' + info.total + ' 题</span>',
          '  </div>',
          '  <span class="pill">练习</span>',
          '</div>'
        ].join('');
      }).join(''),
      '</div>'
    ].join('');

    $('#modeZhuanxiang', v).onclick = function () { LAW.viewZhuanxiang(data); };
    $('#modeZonghe', v).onclick = function () { LAW.viewZonghe(data); };
    var mw = $('#modeWrong', v);
    if (mw) mw.onclick = function () { LAW.startPractice(data, wrong.slice(), '错题复习'); };

    $$('[data-subject]', v).forEach(function (el) {
      el.onclick = function () { LAW.viewSubject(data, el.dataset.subject); };
    });
  }

  /* ═══════════════ 专项练习：科目 → 章节 ═══════════════ */
  LAW.viewZhuanxiang = function (data) {
    var v = document.getElementById('view');
    var bySubject = {};
    data.forEach(function (q) {
      var s = q.region || '其他';
      if (!bySubject[s]) bySubject[s] = [];
      bySubject[s].push(q);
    });
    var subjects = Object.keys(bySubject);

    v.innerHTML = [
      '<div class="spread" style="margin-bottom:14px">',
      '  <div><h1>专项练习</h1><p class="sub">选择科目，再选章节</p></div>',
      '  <button class="btn sm" id="backHome">← 返回</button>',
      '</div>',
      '<div class="rows">',
      subjects.map(function (s) {
        var qs = bySubject[s];
        var subs = {};
        qs.forEach(function (q) { subs[q.sub || '综合'] = (subs[q.sub || '综合'] || 0) + 1; });
        return [
          '<div class="rowitem" style="cursor:pointer" data-go="' + esc(s) + '">',
          '  <span class="rno">' + esc(s) + '</span>',
          '  <div style="flex:1;min-width:0">',
          '    <div class="rtxt">' + Object.keys(subs).length + ' 章节 · ' + qs.length + ' 题</div>',
          '  </div>',
          '  <span class="pill">→</span>',
          '</div>'
        ].join('');
      }).join(''),
      '</div>'
    ].join('');

    $('#backHome', v).onclick = function () { LAW.view(); };
    $$('[data-go]', v).forEach(function (el) {
      el.onclick = function () { LAW.viewSubject(data, el.dataset.go); };
    });
  };

  /* ═══════════════ 单科目：章节列表 + 开始 ═══════════════ */
  LAW.viewSubject = function (data, subject) {
    var v = document.getElementById('view');
    var qs = data.filter(function (q) { return (q.region || '其他') === subject; });
    if (!qs.length) { LAW.view(); return; }

    var subs = {};
    qs.forEach(function (q) {
      var s = q.sub || '综合';
      if (!subs[s]) subs[s] = [];
      subs[s].push(q);
    });
    var stats = getStats();

    v.innerHTML = [
      '<div class="spread" style="margin-bottom:14px">',
      '  <div><h1>' + esc(subject) + '</h1><p class="sub">' + qs.length + ' 题 · ' +
           Object.keys(subs).length + ' 章节</p></div>',
      '  <button class="btn sm" id="back">← 返回</button>',
      '</div>',

      '<div class="card pad" style="margin-bottom:14px">',
      '  <div class="row" style="gap:8px;flex-wrap:wrap">',
      '    <span class="tiny" style="align-self:center">本卷抽题：</span>',
      '    <button class="btn sm primary" data-n="20">20 题</button>',
      '    <button class="btn sm" data-n="50">50 题</button>',
      '    <button class="btn sm" data-n="100">100 题</button>',
      '  </div>',
      '</div>',

      '<h3 style="font-size:15px;margin:0 0 10px 0">选择章节</h3>',
      '<div class="rows">',
      Object.keys(subs).sort().map(function (s) {
        var list = subs[s];
        var done = list.filter(function (q) { return stats[q.id]; }).length;
        var okc = list.reduce(function (n, q) {
          var st = stats[q.id];
          return n + (st && st.ok ? 1 : 0);
        }, 0);
        return [
          '<div class="rowitem" style="cursor:pointer" data-sub="' + esc(s) + '">',
          '  <span class="rno">' + esc(s).slice(0, 6) + '</span>',
          '  <div style="flex:1;min-width:0">',
          '    <div class="rtxt" style="margin-bottom:2px">' + esc(s) + '</div>',
          '    <span class="tiny">' + list.length + ' 题' +
               (done ? ' · 已练 ' + done + (okc ? ' · 对 ' + okc : '') : '') + '</span>',
          '  </div>',
          '  <span class="pill">开始</span>',
          '</div>'
        ].join('');
      }).join(''),
      '</div>'
    ].join('');

    $('#back', v).onclick = function () { LAW.viewZhuanxiang(data); };

    $$('[data-n]', v).forEach(function (b) {
      b.onclick = function () {
        var n = parseInt(b.dataset.n);
        var pool = shuffle(qs.slice()).slice(0, n);
        LAW.startPractice(data, pool.map(function (q) { return q.id; }), subject + ' · 随机' + n + '题');
      };
    });

    $$('[data-sub]', v).forEach(function (el) {
      el.onclick = function () {
        var s = el.dataset.sub;
        var list = subs[s];
        LAW.startPractice(data, list.map(function (q) { return q.id; }), s);
      };
    });
  };

  /* ═══════════════ 综合练习 ═══════════════ */
  LAW.viewZonghe = function (data) {
    var v = document.getElementById('view');
    var bySubject = {};
    data.forEach(function (q) {
      var s = q.region || '其他';
      bySubject[s] = (bySubject[s] || 0) + 1;
    });
    var subjects = Object.keys(bySubject);

    v.innerHTML = [
      '<div class="spread" style="margin-bottom:14px">',
      '  <div><h1>综合练习</h1><p class="sub">模拟真实考试组卷</p></div>',
      '  <button class="btn sm" id="back">← 返回</button>',
      '</div>',

      '<div class="card pad" style="margin-bottom:14px">',
      '  <h3 style="margin:0 0 10px 0;font-size:15px">🎲 全科随机</h3>',
      '  <p class="tiny" style="margin:0 0 10px 0">从所有科目中随机抽取，检验综合水平</p>',
      '  <div class="row" style="gap:8px">',
      '    <button class="btn primary" data-all="20">20 题</button>',
      '    <button class="btn" data-all="50">50 题</button>',
      '    <button class="btn" data-all="100">100 题</button>',
      '  </div>',
      '</div>',

      '<div class="card pad" style="margin-bottom:14px">',
      '  <h3 style="margin:0 0 10px 0;font-size:15px">📐 按法考配比组卷</h3>',
      '  <p class="tiny" style="margin:0 0 10px 0">' +
         '按客观题常见配比（民法 20% 刑法 18% 刑诉 15% 民诉 12% 行政 12% 商经 15% 理论 5% 三国 3%）抽取</p>',
      '  <div class="row" style="gap:8px">',
      '    <button class="btn primary" data-mix="100">模拟卷 100 题</button>',
      '  </div>',
      '  <div id="mixInfo" class="tiny" style="margin-top:8px;color:var(--text-2)"></div>',
      '</div>',

      '<h3 style="font-size:15px;margin:0 0 10px 0">单科随机</h3>',
      '<div class="rows">',
      subjects.map(function (s) {
        return [
          '<div class="rowitem" style="cursor:pointer" data-one="' + esc(s) + '">',
          '  <span class="rno">' + esc(s) + '</span>',
          '  <div style="flex:1;min-width:0"><div class="rtxt">' + bySubject[s] + ' 题</div></div>',
          '  <span class="pill">随机</span>',
          '</div>'
        ].join('');
      }).join(''),
      '</div>'
    ].join('');

    $('#back', v).onclick = function () { LAW.view(); };

    $$('[data-all]', v).forEach(function (b) {
      b.onclick = function () {
        var n = parseInt(b.dataset.all);
        var pool = shuffle(data.slice()).slice(0, n);
        LAW.startPractice(data, pool.map(function (q) { return q.id; }), '全科随机 ' + n + '题');
      };
    });

    $$('[data-one]', v).forEach(function (el) {
      el.onclick = function () {
        var s = el.dataset.one;
        var qs = data.filter(function (q) { return (q.region || '其他') === s; });
        LAW.startPractice(data, shuffle(qs).slice(0, 30).map(function (q) { return q.id; }),
          s + ' · 随机30题');
      };
    });

    $$('[data-mix]', v).forEach(function (b) {
      b.onclick = function () {
        var total = parseInt(b.dataset.mix);
        var ratio = { '民法': 0.20, '刑法': 0.18, '刑诉法': 0.15, '民诉法': 0.12,
                      '行政法': 0.12, '商经知': 0.15, '理论法': 0.05, '三国法': 0.03 };
        var picked = [], info = [];
        Object.keys(ratio).forEach(function (s) {
          var qs = data.filter(function (q) { return (q.region || '') === s; });
          if (!qs.length) return;
          var want = Math.max(1, Math.round(total * ratio[s]));
          var got = shuffle(qs.slice()).slice(0, Math.min(want, qs.length));
          picked = picked.concat(got);
          info.push(s + ' ' + got.length);
        });
        // 补齐差额
        while (picked.length < total) {
          var extra = shuffle(data.slice()).slice(0, total - picked.length);
          picked = picked.concat(extra);
        }
        picked = picked.slice(0, total);
        LAW.startPractice(data, picked.map(function (q) { return q.id; }), '模拟卷 · ' + total + '题');
      };
    });
  };

  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }

  /* ═══════════════ 答题界面 ═══════════════ */
  LAW.startPractice = function (allData, ids, title) {
    var v = document.getElementById('view');
    var pool = ids.map(function (id) {
      return allData.filter(function (q) { return q.id === id; })[0];
    }).filter(Boolean);

    if (!pool.length) { LAW.view(); return; }

    var idx = 0;
    var answers = {};   // id -> { sel, ok }

    function render() {
      var q = pool[idx];
      var a = answers[q.id];
      // 只有「已判过」才算揭晓答案；多选仅仅勾选一项不能立刻出解析
      var show = !!(a && a.revealed);
      var keys = q.optionKeys || ['A', 'B', 'C', 'D'];
      var opts = q.options || [];

      // 选项用 <table> 布局（flex 在部分浏览器环境宽度计算异常）
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
          var isAns = (q.answer || '').indexOf(key) >= 0;
          var picked = a && (a.sel || []).indexOf(key) >= 0;
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
              esc(text) +
              (show && isAns ? '<span style="float:right;font-size:11px;color:#16a34a;margin-left:8px;">✓</span>' : '') +
            '</td>' +
          '</tr>';
        }).join('') + '</table>';

      var doneN = Object.keys(answers).filter(function (k) { return answers[k].revealed; }).length;
      var okN = Object.keys(answers).filter(function (k) { return answers[k].ok; }).length;

      // 章节/考点信息
      var metaLine = [q.chapter, q.kaodian].filter(Boolean).join(' · ');

      // 原书页面图片：law_img/{科目代码}-{4位页码}.jpg
      var SUBJECT_IMG = {
        '刑法': 'xf', '民法': 'mf', '民诉法': 'msf', '刑诉法': 'xsf',
        '行政法': 'xzf', '商经知': 'sxz', '三国法': 'sgf', '理论法': 'llf'
      };
      var code = SUBJECT_IMG[q.region] || 'law';
      // 图片地址：优先 WebP；服务器会在文件缺失时按需从原书 PDF 生成
      var imgBase = q.page ? ('data/zt/law_img/' + code + '-' +
        String(q.page).padStart(4, '0')) : '';
      var imgUrl = imgBase ? (imgBase + '.webp') : '';
      var imgUrlAlt = imgBase ? (imgBase + '.jpg') : '';

      v.innerHTML = [
        '<div class="spread" style="margin-bottom:12px">',
        '  <div><h1 style="font-size:17px">' + esc(title) + '</h1>',
        '    <p class="sub">' + (idx + 1) + ' / ' + pool.length + ' · 已答 ' + doneN +
             (doneN ? ' · 正确 ' + okN : '') + '</p></div>',
        '  <button class="btn sm" id="quit">退出</button>',
        '</div>',

        '<div class="card pad" style="margin-bottom:12px">',
        '  <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:10px">',
        '    <span class="pill brand">' + esc(q.region || '') + '</span>',
        '    <span class="pill">' + esc(q.qtype || '') + '</span>',
        q.source ? '    <span class="pill" style="font-size:11px">' + esc(q.source) + '</span>' : '',
        // 原书页面对照按钮（异步探测图片是否存在后插入）
        '<span id="imgSlot"></span>',
        '    <span class="tiny" style="margin-left:auto">第 ' + (q.page || '?') + ' 页</span>',
        '  </div>',
        // 数据质量提示
        (q.flags && q.flags.length)
          ? '  <div class="tiny" style="margin-bottom:10px;padding:6px 10px;background:#fffbeb;' +
            'border-left:3px solid #f59e0b;border-radius:4px;color:#92400e;line-height:1.7">' +
            '⚠ 本题数据可能有误：' + q.flags.map(esc).join('、') +
            '（OCR 识别问题，<span style="text-decoration:underline;cursor:pointer;color:#b45309" ' +
            'data-open-page="1">核对原书第 ' + (q.page || '?') + ' 页</span>）</div>'
          : '',
        metaLine ? '  <div class="tiny" style="margin-bottom:10px;color:var(--text-2)">' + esc(metaLine) + '</div>' : '',
        '  <div style="font-size:15px;line-height:1.9;white-space:pre-wrap">' + esc(q.stem) + '</div>',
        // 原图预览区（默认隐藏，探测到图片后才启用）
        imgUrl ? '  <div id="pageImgBox" style="display:none;margin-top:12px;padding-top:12px;' +
                 'border-top:1px dashed var(--line)">' +
                 '<div class="row" style="margin-bottom:8px">' +
                 '<span class="tiny" style="color:var(--text-2)">原书第 ' + (q.page || '?') + ' 页</span>' +
                 '<span style="flex:1"></span>' +
                 '<button class="btn sm" id="btnZoomImg" style="font-size:11px">放大</button>' +
                 '<button class="btn sm" id="btnHideImg" style="font-size:11px">收起</button>' +
                 '</div>' +
                 '<img id="pageImg" data-src="' + imgUrl + '" alt="原书页面" ' +
                 'style="width:100%;border:1px solid var(--line);border-radius:6px;cursor:zoom-in">' +
                 '</div>' : '',
        '</div>',

        '<div class="card pad" style="margin-bottom:12px">',
        '  <div class="options" style="display:grid;gap:8px">' + optHtml + '</div>',
        '</div>',

        show ? [
          '<div class="card pad" style="margin-bottom:12px;border-left:4px solid ' +
               (a.ok ? '#16a34a' : '#dc2626') + '">',
          '  <div style="margin-bottom:8px"><b>' + (a.ok ? '✅ 回答正确' : '❌ 回答错误') +
               '</b> <span class="tiny">正确答案：' + esc(q.answer || '?') + '</span></div>',
          '  <div style="font-size:14px;line-height:1.9;white-space:pre-wrap">' +
               esc(q.explain || '（无解析）') + '</div>',
          (q.flags && q.flags.length)
            ? '  <div class="tiny" style="margin-top:10px;color:#b45309">⚠ ' +
              q.flags.map(esc).join('、') + ' · OCR 置信度 ' + q.ocrScore + '，如有疑义请对照原书第 ' +
              (q.page || '?') + ' 页</div>'
            : '',
          '</div>'
        ].join('') : '',

        '<div class="row" style="gap:8px;margin-bottom:20px">',
        '  <button class="btn" id="prevQ"' + (idx === 0 ? ' disabled' : '') + '>← 上一题</button>',
        show ? '<button class="btn" id="retryQ">重做</button>'
             : '<button class="btn primary" id="checkQ">对答案</button>',
        '  <span style="flex:1"></span>',
        '  <button class="btn" id="nextQ"' + (idx === pool.length - 1 ? ' disabled' : '') + '>下一题 →</button>',
        '</div>'
      ].join('');

      // 交互（表格布局下选择器是 .opt-cell）
      $$('.opt-cell', v).forEach(function (b) {
        b.onclick = function () {
          var a0 = answers[q.id];
          if (a0 && a0.revealed) return;   // 已判答案后不可改
          var key = b.dataset.k;
          var cur = (a0 && a0.sel) ? a0.sel.slice() : [];
          // 多选/不定项都允许选多个；单选点一个即判
          var multi = q.qtype === '多选' || q.qtype === '不定项' ||
                      (q.answer || '').length > 1;
          if (multi) {
            var i = cur.indexOf(key);
            if (i >= 0) cur.splice(i, 1); else cur.push(key);
            answers[q.id] = { sel: cur.slice(), ok: false, revealed: false };
          } else {
            cur = [key];
            answers[q.id] = { sel: cur.slice(), ok: false, revealed: false };
            judge(q);   // 单选选中即判
          }
          render();
        };
      });

      var cq = $('#checkQ', v);
      if (cq) cq.onclick = function () { judge(q); render(); };
      var rq = $('#retryQ', v);
      if (rq) rq.onclick = function () { delete answers[q.id]; render(); };

      $('#prevQ', v).onclick = function () { if (idx > 0) { idx--; render(); } };
      var nx = $('#nextQ', v);
      if (nx) nx.onclick = function () {
        if (idx < pool.length - 1) { idx++; render(); }
        else finish();
      };
      $('#quit', v).onclick = function () { if (confirm('退出练习？进度将丢失')) LAW.view(); };

      // 原书页面对照（异步探测图片是否存在）
      if (imgUrl) {
        var box = $('#pageImgBox', v);
        var img = $('#pageImg', v);
        var slot = $('#imgSlot', v);
        var available = false;

        function showImg() {
          if (!available || !box) return;
          box.style.display = 'block';
          if (img) {
            if (!img.src) img.src = img.getAttribute('data-src');
            img.style.width = '100%';
          }
        }

        var realUrl = '';
        // 先探测 webp，失败再试 jpg
        var probe = new Image();
        probe.onload = function () {
          available = true;
          realUrl = probe.src;
          if (img) img.setAttribute('data-src', realUrl);
          if (slot) {
            slot.innerHTML = '<button class="btn sm" id="btnPageImg" ' +
              'style="font-size:11px;padding:2px 8px">📖 原书第 ' + (q.page || '?') + ' 页</button>';
            var b = $('#btnPageImg', v);
            if (b) b.onclick = function () {
              if (box && box.style.display === 'block') { box.style.display = 'none'; }
              else { showImg(); if (box) box.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
            };
          }
        };
        probe.onerror = function () {
          // webp 不存在，试 jpg
          if (probe.src.indexOf('.webp') >= 0 && imgUrlAlt) {
            probe.src = imgUrlAlt;
          } else {
            available = false;
          }
        };
        probe.src = imgUrl;

        var lnk = $('[data-open-page]', v);
        if (lnk) lnk.onclick = function () {
          if (!available) {
            lnk.textContent = '（原书第 ' + (q.page || '?') + ' 页图片未生成）';
            return;
          }
          showImg();
          if (box) box.scrollIntoView({ block: 'center', behavior: 'smooth' });
        };
        var bHide = $('#btnHideImg', v);
        if (bHide) bHide.onclick = function () { if (box) box.style.display = 'none'; };
        var bZoom = $('#btnZoomImg', v);
        if (bZoom) bZoom.onclick = function () { if (img && img.src) openImageFull(img.src); };
        if (img) img.onclick = function () { if (img.src) openImageFull(img.src); };
        if (img) img.onerror = function () {
          if (box) box.style.display = 'none';
          available = false;
        };
      }
    }

    /** 全屏查看图片 */
    function openImageFull(src) {
      var ov = document.createElement('div');
      ov.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.92);' +
        'display:flex;align-items:center;justify-content:center;padding:16px;cursor:zoom-out';
      ov.innerHTML = '<img src="' + src + '" style="max-width:100%;max-height:100%;' +
        'object-fit:contain;border-radius:4px">';
      ov.onclick = function () { ov.remove(); };
      document.body.appendChild(ov);
      document.addEventListener('keydown', function onEsc(e) {
        if (e.key === 'Escape') { ov.remove(); document.removeEventListener('keydown', onEsc); }
      });
    }

    function judge(q) {
      var a = answers[q.id];
      if (!a) return;
      var sel = a.sel.slice().sort().join('');
      var ans = (q.answer || '').split('').sort().join('');
      a.ok = sel === ans;
      a.revealed = true;          // 判过之后才揭晓对错与解析
      addStat(q.id, a.ok);
      if (a.ok) removeWrong(q.id); else addWrong(q.id);
    }

    function finish() {
      var ids = Object.keys(answers);
      var ok = ids.filter(function (k) { return answers[k].ok; }).length;
      var vw = document.getElementById('view');
      vw.innerHTML = [
        '<div class="card pad" style="text-align:center;padding:40px 20px">',
        '  <div style="font-size:40px;margin-bottom:10px">' + (ok / Math.max(ids.length, 1) >= 0.8 ? '🎉' : '💪') + '</div>',
        '  <h2 style="margin:0 0 8px 0">完成练习</h2>',
        '  <p class="sub">' + esc(title) + '</p>',
        '  <div style="display:flex;gap:30px;justify-content:center;margin:24px 0">',
        '    <div><div class="tiny">已答</div><div style="font-size:26px;font-weight:700">' + ids.length + '</div></div>',
        '    <div><div class="tiny">正确</div><div style="font-size:26px;font-weight:700;color:#16a34a">' + ok + '</div></div>',
        '    <div><div class="tiny">正确率</div><div style="font-size:26px;font-weight:700">' +
             (ids.length ? Math.round(ok / ids.length * 100) + '%' : '—') + '</div></div>',
        '  </div>',
        '  <div class="row" style="gap:10px;justify-content:center">',
        '    <button class="btn primary" id="backHome">返回首页</button>',
        '  </div>',
        '</div>'
      ].join('');
      $('#backHome', vw).onclick = function () { LAW.view(); };
    }

    render();
  };

})();

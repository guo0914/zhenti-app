/* =========================================================
   分类真题刷题（zhenti 模式）
   依赖：window.__ZHENTI__（题库）、window.ZLFX_API（后端）
   ========================================================= */
(function () {
  'use strict';

  const CAT_ORDER = ['politics', 'common', 'verbal', 'quantity', 'graph', 'judge', 'data'];
  const CAT_ICON = {
    politics: '★', common: '◈', verbal: '文', quantity: '∑',
    graph: '◫', judge: '⊹', data: '▤',
  };
  const PRESETS = [5, 10, 15, 20, 30, 50];
  const TIME_PRESETS = [0, 300, 600, 900, 1200, 1800];

  const Z = window.__ZHENTI__ || { categories: [], questions: [], meta: {} };
  const shardCache = new Map();      // cat -> 题目数组（按需加载）

  /** 按需加载某分类的题目分片 */
  async function loadShard(cat) {
    if (shardCache.has(cat)) return shardCache.get(cat);
    // 若已内联全部题目（老数据），直接用
    if ((Z.questions || []).length) {
      const filtered = Z.questions.filter(q => q.cat === cat);
      shardCache.set(cat, filtered);
      return filtered;
    }
    // 版本号取自页面版本，绝不写死。
    // 曾经写成 ?v=17 并配 cache:'force-cache'，导致数据文件更新后
    // URL 永不变 → 浏览器（或包内 WebView）永远返回旧 JSON，
    // 表现为「材料张冠李戴」「手机上改了数据看不到」。
    const ver = window.__APP_VER__ || Date.now();
    const res = await fetch(`data/zt/${cat}.json?v=${encodeURIComponent(ver)}`,
      { cache: 'no-store' });
    if (!res.ok) throw new Error('题目加载失败');
    const data = await res.json();
    const arr = data && data.questions ? data.questions : (Array.isArray(data) ? data : []);
    shardCache.set(cat, arr);
    return arr;
  }

  /** 同步取已缓存的题目（未加载返回空） */
  function shardOf(cat) {
    return shardCache.get(cat) || [];
  }

  /** 建立 qid -> 题目的全量映射（加载所有分片，供错题本/收藏使用） */
  let allIndexPromise = null;
  function ensureIndex() {
    if (allIndexPromise) return allIndexPromise;
    allIndexPromise = (async () => {
      const map = new Map();
      const cats = (Z.categories || []).filter(c => c.count > 0);
      await Promise.all(cats.map(async c => {
        try {
          const arr = await loadShard(c.key);
          arr.forEach(q => map.set(String(q.id), q));
        } catch (e) { /* ignore */ }
      }));
      return map;
    })();
    return allIndexPromise;
  }

  let pool = [];            // 本次抽到的题
  let idx = 0;
  let answers = {};         // qid -> {sel, ok, secs}
  let selected = { cat: 'politics', n: 10, limit: 0, mode: 'random', avoid: '' };
  let startedAt = 0;        // 本节开始的时间戳
  let pausedAt = 0;         // 暂停开始的时刻（0 表示正在计时）
  let pausedTotal = 0;      // 累计暂停毫秒
  let tick = 0;
  let drillId = 0;
  let showExplain = {};
  let paused = false;

  /* ---------- 草稿本 ---------- */
  const LS_SCRATCH = 'zlfx.scratchpad.v1';
  const LS_SCRATCH_IMG = 'zlfx.scratchpad.img.v1';
  let scratchText = '';
  let scratchImgData = '';     // canvas toDataURL
  let scratchTab = 'text';     // 'text' | 'draw'
  let brushColor = '#333';
  let brushSize = 2;

  function loadScratch() {
    try { scratchText = localStorage.getItem(LS_SCRATCH) || ''; } catch (e) { scratchText = ''; }
    try { scratchImgData = localStorage.getItem(LS_SCRATCH_IMG) || ''; } catch (e) { scratchImgData = ''; }
  }
  function saveScratch(text) {
    scratchText = text;
    try { localStorage.setItem(LS_SCRATCH, text); } catch (e) { /* quota exceeded */ }
  }
  function saveScratchImg(dataUrl) {
    scratchImgData = dataUrl;
    try { localStorage.setItem(LS_SCRATCH_IMG, dataUrl); } catch (e) { /* quota exceeded */ }
  }


  /* ---------- 通用请求（后端需要） ---------- */
  async function callApi(path, opts) {
    const api = window.ZLFX_API;
    if (api && typeof api.request === "function") return api.request(path, opts);
    const headers = { "Content-Type": "application/json" };
    if (api && api.token) headers.Authorization = "Bearer " + api.token;
    const res = await fetch(path, Object.assign({ headers }, opts || {}));
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }
    if (!res.ok) throw new Error((data && data.error) || ("HTTP " + res.status));
    return data;
  }

  /* ---------- 工具 ---------- */
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /** 解析文本：转义后把 ![公式](path) 变成真实图片 */
  function renderExplain(text) {
    const safe = esc(text || '');
    return safe.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,
      (m, alt, src) => `<img class="formula" src="${esc(src)}" alt="${esc(alt)}" data-ztimg>`);
  }

  function fmt(sec) {
    const s = Math.max(0, Math.floor(sec || 0));
    const m = Math.floor(s / 60);
    const ss = s % 60;
    if (m >= 60) {
      const h = Math.floor(m / 60);
      return `${h}:${String(m % 60).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
    }
    return `${m}:${String(ss).padStart(2, '0')}`;
  }

  function toast(msg) {
    const el = $('#toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toast.__t);
    toast.__t = setTimeout(() => el.classList.remove('show'), 2200);
  }

  function catCount(key) {
    const c = (Z.categories || []).find(x => x.key === key);
    return c ? c.count : 0;
  }

  function catName(key) {
    const c = (Z.categories || []).find(x => x.key === key);
    return c ? c.name : key;
  }

  /* ---------- 分类选择页 ---------- */
  function viewCats() {
    const allCats = (Z.categories || []);
    const cats = allCats.filter(c => c.count > 0)
      .sort((a, b) => CAT_ORDER.indexOf(a.key) - CAT_ORDER.indexOf(b.key));
    const emptyCats = allCats.filter(c => !c.count)
      .sort((a, b) => CAT_ORDER.indexOf(a.key) - CAT_ORDER.indexOf(b.key));

    if (!cats.length) {
      $('#view').innerHTML = `<div class="empty"><div class="big">∅</div>
        <p>真题库还没导入。运行 <code>python fetch_zhenti.py</code> 抓取，再 <code>python parse_zhenti.py</code> 生成。</p>
      </div>`;
      return;
    }

    const total = cats.reduce((a, c) => a + c.count, 0);
    const mk = (c, dim) => `
      <button class="cat-card ${selected.cat === c.key ? 'on' : ''}${dim ? ' dim' : ''}"
              data-cat="${c.key}"${dim ? ' disabled' : ''}>
        <span class="cat-ico">${CAT_ICON[c.key] || '·'}</span>
        <span class="cat-name">${esc(c.name)}</span>
        <span class="cat-n">${dim ? '待导入' : c.count + ' 题'}</span>
        <span class="cat-meta">${dim ? '抓取中' : c.papers + ' 卷' + (c.years ? ' · ' + Object.keys(c.years).sort().join('/') : '')}</span>
      </button>`;
    const cards = cats.map(c => mk(c, false)).join('') + emptyCats.map(c => mk(c, true)).join('');

    const nChips = PRESETS.map(n =>
      `<button class="chip ${selected.n === n ? 'on' : ''}" data-n="${n}">${n} 题</button>`).join('');
    const tChips = TIME_PRESETS.map(t =>
      `<button class="chip ${selected.limit === t ? 'on' : ''}" data-limit="${t}">${t ? (t / 60) + ' 分钟' : '不限时'}</button>`).join('');

    const cur = catCount(selected.cat);
    const maxN = Math.min(100, cur || 10);

    $('#view').innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div>
          <h1>分类刷题</h1>
          <p class="sub">${cats.length} 大模块 · ${(Z.meta && Z.meta.papers) || 0} 套真题 · 共 ${total} 题（2023–2026 国考 + 省考）</p>
        </div>
      </div>

      <div class="cat-grid">${cards}</div>

      <div class="card pad" style="margin-top:16px">
        <div class="spread" style="margin-bottom:6px">
          <h2 style="margin:0">练习设置</h2>
          <span class="pill brand" id="curCat">${esc(catName(selected.cat))} · ${cur} 题可选</span>
        </div>
        <div class="hr"></div>

        <h3>每组题数</h3>
        <div class="chips" id="nChips">${nChips}</div>
        <div class="row" style="margin-top:8px">
          <span class="tiny">自定义</span>
          <input id="customN" type="number" min="1" max="${maxN}" value="${selected.n}"
                 class="btn sm" style="width:88px;text-align:center">
          <span class="tiny">题（1–${maxN}）</span>
        </div>

        <div class="hr"></div>
        <h3>限时</h3>
        <div class="chips" id="tChips">${tChips}</div>

        <div class="hr"></div>
        <h3>出题方式</h3>
        <div class="chips" id="mChips">
          <button class="chip ${selected.mode === 'random' ? 'on' : ''}" data-mode="random">随机抽题</button>
          <button class="chip ${selected.mode === 'seq' ? 'on' : ''}" data-mode="seq">按顺序</button>
        </div>
        <label class="row" style="margin-top:10px;cursor:pointer">
          <input type="checkbox" id="avoidDone" ${selected.avoid === 'done' ? 'checked' : ''}>
          <span class="tiny">优先抽没做过的题</span>
        </label>

        <div class="row" style="margin-top:16px">
          <button class="btn primary" id="startBtn" style="min-width:150px">开始练习</button>
          <button class="btn" id="wrongBtn">练错题</button>
        </div>
      </div>
    `;

    $$('.cat-card').forEach(b => b.onclick = () => {
      selected.cat = b.dataset.cat;
      viewCats();
    });
    $$('#nChips .chip').forEach(b => b.onclick = () => {
      selected.n = Number(b.dataset.n);
      viewCats();
    });
    $$('#tChips .chip').forEach(b => b.onclick = () => {
      selected.limit = Number(b.dataset.limit);
      viewCats();
    });
    $$('#mChips .chip').forEach(b => b.onclick = () => {
      selected.mode = b.dataset.mode;
      viewCats();
    });
    const cn = $('#customN');
    if (cn) cn.onchange = () => {
      let v = parseInt(cn.value, 10) || 1;
      v = Math.max(1, Math.min(maxN, v));
      selected.n = v;
      viewCats();
    };
    const ad = $('#avoidDone');
    if (ad) ad.onchange = () => { selected.avoid = ad.checked ? 'done' : ''; };

    $('#startBtn').onclick = () => startDrill();
    $('#wrongBtn').onclick = () => {
      location.hash = '#/wrong';
    };

    document.body.dataset.zmode = 'cats';
  }

  /* ---------- 开始练习 ---------- */
  async function startDrill() {
    const cat = selected.cat;
    const n = Math.max(1, Math.min(100, selected.n | 0));
    const api = window.ZLFX_API;

    // 本地分片优先（无后端或未登录时也能刷）
    let local = [];
    try {
      local = await loadShard(cat);
    } catch (e) {
      toast('题目加载失败，请检查网络或运行 parse_zhenti.py');
      return;
    }
    if (!local.length) { toast('该分类暂无题目'); return; }

    let picked = null;
    if (api && api.token) {
      try {
        const qs = [
          `cat=${encodeURIComponent(cat)}`,
          `n=${n}`,
          `mode=${selected.mode}`,
          selected.avoid ? `avoid=${selected.avoid}` : '',
        ].filter(Boolean).join('&');
        const res = await callApi(`/api/zhenti?${qs}`);
        if (res && res.questions && res.questions.length) {
          picked = res.questions;
          drillId = res.drill || 0;
        }
      } catch (e) {
        /* 降级到本地 */
      }
    }

    if (!picked) {
      const arr = local.slice();
      if (selected.mode === 'random') {
        for (let i = arr.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [arr[i], arr[j]] = [arr[j], arr[i]];
        }
      }
      picked = arr.slice(0, Math.min(n, arr.length));
      drillId = 0;
    }

    pool = picked;
    idx = 0;
    answers = {};
    showExplain = {};
    paused = false;
    pausedAt = 0;
    pausedTotal = 0;
    startedAt = Date.now();
    loadScratch();  // 恢复上次的草稿
    startTick();
    goDrill();
  }

  /** 进入答题页；hash 相同时也要强制重绘 */
  function goDrill() {
    if (location.hash === '#/drillrun') {
      viewDrill();
    } else {
      location.hash = '#/drillrun';
    }
  }

  function startTick() {
    if (tick) clearInterval(tick);
    tick = setInterval(() => {
      if (!startedAt) return;
      const el = $('#drillClock');
      if (!el) return;
      const used = currentElapsed();
      if (selected.limit > 0) {
        const left = Math.max(0, selected.limit - used);
        el.textContent = fmt(left);
        el.classList.toggle('low', left <= 60 && left > 0);
        if (left === 0 && !paused) finish(true);
      } else {
        el.textContent = fmt(used);
        el.classList.remove('low');
      }
    }, 1000);
  }

  /** 已用秒数（不含暂停期间） */
  function currentElapsed() {
    if (!startedAt) return 0;
    const end = paused && pausedAt ? pausedAt : Date.now();
    return Math.max(0, Math.floor((end - startedAt - pausedTotal) / 1000));
  }

  function stopTick() {
    if (tick) { clearInterval(tick); tick = 0; }
  }

  /* ---------- 刷题页 ---------- */
  function viewDrill() {
    if (!pool.length) {
      $('#view').innerHTML = `<div class="empty"><div class="big">∅</div><p>还没有开始练习</p>
        <button class="btn primary" onclick="location.hash='#/cats'">去选题</button></div>`;
      return;
    }
    if (idx < 0) idx = 0;
    if (idx >= pool.length) idx = pool.length - 1;
    const q = pool[idx];
    const a = answers[q.id];
    const show = !!a;
    const done = Object.keys(answers).length;
    const correct = Object.values(answers).filter(x => x.ok).length;

    // 选项渲染：用 <table> 布局
    //   原因：实测用户浏览器（Edge + 150% 缩放）中 flex 布局会算出错误的宽度，
    //   导致选项溢出卡片或被压成窄条。表格布局宽度计算简单稳定，任何环境都正常。
    const optHtml = (q.options || []).length ? `
      <table class="opt-table" style="width:100%;max-width:100%;border-collapse:separate;border-spacing:0 9px;table-layout:fixed;box-sizing:border-box;margin:0;padding:0;">
        ${(q.options || []).map((text, i) => {
          const key = (q.optionKeys && q.optionKeys[i]) || 'ABCD'[i];
          // 选项本身是图片时（公式/图形/图表型选项），优先渲染图片
          const optImg = (q.optionImgs || [])[i] || '';
          // 内联 HTML（文字+原位图片）优先，保住文字与图片位置
          const optHtmlCell = String((q.optionHtml || [])[i] || '').trim();
          const picked = a && a.sel === key;
          const isAns = q.answer === key;
          let bg = '#fff', bd = '#c5cddd', lbg = '#d8dfec', lfg = '#46506a';
          if (show) {
            if (isAns) { bg = '#e7f8f0'; bd = '#37c98b'; lbg = '#37c98b'; lfg = '#fff'; }
            else if (picked) { bg = '#fdecef'; bd = '#e0405a'; lbg = '#e0405a'; lfg = '#fff'; }
          } else if (picked) { bg = '#eef0ff'; bd = '#4f46e5'; lbg = '#4f46e5'; lfg = '#fff'; }
          return `<tr>
            <td style="width:24px;padding:0;vertical-align:top;">
              <span style="display:block;width:24px;height:24px;line-height:24px;text-align:center;
                     border-radius:7px;background:${lbg};color:${lfg};font-size:12.5px;
                     font-weight:700;margin-top:11px;box-sizing:border-box;">${key}</span>
            </td>
            <td class="opt-cell" data-k="${key}" style="vertical-align:top;background:${bg};
                   border:1.5px solid ${bd};border-radius:11px;padding:10px 13px;
                   font-size:14.5px;line-height:1.7;color:#1c2333;
                   overflow-wrap:anywhere;word-break:break-word;
                   cursor:pointer;">${optHtmlCell || (optImg
              ? `<img src="${esc(optImg)}" alt="选项${key}" loading="lazy"
                     onerror="this.style.display='none'"
                     style="${String(optImg).indexOf('公式图') >= 0
                       ? 'max-width:100%;height:auto;display:inline-block;vertical-align:middle'
                       : 'max-width:100%;height:auto;display:block;border-radius:6px'}">`
              : esc(text || '（源数据无此选项内容）'))}${
              show && isAns ? '<span style="float:right;font-size:11px;color:#16a34a;margin-left:8px;">✓</span>' : ''
            }</td>
          </tr>`;
        }).join('')}
      </table>` : '';

    const explainHtml = show && q.explain ? `
      <div class="explain ${showExplain[q.id] ? '' : 'collapsed'}">
        <div class="explain-h" id="explainToggle">
          <b>解析</b><span>${esc(q.sub || '')}</span>
          <span style="margin-left:auto" class="tiny">${showExplain[q.id] ? '收起' : '展开'}</span>
        </div>
        <div class="explain-b">${renderExplain(q.explain)}</div>
      </div>` : '';

    const stemHtmlInline = String(q.stemHtml || '').trim();
    const imgsHtml = (!stemHtmlInline && (q.imgs || []).length)
      ? `<div class="q-img-wrap">${q.imgs.map(s => `<img src="${esc(s)}" alt="题目图" data-ztimg>`).join('')}</div>`
      : '';

    // 资料分析：题目自带材料（文字 + 图表），需要一起展示
    let matHtml = '';
    if (q.material || (q.materialImgs || []).length) {
      const mImgs = (q.materialImgs || []).map(s => `<img src="${esc(s)}" alt="材料图表" data-ztimg>`).join('');
      const hasImg = (q.materialImgs || []).length > 0;
      // 有图表时文字默认折叠（图更重要）；纯文字材料默认展开
      const txtHidden = hasImg ? 'hidden' : '';
      matHtml = `<div class="material">
        <div class="material-h">
          <b>材料${q.matNo ? ' ' + q.matNo : ''}</b>
          <span class="mat-title">${esc(q.sub || '')}</span>
          ${q.material ? `<button class="btn sm" id="btnMatTxt2" style="margin-left:auto">${hasImg ? '展开文字' : '收起文字'}</button>` : ''}
        </div>
        <div class="material-b">
          ${mImgs}
          ${q.material ? `<div class="material-txt ${txtHidden}" id="matTxt2">${esc(q.material)}</div>` : ''}
        </div>
      </div>`;
    }

    const sheet = pool.map((item, i) => {
      const aa = answers[item.id];
      let cls = aa ? (aa.ok ? 'ok' : 'bad') : '';
      if (i === idx) cls += ' cur';
      return `<button class="${cls}" data-jump="${i}">${i + 1}</button>`;
    }).join('');

    const limit = selected.limit;
    const left = limit > 0 ? Math.max(0, limit - currentElapsed()) : 0;

    $('#view').innerHTML = `
      <div class="practice">
        <div class="q-card">
          <div class="q-head">
            <span class="pill brand">${esc(catName(selected.cat))}</span>
            <span class="qid">${idx + 1} / ${pool.length}</span>
            <span class="pill">${q.year || ''} ${esc(q.region || '')}</span>
            ${q.tf ? '<span class="pill warn">判断题</span>' : ''}
            <span style="margin-left:auto"></span>
            <button class="btn sm" id="btnFav2">☆ 收藏</button>
          </div>
          <div class="q-body">
            ${matHtml}
            ${imgsHtml}
            <div class="stem">${stemHtmlInline || esc(q.stem)}</div>
            <div class="options">${optHtml}</div>
            ${explainHtml}
          </div>
          <div class="q-foot">
            <button class="btn" id="prevQ" ${idx === 0 ? 'disabled' : ''}>← 上一题</button>
            ${show ? '<button class="btn" id="retryQ">重做</button>' : '<button class="btn primary" id="checkQ">对答案</button>'}
            <span class="grow"></span>
            <button class="btn" id="nextQ" ${idx === pool.length - 1 ? 'disabled' : ''}>下一题 →</button>
          </div>
        </div>
        <aside class="side-panel">
          <div class="panel timer-panel">
            <div class="spread">
              <h3 style="margin:0">${limit > 0 ? '倒计时' : '用时'}</h3>
              <span class="tiny" id="drillState">${paused ? '已暂停' : '计时中'}</span>
            </div>
            <div class="clock" id="drillClock">${fmt(limit > 0 ? left : currentElapsed())}</div>
            <div class="clock-sub">${limit > 0 ? '限时 ' + fmt(limit) : '不限时'}</div>
            <div class="row" style="margin-top:10px;gap:6px">
              <button class="btn sm" id="pauseBtn">${paused ? '继续' : '暂停'}</button>
              <button class="btn sm" id="resetBtn" title="计时清零">清零</button>
              <button class="btn sm primary" id="finishBtn">交卷</button>
            </div>
          </div>
          <div class="panel">
            <div class="spread" style="margin-bottom:8px">
              <h3 style="margin:0">答题卡</h3>
              <span class="tiny">${done}/${pool.length} · 对 ${correct}</span>
            </div>
            <div class="sheet-grid">${sheet}</div>
            <div class="legend">
              <span><i style="background:var(--ok-soft);border:1px solid var(--ok)"></i>正确</span>
              <span><i style="background:var(--bad-soft);border:1px solid var(--bad)"></i>错误</span>
              <span><i style="background:var(--brand)"></i>当前</span>
            </div>
          </div>
          <div class="panel scratchpad-panel">
            <div class="spread" style="margin-bottom:4px">
              <h3 style="margin:0">草稿本</h3>
              <div class="row" style="gap:4px">
                <button class="btn sm scratch-tab active" data-scratchtab="text">文字</button>
                <button class="btn sm scratch-tab" data-scratchtab="draw">画笔</button>
                <button class="btn sm" id="scratchFull" title="全屏草稿">⛶</button>
                <button class="btn sm" id="clearScratch" title="清空草稿">清空</button>
              </div>
            </div>
            <div id="scratchTextWrap">
              <textarea id="scratchArea" placeholder="在此打草稿…" style="width:100%;height:200px;resize:vertical;box-sizing:border-box;font-size:13px;line-height:1.5;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg-1);color:var(--text-1);font-family:inherit"></textarea>
            </div>
            <div id="scratchDrawWrap" style="display:none">
              <canvas id="scratchCanvas" width="280" height="200" style="width:100%;border:1px solid var(--line);border-radius:6px;cursor:crosshair;background:#fff;touch-action:none;box-sizing:border-box"></canvas>
              <div class="row" style="margin-top:6px;gap:6px;flex-wrap:wrap">
                <input type="color" id="brushColor" value="#333333" title="颜色" style="width:28px;height:28px;border:none;padding:0;border-radius:4px;cursor:pointer">
                <input type="range" id="brushSize" min="1" max="10" value="2" title="笔刷大小" style="width:80px">
                <button class="btn sm" id="undoStroke" title="撤销">↩</button>
                <button class="btn sm" id="clearDraw" title="清空画布">清空画布</button>
              </div>
            </div>
          </div>
          <div class="panel">
            <h3>本组进度</h3>
            <div class="bar ${done && correct / done >= 0.8 ? 'ok' : ''}">
              <i style="width:${Math.round(done / pool.length * 100)}%"></i>
            </div>
            <div class="tiny" style="margin-top:8px">${esc(q.paper || '')}</div>
          </div>
        </aside>
        <!-- 草稿本全屏浮层 -->
        <div id="scratchFullOverlay" class="scratch-full-overlay" style="display:none">
          <div class="scratch-full-bar">
            <span>草稿本 · 全屏</span>
            <button class="btn sm" id="scratchFullHide">退出全屏</button>
          </div>
          <div id="scratchFullBody" style="flex:1;display:flex;align-items:flex-start;justify-content:center;overflow:auto"></div>
        </div>
      </div>
    `;

    // 选项点击：表格布局下选择器是 .opt-cell（td）
    $$('.opt-cell').forEach(cell => cell.onclick = () => {
      if (show) return;                       // 已判分不再响应
      pick(q, cell.dataset.k);
    });
    $$('.sheet-grid button').forEach(b => b.onclick = () => {
      idx = Number(b.dataset.jump);
      viewDrill();
    });
    const pq = $('#prevQ'); if (pq) pq.onclick = () => { idx--; viewDrill(); };
    const nq = $('#nextQ'); if (nq) nq.onclick = () => { idx++; viewDrill(); };
    const cq = $('#checkQ'); if (cq) cq.onclick = () => { showExplain[q.id] = true; viewDrill(); };
    const rq = $('#retryQ'); if (rq) rq.onclick = () => { delete answers[q.id]; viewDrill(); };
    const et = $('#explainToggle');
    if (et) et.onclick = () => { showExplain[q.id] = !showExplain[q.id]; viewDrill(); };
    const bmt2 = $('#btnMatTxt2');
    if (bmt2) bmt2.onclick = () => {
      const t = $('#matTxt2');
      if (!t) return;
      const hidden = t.classList.toggle('hidden');
      bmt2.textContent = hidden ? '展开文字' : '收起文字';
    };

    // ---- 草稿本 (文字 + 画笔) ----
    // --- 文字模式 ---
    const sa = $('#scratchArea');
    if (sa) {
      sa.value = scratchText;
      let scratchTimer = 0;
      sa.addEventListener('input', () => {
        clearTimeout(scratchTimer);
        scratchTimer = setTimeout(() => saveScratch(sa.value), 300);
      });
    }

    // --- 画笔模式 ---
    const cv = $('#scratchCanvas');
    let drawCtx = null;
    let drawing = false;
    let strokes = [];       // 每笔 = ImageData 快照（撤销用）

    function initDrawCtx() {
      if (!cv) return;
      // 调整 canvas 实际分辨率匹配 CSS 宽度
      const rect = cv.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const w = rect.width;
      const h = Math.max(200, w * 0.7);
      if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
        cv.width = Math.round(w * dpr);
        cv.height = Math.round(h * dpr);
      }
      drawCtx = cv.getContext('2d');
      drawCtx.scale(dpr, dpr);
      drawCtx.lineCap = 'round';
      drawCtx.lineJoin = 'round';
      drawCtx.strokeStyle = brushColor;
      drawCtx.lineWidth = brushSize;
      // 恢复上次的图片
      if (scratchImgData) {
        const img = new Image();
        img.onload = () => {
          drawCtx.clearRect(0, 0, w, h);
          drawCtx.drawImage(img, 0, 0, w, h);
        };
        img.src = scratchImgData;
      } else {
        drawCtx.fillStyle = '#fff';
        drawCtx.fillRect(0, 0, w, h);
      }
    }

    function snapshotCanvas() {
      if (!cv || !drawCtx) return;
      strokes.push(drawCtx.getImageData(0, 0, cv.width, cv.height));
      // 限制撤销步数
      if (strokes.length > 30) strokes.shift();
    }

    function saveDrawState() {
      if (!cv) return;
      const dataUrl = cv.toDataURL('image/png');
      saveScratchImg(dataUrl);
    }

    if (cv) {
      initDrawCtx();

      cv.addEventListener('pointerdown', (e) => {
        drawing = true;
        snapshotCanvas();
        const rect = cv.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        drawCtx.beginPath();
        drawCtx.moveTo(x, y);
        cv.setPointerCapture(e.pointerId);
      });

      cv.addEventListener('pointermove', (e) => {
        if (!drawing) return;
        const rect = cv.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        drawCtx.lineTo(x, y);
        drawCtx.stroke();
      });

      cv.addEventListener('pointerup', () => {
        if (!drawing) return;
        drawing = false;
        drawCtx.closePath();
        saveDrawState();
      });

      cv.addEventListener('pointerleave', () => {
        if (drawing) {
          drawing = false;
          drawCtx.closePath();
          saveDrawState();
        }
      });

      // 颜色
      const bc = $('#brushColor');
      if (bc) bc.oninput = () => {
        brushColor = bc.value;
        drawCtx.strokeStyle = brushColor;
      };

      // 笔刷大小
      const bs = $('#brushSize');
      if (bs) bs.oninput = () => {
        brushSize = Number(bs.value);
        drawCtx.lineWidth = brushSize;
      };

      // 撤销
      const ub = $('#undoStroke');
      if (ub) ub.onclick = () => {
        if (strokes.length === 0) return;
        const prev = strokes.pop();
        drawCtx.putImageData(prev, 0, 0);
        saveDrawState();
      };

      // 清空画布
      const cd = $('#clearDraw');
      if (cd) cd.onclick = () => {
        strokes = [];
        const w = cv.getBoundingClientRect().width;
        const h = cv.getBoundingClientRect().height;
        drawCtx.fillStyle = '#fff';
        drawCtx.fillRect(0, 0, w, h);
        saveScratchImg('');
        scratchImgData = '';
      };
    }

    // --- 切换标签 ---
    $$('.scratch-tab').forEach(btn => {
      btn.onclick = () => {
        scratchTab = btn.dataset.scratchtab;
        $$('.scratch-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const textW = $('#scratchTextWrap');
        const drawW = $('#scratchDrawWrap');
        if (scratchTab === 'text') {
          if (textW) textW.style.display = '';
          if (drawW) drawW.style.display = 'none';
        } else {
          if (textW) textW.style.display = 'none';
          if (drawW) drawW.style.display = '';
          // 重新初始化 canvas（可能 resize 后需要）
          setTimeout(initDrawCtx, 50);
        }
      };
    });

    // 初始标签状态
    if (scratchTab === 'draw') {
      const drawBtn = document.querySelector('.scratch-tab[data-scratchtab="draw"]');
      if (drawBtn) drawBtn.click();
    }

    // --- 清空 ---
    const cs = $('#clearScratch');
    if (cs) cs.onclick = () => {
      if (scratchTab === 'text') {
        const sa2 = $('#scratchArea');
        if (sa2) { sa2.value = ''; saveScratch(''); }
      } else {
        strokes = [];
        if (cv && drawCtx) {
          const w = cv.getBoundingClientRect().width;
          const h = cv.getBoundingClientRect().height;
          drawCtx.fillStyle = '#fff';
          drawCtx.fillRect(0, 0, w, h);
        }
        saveScratchImg('');
        scratchImgData = '';
      }
    };

    // --- 全屏草稿 ---
    let fullscreenMode = false;

    function enterFullscreen() {
      fullscreenMode = true;
      const overlay = $('#scratchFullOverlay');
      const body = $('#scratchFullBody');
      if (!overlay || !body) return;
      overlay.style.display = 'flex';
      // 将当前模式的内容克隆到全屏
      if (scratchTab === 'text') {
        const src = $('#scratchArea');
        body.innerHTML = `<textarea id="scratchFullArea" style="width:100%;height:100%;box-sizing:border-box;font-size:15px;line-height:1.6;padding:16px;border:1px solid var(--line);border-radius:6px;background:var(--bg-1);color:var(--text-1);font-family:inherit;resize:none">${esc(src ? src.value : '')}</textarea>`;
        const fa = $('#scratchFullArea');
        if (fa) {
          fa.addEventListener('input', () => {
            // 同步回侧边栏
            const src2 = $('#scratchArea');
            if (src2) src2.value = fa.value;
            saveScratch(fa.value);
          });
          setTimeout(() => fa.focus(), 100);
        }
      } else {
        body.innerHTML = `<canvas id="scratchFullCanvas" style="max-width:100%;max-height:100%;cursor:crosshair;background:#fff;touch-action:none;border:1px solid var(--line);border-radius:6px;box-shadow:0 2px 12px rgba(0,0,0,0.1)"></canvas>`;
        const fc = $('#scratchFullCanvas');
        if (fc) {
          const parentW = body.clientWidth;
          const parentH = body.clientHeight;
          const dpr = window.devicePixelRatio || 1;
          fc.width = Math.round(parentW * dpr);
          fc.height = Math.round(parentH * dpr);
          fc.style.width = parentW + 'px';
          fc.style.height = parentH + 'px';
          const fctx = fc.getContext('2d');
          fctx.scale(dpr, dpr);
          fctx.lineCap = 'round';
          fctx.lineJoin = 'round';
          fctx.strokeStyle = brushColor;
          fctx.lineWidth = brushSize;
          // 恢复图片
          if (scratchImgData) {
            const img = new Image();
            img.onload = () => { fctx.drawImage(img, 0, 0, parentW, parentH); };
            img.src = scratchImgData;
          } else {
            fctx.fillStyle = '#fff';
            fctx.fillRect(0, 0, parentW, parentH);
          }
          // 全屏画笔事件
          let fdrawing = false, fstrokes = [];
          fc.addEventListener('pointerdown', (e) => {
            // 每次落笔读取最新颜色/大小
            fctx.strokeStyle = brushColor;
            fctx.lineWidth = brushSize;
            fdrawing = true;
            fstrokes.push(fctx.getImageData(0, 0, fc.width, fc.height));
            if (fstrokes.length > 30) fstrokes.shift();
            const rect = fc.getBoundingClientRect();
            fctx.beginPath();
            fctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
            fc.setPointerCapture(e.pointerId);
          });
          fc.addEventListener('pointermove', (e) => {
            if (!fdrawing) return;
            const rect = fc.getBoundingClientRect();
            fctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
            fctx.stroke();
          });
          fc.addEventListener('pointerup', () => {
            if (!fdrawing) return;
            fdrawing = false;
            fctx.closePath();
            // 同步回侧边栏
            syncFullDrawToSidebar(fc);
          });
          fc.addEventListener('pointerleave', () => {
            if (fdrawing) { fdrawing = false; fctx.closePath(); syncFullDrawToSidebar(fc); }
          });
          // 颜色/大小跟随全局设置
          // （通过重新设置 fctx.strokeStyle/lineWidth，在每次 pointerdown 时读取 brushColor/brushSize）
          // 撤销
          const undoKey = (e) => {
            if (e.key === 'z' && (e.ctrlKey || e.metaKey) && fstrokes.length > 0) {
              const prev = fstrokes.pop();
              fctx.putImageData(prev, 0, 0);
              syncFullDrawToSidebar(fc);
              e.preventDefault();
            }
          };
          document.addEventListener('keydown', undoKey);
          fc._cleanupUndo = () => document.removeEventListener('keydown', undoKey);
        }
      }
    }

    function syncFullDrawToSidebar(fc) {
      const dataUrl = fc.toDataURL('image/png');
      saveScratchImg(dataUrl);
      // 同步到侧边栏 canvas
      const sc = $('#scratchCanvas');
      if (sc && drawCtx) {
        const img = new Image();
        img.onload = () => {
          const w = sc.getBoundingClientRect().width;
          const h = sc.getBoundingClientRect().height;
          drawCtx.clearRect(0, 0, w, h);
          drawCtx.drawImage(img, 0, 0, w, h);
        };
        img.src = dataUrl;
      }
    }

    function exitFullscreen() {
      fullscreenMode = false;
      const overlay = $('#scratchFullOverlay');
      if (overlay) overlay.style.display = 'none';
      const fc = $('#scratchFullCanvas');
      if (fc && fc._cleanupUndo) fc._cleanupUndo();
      // 清除全屏 body
      const body = $('#scratchFullBody');
      if (body) body.innerHTML = '';
    }

    const sf = $('#scratchFull');
    if (sf) sf.onclick = () => {
      if (fullscreenMode) { exitFullscreen(); return; }
      enterFullscreen();
    };

    const sfh = $('#scratchFullHide');
    if (sfh) sfh.onclick = exitFullscreen;

    // ESC 退出全屏
    const escKey = (e) => { if (e.key === 'Escape' && fullscreenMode) exitFullscreen(); };
    document.addEventListener('keydown', escKey);

    // 图片还没下载完时，显示占位而不是破图
    $$('img[data-ztimg]').forEach(img => {
      img.onerror = () => {
        const box = document.createElement('div');
        box.className = 'img-missing';
        box.textContent = '图片待下载（运行 fetch_images_parallel.py 补齐）';
        img.replaceWith(box);
      };
    });
    $('#pauseBtn').onclick = () => {
      paused = !paused;
      if (paused) {
        pausedAt = Date.now();
      } else {
        if (pausedAt) pausedTotal += Date.now() - pausedAt;
        pausedAt = 0;
      }
      $('#drillState').textContent = paused ? '已暂停' : '计时中';
      $('#pauseBtn').textContent = paused ? '继续' : '暂停';
      const el = $('#drillClock');
      if (el) el.textContent = fmt(selected.limit > 0
        ? Math.max(0, selected.limit - currentElapsed())
        : currentElapsed());
    };
    $('#finishBtn').onclick = () => finish(false);
    $('#resetBtn').onclick = () => {
      // 计时清零：重新从 0 开始计时
      startedAt = Date.now();
      pausedTotal = 0;
      paused = false;
      pausedAt = 0;
      $('#drillState').textContent = '计时中';
      $('#pauseBtn').textContent = '暂停';
      const el = $('#drillClock');
      if (el) el.textContent = fmt(selected.limit > 0 ? selected.limit : 0);
      if (window.ZLFX_API && typeof window.ZLFX_API.toast === 'function') {
        window.ZLFX_API.toast('计时已清零');
      }
    };
    const fv = $('#btnFav2');
    if (fv) fv.onclick = () => {
      const api = window.ZLFX_API;
      if (api && api.token) api.favorite(q.id, true, 'zhenti');
      toast('已收藏');
    };
  }

  function pick(q, key) {
    const ok = key === q.answer;
    answers[q.id] = { sel: key, ok, secs: 0 };
    showExplain[q.id] = true;
    const api = window.ZLFX_API;
    if (api && api.token) {
      api.answer({ qid: q.id, sel: key, ok, secs: 0, bank: 'zhenti' });
      if (drillId) {
        const done = Object.keys(answers).length;
        const correct = Object.values(answers).filter(x => x.ok).length;
        callApi('/api/drill', { method: 'PUT', body: JSON.stringify({ drill: drillId, done, correct, elapsed: currentElapsed() }) }).catch(() => null);
      }
    }
    viewDrill();
    if (!ok) toast('答错，已记入错题本');
  }

  function finish(auto) {
    stopTick();
    const done = Object.keys(answers).length;
    const correct = Object.values(answers).filter(x => x.ok).length;
    const el = currentElapsed();
    const api = window.ZLFX_API;
    if (api && api.token && drillId) {
      callApi('/api/drill', { method: 'PUT', body: JSON.stringify({ drill: drillId, done, correct, elapsed: el, finished: true }) }).catch(() => null);
    }
    const sheet = $('#sheet');
    $('#sheetBody').innerHTML = `
      <h2>${auto ? '时间到 · 自动交卷' : '本组完成'}</h2>
      <div class="grid g3" style="margin:14px 0">
        <div class="card stat-card"><div class="k">完成</div><div class="v">${done}/${pool.length}</div></div>
        <div class="card stat-card"><div class="k">正确率</div><div class="v">${done ? Math.round(correct / done * 100) : 0}%</div></div>
        <div class="card stat-card"><div class="k">用时</div><div class="v" style="font-size:19px">${fmt(el)}</div></div>
      </div>
      <div class="row">
        <button class="btn primary" onclick="location.hash='#/cats';document.getElementById('sheetClose').click()">再练一组</button>
        <button class="btn" onclick="document.getElementById('sheetClose').click()">留在此页</button>
      </div>
    `;
    sheet.classList.remove('hidden');
  }

  /* ---------- 从错题本/收藏进入：按 qid 列表练习 ---------- */
  async function practiceList(ids) {
    const list = (ids || []);
    const need = new Set();
    // 先按已知分类加载分片
    const want = [];
    list.forEach(id => {
      for (const c of (Z.categories || [])) {
        if (shardOf(c.key).some(q => q.id === id)) { want.push(shardOf(c.key).find(q => q.id === id)); return; }
      }
      need.add(id);
    });
    // 剩余的去各分类分片里找
    if (need.size) {
      for (const c of (Z.categories || [])) {
        if (!c.count) continue;
        try { await loadShard(c.key); } catch (e) { continue; }
        shardOf(c.key).forEach(q => { if (need.has(q.id)) want.push(q); });
        if (want.length >= list.length) break;
      }
    }
    const pool2 = want;
    if (!pool2.length) { toast('这些题目不在真题库中'); return; }
    pool = pool2;
    idx = 0;
    answers = {};
    showExplain = {};
    paused = false;
    pausedAt = 0;
    pausedTotal = 0;
    startedAt = Date.now();
    drillId = 0;
    selected.cat = pool2[0].cat;
    selected.limit = 0;
    startTick();
    goDrill();
  }

  function practiceOne(id) {
    practiceList([id]);
  }

  /* ---------- 导出 ---------- */
  window.ZLFX_ZHENTI = {
    viewCats, viewDrill, practiceList, practiceOne, ensureIndex,
    _shardOf: shardOf,  // 供 app.js _syncBank 读取已缓存分片
    reset() { pool = []; idx = 0; answers = {}; stopTick(); },
    reset() { pool = []; idx = 0; answers = {}; stopTick(); },
    state() { return { pool, idx, answers, selected, drillId }; },
    isEmpty() { return !(Z.categories || []).some(c => c.count > 0); },
    count() {
      return (Z.categories || []).reduce((a, c) => a + (c.count || 0), 0);
    },
  };
})();

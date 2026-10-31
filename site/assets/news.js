/* =========================================================
   时政资讯 · 多源聚合版
   数据: window.__NEWS__ = { updated, total, sources[], topics[], articles[] }
   功能: 分源筛选 / 话题筛选 / 关键词搜索 / 收藏 / 摘要展开
   ========================================================= */
(function () {
  'use strict';

  const NL = window.ZLFX_NEWS = {};
  const LS_FAV = 'zlfx.news.favs';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function fmtDate(d) {
    return d && d.length === 8 ? d.slice(0, 4) + '-' + d.slice(4, 6) + '-' + d.slice(6, 8) : (d || '');
  }
  function relDate(d) {
    if (!d || d.length !== 8) return '';
    const t = new Date(+d.slice(0, 4), +d.slice(4, 6) - 1, +d.slice(6, 8));
    const now = new Date();
    const days = Math.floor((now - t) / 86400000);
    if (days <= 0) return '今天';
    if (days === 1) return '昨天';
    if (days < 7) return days + '天前';
    return fmtDate(d);
  }

  function getFavs() {
    try { return JSON.parse(localStorage.getItem(LS_FAV) || '[]'); } catch (e) { return []; }
  }
  function setFavs(a) { try { localStorage.setItem(LS_FAV, JSON.stringify(a)); } catch (e) {} }
  function toggleFav(url) {
    const f = getFavs();
    const i = f.indexOf(url);
    if (i >= 0) f.splice(i, 1); else f.push(url);
    setFavs(f);
    return i < 0;
  }

  // 视图状态
  NL._state = { source: 'all', topic: 'all', fav: false, q: '', live: false, loading: false, err: '', hasNew: false };
  NL._live = null;      // 实时抓取的数据
  NL._lastLiveTs = 0;   // 上次实时抓取时间
  NL._inflight = null;  // 进行中的请求，用于并发去重

  const LIVE_TTL = 30000;      // 本地复用窗口 30 秒（后端有 60 秒缓存，故请求很便宜）
  const AUTO_REFRESH = 90000;  // 资讯页每 90 秒自动刷新
  const IDLE_REFRESH = 180000; // 非资讯页后台每 3 分钟静默检查一次
  let _timer = null;
  let _idleTimer = null;
  let _countdownTimer = null;

  /** 探测 API 是否可用 */
  function apiBase() {
    // 若通过 serve.py / server.py 打开，同源即 API
    if (location.protocol === 'http:' || location.protocol === 'https:') {
      return '';
    }
    return '';
  }

  /** 从后端实时抓取。返回 Promise，resolve 为抓取结果 */
  NL.loadLive = function (opts) {
    opts = opts || {};
    const force = !!opts.force;
    const now = Date.now();

    // 命中本地缓存
    if (!force && NL._live && now - NL._lastLiveTs < LIVE_TTL) {
      return Promise.resolve(NL._live);
    }

    // 已有请求在飞：复用同一个 Promise，避免重复抓取
    if (NL._state.loading && NL._inflight) {
      return NL._inflight;
    }

    NL._state.loading = true;
    NL._state.err = '';
    if (document.getElementById('newsStatus')) NL.paintStatus();

    const url = apiBase() + '/api/news?limit=30&timeout=40';
    NL._inflight = fetch(url, { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (j) {
        if (!j.ok) throw new Error(j.error || '抓取失败');
        NL._live = j;
        NL._lastLiveTs = Date.now();
        NL._state.loading = false;
        NL._state.live = true;
        NL._inflight = null;
        return j;
      })
      .catch(function (e) {
        NL._state.loading = false;
        NL._state.err = String(e.message || e);
        NL._inflight = null;
        throw e;
      });

    return NL._inflight;
  };

  /** 当前生效的数据（实时优先，否则静态缓存） */
  function currentData() {
    if (NL._live && NL._live.articles && NL._live.articles.length) return NL._live;
    return window.__NEWS__ || { articles: [], sources: [], topics: [] };
  }

  /** 只重绘状态条 */
  NL.paintStatus = function () {
    const el = document.getElementById('newsStatus');
    if (!el) return;
    const st = NL._state;
    if (st.loading) {
      el.innerHTML = '<span class="pill">⏳ 正在抓取最新资讯…</span>';
      return;
    }
    if (st.err) {
      el.innerHTML = '<span class="pill" style="color:var(--danger)">⚠ 实时抓取不可用（' +
        esc(st.err) + '），当前显示本地缓存</span>';
      return;
    }
    const n = NL._live;
    if (n) {
      const ago = Math.round((Date.now() - NL._lastLiveTs) / 1000);
      const agoText = ago < 10 ? '刚刚' : ago < 60 ? ago + ' 秒前' : Math.round(ago / 60) + ' 分钟前';
      let extra = '';
      if (n.changed) extra = ' <span class="pill" style="background:#fde68a;color:#000">🔔 有新内容</span>';
      el.innerHTML = '<span class="pill ok">🟢 实时 · ' + n.total + ' 篇 · ' +
        '最新 ' + esc(n.first_article || '') + ' · ' + agoText + '更新</span>' + extra;
    } else {
      el.innerHTML = '<span class="pill dim">📦 本地缓存（未连接实时服务）</span>';
    }
  };

  /** 启动自动刷新（含后台静默检查） */
  NL.startAuto = function () {
    if (_timer) clearInterval(_timer);
    if (_idleTimer) clearInterval(_idleTimer);
    if (_countdownTimer) clearInterval(_countdownTimer);

    // 资讯页：每 90 秒强制刷新
    _timer = setInterval(function () {
      if (location.hash.indexOf('/news') < 0) return;
      if (document.hidden) return;
      NL.loadLive({ force: true })
        .then(function (j) {
          if (j && j.changed) NL._state.hasNew = true;
          NL.viewNews();
        })
        .catch(function () { NL.paintStatus(); });
    }, AUTO_REFRESH);

    // 非资讯页：每 3 分钟静默检查一次，只更新数据不重绘
    _idleTimer = setInterval(function () {
      if (document.hidden) return;
      if (location.hash.indexOf('/news') >= 0) return;
      NL.loadLive({ force: true })
        .then(function (j) { if (j && j.changed) NL._state.hasNew = true; })
        .catch(function () {});
    }, IDLE_REFRESH);

    // 状态条倒计时每秒更新一次（显示"X秒前更新"）
    _countdownTimer = setInterval(function () {
      if (location.hash.indexOf('/news') >= 0 && !NL._state.loading) NL.paintStatus();
    }, 10000);

    // 页面重新可见时立即检查（从后台切回来）
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) return;
      if (location.hash.indexOf('/news') < 0) return;
      NL.loadLive({ force: true })
        .then(function () { NL.viewNews(); })
        .catch(function () { NL.paintStatus(); });
    });
  };

  /** 立即刷新（供路由切回资讯页时调用） */
  NL.refresh = function () {
    if (NL._state.loading) return;
    return NL.loadLive({ force: true })
      .then(function () { NL.viewNews(); })
      .catch(function () { NL.paintStatus(); });
  };

  NL.viewNews = function () {
    const data = currentData();
    const view = document.getElementById('view');
    if (!view) return;

    const arts = (data && data.articles) ? data.articles : [];
    const sources = (data && data.sources) ? data.sources : [];
    const topics = (data && data.topics) ? data.topics : [];
    const favs = getFavs();
    const st = NL._state;

    // 过滤
    let list = arts;
    if (st.fav) list = list.filter(a => favs.indexOf(a.url) >= 0);
    if (st.source !== 'all') list = list.filter(a => a.source === st.source);
    if (st.topic !== 'all') list = list.filter(a => (a.topics || []).indexOf(st.topic) >= 0);
    if (st.q) {
      const q = st.q.toLowerCase();
      list = list.filter(a =>
        (a.title || '').toLowerCase().indexOf(q) >= 0 ||
        (a.content || '').toLowerCase().indexOf(q) >= 0);
    }

    const shown = list.slice(0, 120);

    view.innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div>
          <h1>时政资讯</h1>
          <p class="sub">
            ${arts.length} 篇 · ${sources.length} 个来源 · ${topics.length} 个话题
          </p>
          <div id="newsStatus" style="margin-top:6px"></div>
        </div>
        <div class="row" style="gap:6px">
          <button class="btn sm${st.fav ? ' primary' : ''}" id="btnFavOnly">⭐ 收藏 ${favs.length}</button>
          <button class="btn sm primary" id="btnReload">⟳ 抓取最新</button>
        </div>
      </div>

      <div class="card pad" style="margin-bottom:12px">
        <div style="margin-bottom:8px">
          <input id="newsSearch" placeholder="🔍 搜索标题或摘要关键词…" value="${esc(st.q)}"
            style="width:100%;box-sizing:border-box;padding:9px 14px;border:1px solid var(--line);border-radius:8px;font-size:14px;background:var(--bg-1);color:var(--text-1)">
        </div>
        <div style="margin-bottom:6px" class="tiny">来源</div>
        <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:10px">
          <button class="btn sm${st.source === 'all' ? ' primary' : ''}" data-src="all">全部 ${arts.length}</button>
          ${sources.map(s => `<button class="btn sm${st.source === s.name ? ' primary' : ''}" data-src="${esc(s.name)}">${esc(s.name)} ${s.count}</button>`).join('')}
        </div>
        <div style="margin-bottom:6px" class="tiny">话题</div>
        <div class="row" style="gap:6px;flex-wrap:wrap">
          <button class="btn sm${st.topic === 'all' ? ' primary' : ''}" data-topic="all">全部</button>
          ${topics.map(t => `<button class="btn sm${st.topic === t.name ? ' primary' : ''}" data-topic="${esc(t.name)}">${esc(t.name)} <span class="tiny">${t.count}</span></button>`).join('')}
        </div>
      </div>

      <div class="spread" style="margin-bottom:8px">
        <span class="tiny">共 ${list.length} 条${list.length > 120 ? '（显示前 120 条）' : ''}</span>
      </div>

      ${shown.length ? `
        <div class="rows" id="newsList">
          ${shown.map((a, i) => {
            const isFav = favs.indexOf(a.url) >= 0;
            return `
            <div class="rowitem" style="cursor:pointer;align-items:flex-start" data-newsidx="${i}">
              <span class="rno" style="margin-top:2px">${relDate(a.date)}</span>
              <div style="flex:1;min-width:0">
                <div class="rtxt" style="margin-bottom:3px;line-height:1.55">${esc(a.title)}</div>
                <span class="tiny">
                  ${esc(a.source || '')}${a.topics && a.topics.length ? ' · ' + a.topics.map(t => esc(t)).join(' / ') : ''}
                </span>
              </div>
              <div class="row" style="gap:4px;flex-shrink:0">
                <button class="btn sm" data-fav="${esc(a.url)}" title="收藏" style="padding:2px 7px">${isFav ? '★' : '☆'}</button>
                <button class="btn sm" data-openurl="${esc(a.url)}" title="打开原文" style="padding:2px 7px">↗</button>
              </div>
            </div>`;
          }).join('')}
        </div>` : `
        <div class="empty">
          <div class="big">📰</div>
          <p>${arts.length ? '没有符合条件的资讯' : '暂无资讯'}</p>
          ${arts.length ? '<p class="tiny">试试切换来源或话题，或清空搜索关键词。</p>'
            : '<p class="tiny">请运行 <code>python scripts/fetch_news.py</code> 抓取内容。</p>'}
        </div>`}
    `;

    // ── 交互 ──
    $$('[data-src]', view).forEach(b => b.onclick = () => { st.source = b.dataset.src; NL.viewNews(); });
    $$('[data-topic]', view).forEach(b => b.onclick = () => { st.topic = b.dataset.topic; NL.viewNews(); });

    const favBtn = $('#btnFavOnly', view);
    if (favBtn) favBtn.onclick = () => { st.fav = !st.fav; NL.viewNews(); };

    const relBtn = $('#btnReload', view);
    if (relBtn) relBtn.onclick = () => {
      if (st.loading) return;
      relBtn.disabled = true;
      relBtn.textContent = '⏳ 抓取中…';
      NL.loadLive({ force: true })
        .then((j) => {
          NL.viewNews();
          if (window.toast) window.toast('已获取 ' + j.total + ' 篇最新资讯');
        })
        .catch((e) => {
          relBtn.disabled = false;
          relBtn.textContent = '⟳ 抓取最新';
          NL.paintStatus();
          if (window.toast) window.toast('抓取失败：' + (e.message || '') + '（需通过 python serve.py 启动）');
        });
    };

    // 绘制状态 + 数据超过 30 秒就自动拉一次
    NL.paintStatus();
    const stale = !NL._live || (Date.now() - NL._lastLiveTs > LIVE_TTL);
    if (stale && !st.loading) {
      NL.loadLive({ force: true })
        .then(function () { NL.viewNews(); })
        .catch(function () { NL.paintStatus(); });
    }
    NL.startAuto();

    const searchEl = $('#newsSearch', view);
    if (searchEl) {
      let timer = null;
      searchEl.oninput = () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          st.q = searchEl.value.trim();
          NL.viewNews();
          const s2 = $('#newsSearch');
          if (s2) { s2.focus(); s2.setSelectionRange(s2.value.length, s2.value.length); }
        }, 350);
      };
    }

    $$('[data-fav]', view).forEach(b => b.onclick = (e) => {
      e.stopPropagation();
      const nowFav = toggleFav(b.dataset.fav);
      b.textContent = nowFav ? '★' : '☆';
      const fb = $('#btnFavOnly');
      if (fb) fb.textContent = '⭐ 收藏 ' + getFavs().length;
      if (window.toast) window.toast(nowFav ? '已收藏' : '已取消收藏');
    });

    $$('[data-openurl]', view).forEach(b => b.onclick = (e) => {
      e.stopPropagation();
      if (b.dataset.openurl) window.open(b.dataset.openurl, '_blank');
    });

    // 点击行展开摘要
    $$('#newsList .rowitem', view).forEach(el => {
      el.onclick = () => {
        const a = shown[parseInt(el.dataset.newsidx)];
        if (a) showDetail(el, a);
      };
    });
  };

  function showDetail(row, a) {
    const next = row.nextElementSibling;
    if (next && next.classList.contains('news-detail')) { next.remove(); return; }

    const detail = document.createElement('div');
    detail.className = 'news-detail card pad';
    detail.style.cssText = 'margin:0 0 8px 0;font-size:14px;line-height:1.85;max-height:340px;overflow-y:auto';

    const topics = (a.topics || []).map(t =>
      `<span class="pill" style="font-size:11px;margin-right:4px">${esc(t)}</span>`).join('');

    detail.innerHTML = `
      <div style="margin-bottom:8px">
        ${topics}
        <span class="tiny" style="color:var(--text-2)">${esc(a.source || '')} · ${fmtDate(a.date)}</span>
      </div>
      ${a.content
        ? `<p style="margin:0 0 10px 0">${esc(a.content)}</p>`
        : `<p class="tiny" style="margin:0 0 10px 0;color:var(--text-2)">本地未缓存摘要，点击下方按钮查看原文全文。</p>`}
      <div class="row" style="gap:8px">
        <button class="btn sm primary" data-go="${esc(a.url)}">↗ 阅读原文</button>
        <button class="btn sm" data-copy="${esc(a.title)}">📋 复制标题</button>
      </div>`;

    detail.querySelector('[data-go]').onclick = (e) => {
      e.stopPropagation();
      window.open(a.url, '_blank');
    };
    detail.querySelector('[data-copy]').onclick = (e) => {
      e.stopPropagation();
      const t = a.title + ' ' + a.url;
      if (navigator.clipboard) navigator.clipboard.writeText(t);
      if (window.toast) window.toast('已复制');
    };

    row.insertAdjacentElement('afterend', detail);
  }

})();

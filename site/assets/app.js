/* =========================================================
   资料分析刷题 · 单页应用
   数据: window.__BANK__ = { meta, materials[], questions[] }
   后端: window.ZLFX_API（可选；无后端时自动离线）
   ========================================================= */
(function () {
  'use strict';

  const API = window.ZLFX_API || null;
  const LS = {
    state: 'zlfx.state.v1',
    custom: 'zlfx.customBanks.v1',
    pref: 'zlfx.pref.v1',
  };

  const LETTERS = ['A', 'B', 'C', 'D'];
  /* ---------------- storage ---------------- */
  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  const memStore = new Map();
  let storageOK = true;
  try {
    localStorage.setItem('__zlfx_probe__', '1');
    localStorage.removeItem('__zlfx_probe__');
  } catch (e) {
    storageOK = false;
  }

  const store = {
    get(key) {
      if (!storageOK) return memStore.has(key) ? memStore.get(key) : null;
      try { return localStorage.getItem(key); } catch (e) { return null; }
    },
    set(key, val) {
      if (!storageOK) { memStore.set(key, val); return true; }
      try { localStorage.setItem(key, val); return true; } catch (e) { return false; }
    },
  };

  function loadJSON(key, dflt) {
    try {
      const raw = store.get(key);
      return raw ? JSON.parse(raw) : dflt;
    } catch (e) {
      return dflt;
    }
  }

  function saveJSON(key, val) {
    try {
      return store.set(key, JSON.stringify(val));
    } catch (e) {
      toast('存储空间不足，本次进度未能保存');
      return false;
    }
  }

  const DEFAULT_STATE = {
    answers: {},
    marks: {},
    wrong: {},
    sets: {},
    visits: {},
    sessions: [],
    lastQ: null,
    streak: {},
  };

  let state = Object.assign({}, DEFAULT_STATE, loadJSON(LS.state, {}));
  ['answers', 'marks', 'wrong', 'sets', 'visits', 'streak'].forEach(k => {
    if (!state[k] || typeof state[k] !== 'object') state[k] = {};
  });
  if (!Array.isArray(state.sessions)) state.sessions = [];

  function persist() { saveJSON(LS.state, state); }

  let pref = Object.assign({
    theme: 'light',
    showMaterialText: false,
    autoNext: false,
    instantJudge: true,
  }, loadJSON(LS.pref, {}));

  function savePref() { saveJSON(LS.pref, pref); }

  let toastTimer = 0;
  function toast(msg) {
    const el = $('#toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
  }

  /* ---------------- DOM helpers ---------------- */
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function pct(a, b) { return b > 0 ? Math.round((a / b) * 100) : 0; }

  function todayKey(d) {
    const x = d || new Date();
    const m = String(x.getMonth() + 1).padStart(2, '0');
    const dd = String(x.getDate()).padStart(2, '0');
    return `${x.getFullYear()}-${m}-${dd}`;
  }

  function fmtDate(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  }

  function fmtClock(sec) {
    const s = Math.max(0, Math.floor(sec || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const ss = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
    return `${m}:${String(ss).padStart(2, '0')}`;
  }

  function fmtDuration(sec) {
    const s = Math.max(0, Math.floor(sec || 0));
    if (s < 60) return `${s} 秒`;
    const m = Math.floor(s / 60);
    const ss = s % 60;
    if (m < 60) return ss ? `${m} 分 ${ss} 秒` : `${m} 分钟`;
    const h = Math.floor(m / 60);
    return `${h} 小时 ${m % 60} 分`;
  }

  function normalizeBank(raw, id, name) {
    const materials = (raw.materials || []).map(m => ({
      id: String(m.id),
      set: Number(m.set),
      heading: m.heading || '',
      text: m.text || '',
      imgs: Array.isArray(m.imgs) ? m.imgs : [],
    }));
    const questions = (raw.questions || []).map(q => ({
      id: String(q.id),
      set: Number(q.set),
      no: Number(q.no),
      mat: String(q.mat || ''),
      stem: q.stem || '',
      options: (Array.isArray(q.options) ? q.options : []).slice(0, 4),
      answer: String(q.answer || '').trim().toUpperCase().slice(0, 1),
      imgs: Array.isArray(q.imgs) ? q.imgs : [],
      textok: !!q.textok,
      risky: !!q.risky,
    }));
    return { id, name, meta: raw.meta || {}, materials, questions };
  }

  function indexBank(b) {
    bank = b;
    qIndex = new Map();
    matIndex = new Map();
    bySet = new Map();
    b.questions.forEach(q => {
      qIndex.set(q.id, q);
      if (!bySet.has(q.set)) bySet.set(q.set, []);
      bySet.get(q.set).push(q);
    });
    bySet.forEach(arr => arr.sort((a, c) => a.no - c.no));
    b.materials.forEach(m => matIndex.set(m.id, m));
  }

  /* ---------------- bank stubs (委托至 __ZHENTI__ 题库) ---------------- */
  let bank = { questions: [], materials: [], name: '行测题库' };
  let qIndex = new Map();
  let matIndex = new Map();
  let bySet = new Map();

  async function _syncBank() {
    const ZH = window.ZLFX_ZHENTI;
    if (!ZH || !ZH.ensureIndex) return;
    try {
      const map = await ZH.ensureIndex();
      if (map && map.size) {
        bank.questions = Array.from(map.values());
        qIndex = map;
      }
    } catch (e) { /* shard load failed, retry on next view */ }
  }

  function setList() { return []; }
  function setQuestions(no) { return []; }
  function statsSet(no) { return { total: 0, done: 0, ok: 0, secs: 0 }; }
  function setTime(no) { return { elapsed: 0, limit: 0, submitted: false, submitTs: 0 }; }
  function saveSetTime(no, patch) {}

  /* ---------------- wrong / marks ---------------- */
  function isWrong(qid) {
    const w = state.wrong[qid];
    return !!w && w.wrongCount > 0 && !w.cleared;
  }

  function markWrong(q, sel) {
    const cur0 = state.wrong[q.id] || { wrongCount: 0, cleared: false };
    cur0.wrongCount = (cur0.wrongCount || 0) + 1;
    cur0.lastTs = Date.now();
    cur0.cleared = false;
    cur0.fixed = false;
    cur0.sel = sel;
    state.wrong[q.id] = cur0;
  }

  function dropWrong(qid) {
    delete state.wrong[qid];
    if (API && API.token) API.wrong(qid, 'drop', 'builtin');
  }

  function wrongIds() {
    return Object.keys(state.wrong).filter(id => {
      if (!state.wrong[id] || state.wrong[id].cleared) return false;
      return qIndex.has(id);
    });
  }

  function favIds() {
    return Object.keys(state.marks).filter(id => {
      if (!state.marks[id]) return false;
      return qIndex.has(id);
    });
  }

  function updateBadges() {
    const w = wrongIds().length;
    const f = favIds().length;
    const bw = $('#badgeWrong'), bf = $('#badgeFav');
    if (bw) { bw.textContent = w; bw.classList.toggle('zero', w === 0); }
    if (bf) { bf.textContent = f; bf.classList.toggle('zero', f === 0); }
    const sp = $('#sideProgress');
    if (sp) {
      const total = bank.questions.length;
      const done = Object.keys(state.answers).filter(id => qIndex.has(id)).length;
      sp.textContent = total ? `已练 ${done}/${total} · ${pct(done, total)}%` : '—';
    }
  }

  /* ---------------- stats ---------------- */
  function statsAll() {
    const ids = Object.keys(state.answers).filter(id => qIndex.has(id));
    let ok = 0, secs = 0;
    ids.forEach(id => {
      if (state.answers[id].ok) ok++;
      secs += state.answers[id].secs || 0;
    });
    const total = bank.questions.length;
    return { done: ids.length, ok, bad: ids.length - ok, total, secs };
  }


  function accuracy() {
    const s = statsAll();
    return s.done ? Math.round((s.ok / s.done) * 100) : 0;
  }



  /* ---------------- answer ---------------- */
  function answer(q, sel) {
    const ok = !!q.answer && sel === q.answer;
    const secs = Math.max(0, Math.min(3600, Math.round((Date.now() - (cur.qStart || Date.now())) / 1000)));
    cur.qStart = Date.now();

    if (!q.answer) {
      state.answers[q.id] = { sel, ok: false, ts: Date.now(), set: q.set, no: q.no, secs, unknown: true };
      persist();
      return { ok: false, unknown: true, secs };
    }

    state.answers[q.id] = { sel, ok, ts: Date.now(), set: q.set, no: q.no, secs };
    if (!ok) {
      markWrong(q, sel);
    } else if (isWrong(q.id)) {
      state.wrong[q.id].fixed = true;
    }

    const today = todayKey();
    state.streak[today] = (state.streak[today] || 0) + 1;
    persist();
    updateBadges();

    if (API && API.token) {
      API.answer({ qid: q.id, sel, ok, secs, bank: 'builtin' });
    }
    return { ok, unknown: false, secs };
  }

  /* =========================================================
     AUTH
     ========================================================= */
  let authMode = 'login';

  function needAuth() {
    // 只有主动访问 #/auth 时才显示登录页；
    // 未登录也能刷题（题库内置、记录存本地），
    // 避免 App/离线环境被强制跳到登录页。
    const raw = (location.hash || '').replace(/^#/, '').replace(/^\//, '');
    const head = raw.split('?')[0].split('/')[0];
    return head === 'auth';
  }

  function renderAuth(message) {
    setActiveNav('auth');
    const isReg = authMode === 'register';
    view().innerHTML = `
      <div class="auth-wrap">
        <div class="auth-card card">
          <div class="auth-head">
            <div class="logo big">资</div>
            <h1>${isReg ? '注册新账号' : '登录你的账号'}</h1>
            <p class="sub">${isReg ? '进度、错题本、收藏与计时都会保存在服务器' : '登录后可在同一账号下继续练习'}</p>
          </div>
          ${message ? `<div class="auth-msg">${esc(message)}</div>` : ''}
          <form id="authForm" autocomplete="on">
            <label class="field">
              <span>用户名</span>
              <input id="afUser" name="username" placeholder="3–20 位中文 / 字母 / 数字" autocomplete="username" required>
            </label>
            ${isReg ? `<label class="field"><span>昵称（可选）</span>
              <input id="afNick" name="nickname" placeholder="显示用昵称" autocomplete="nickname"></label>` : ''}
            <label class="field">
              <span>密码</span>
              <div class="pw-wrap">
                <input id="afPass" name="password" type="password" placeholder="至少 6 位" autocomplete="${isReg ? 'new-password' : 'current-password'}" required>
                <button type="button" class="pw-eye" data-for="afPass" title="显示/隐藏密码">👁</button>
              </div>
            </label>
            ${isReg ? `<label class="field"><span>确认密码</span>
              <div class="pw-wrap">
                <input id="afPass2" name="password2" type="password" placeholder="再输入一次" autocomplete="new-password" required>
                <button type="button" class="pw-eye" data-for="afPass2" title="显示/隐藏密码">👁</button>
              </div></label>` : ''}
            <button class="btn primary block" id="afSubmit" type="submit">${isReg ? '注册并登录' : '登录'}</button>
          </form>
          <div class="auth-foot">
            ${isReg
              ? '已经有账号了？<button class="link" id="afSwitch">去登录</button>'
              : '还没有账号？<button class="link" id="afSwitch">立即注册</button>'}
          </div>
          <div class="auth-note tiny">
            数据保存在本机 <code>quiz.db</code>；密码以 PBKDF2-SHA256（16 万轮）加盐存储，不上传任何外部服务器。
          </div>
        </div>
      </div>
    `;

    const form = $('#authForm');
    $('#afSwitch').onclick = () => {
      authMode = isReg ? 'login' : 'register';
      renderAuth();
    };

    // 密码显隐
    $$('.pw-eye').forEach(btn => {
      btn.onclick = () => {
        const input = document.getElementById(btn.dataset.for);
        if (!input) return;
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        btn.textContent = show ? '🙈' : '👁';
      };
    });

    form.onsubmit = async (e) => {
      e.preventDefault();
      const btn = $('#afSubmit');
      const username = $('#afUser').value.trim();
      const password = $('#afPass').value;
      const nickname = isReg ? ($('#afNick').value.trim()) : '';
      const pass2 = isReg ? $('#afPass2').value : password;

      if (!username) return toast('请输入用户名');
      if (!password) return toast('请输入密码');
      if (isReg && password !== pass2) return toast('两次输入的密码不一致');

      btn.disabled = true;
      btn.textContent = isReg ? '注册中…' : '登录中…';
      try {
        const user = isReg
          ? await API.register(username, password, nickname)
          : await API.login(username, password);
        await afterLogin(user, isReg);
      } catch (err) {
        btn.disabled = false;
        btn.textContent = isReg ? '注册并登录' : '登录';
        toast(err.message || '操作失败');
      }
    };
  }

  async function afterLogin(user, isNew) {
    let merged = { pulled: 0, pushed: 0 };
    try {
      merged = await syncWithServer();
    } catch (e) {
      toast('同步失败：' + (e.message || '网络异常'));
    }
    authMode = 'login';
    updateUserChip();
    updateBadges();
    toast(isNew ? `欢迎，${user.nickname || user.username}` : `欢迎回来，${user.nickname || user.username}`);
    if (merged.pulled > 0) {
      setTimeout(() => toast(`已合并服务器进度 ${merged.pulled} 条`), 1400);
    }
    location.hash = '#/home';
    render();
  }

  /** 登录后合并本地与服务端进度（取较新者），再整体推回服务端 */
  async function syncWithServer() {
    const remote = await API.getProgress();
    const rAnswers = remote.answers || {};
    const rMarks = remote.marks || {};
    const rWrong = remote.wrong || {};
    const rSets = remote.sets || {};
    const rDays = remote.days || {};

    let pulled = 0;

    // 每日练习量以服务器为准（服务器按天聚合，换设备也不会丢）
    Object.keys(rDays).forEach(day => {
      const d = rDays[day];
      state.streak[day] = Math.max(state.streak[day] || 0, d.n || 0);
      pulled++;
    });

    Object.keys(rAnswers).forEach(qid => {
      const r = rAnswers[qid];
      const l = state.answers[qid];
      if (!l || (r.ts || 0) > (l.ts || 0)) {
        const q = qIndex.get(qid);
        state.answers[qid] = {
          sel: r.sel, ok: !!r.ok, ts: r.ts || 0, secs: r.secs || 0,
          set: q ? q.set : undefined, no: q ? q.no : undefined,
        };
        pulled++;
      }
    });

    Object.keys(rMarks).forEach(qid => {
      if (!state.marks[qid]) { state.marks[qid] = 1; pulled++; }
    });

    Object.keys(rWrong).forEach(qid => {
      const r = rWrong[qid];
      const l = state.wrong[qid];
      if (!l || (r.lastTs || 0) >= (l.lastTs || 0)) {
        state.wrong[qid] = {
          wrongCount: r.wrongCount || 0,
          lastTs: r.lastTs || 0,
          cleared: !!r.cleared,
          fixed: !!r.fixed,
        };
        pulled++;
      }
    });

    Object.keys(rSets).forEach(no => {
      const r = rSets[no];
      const l = state.sets[no] || { elapsed: 0, limit: 0, submitted: false };
      state.sets[no] = {
        elapsed: Math.max(l.elapsed || 0, r.elapsed || 0),
        limit: r.limit || l.limit || 0,
        submitted: !!(l.submitted || r.submitted),
        submitTs: Math.max(l.submitTs || 0, r.submitTs || 0),
      };
      pulled++;
    });

    persist();

    await API.pushProgress({
      answers: state.answers,
      marks: state.marks,
      wrong: state.wrong,
    }).catch(() => null);

    Object.keys(state.sets).forEach(no => {
      const t = state.sets[no];
      API.timer(Number(no), t.elapsed || 0, t.limit || 0, !!t.submitted, 'builtin');
    });

    return { pulled, pushed: 0 };
  }

  function updateUserChip() {
    const box = $('#userChip');
    if (!box) return;
    if (API && API.token && API.user) {
      const name = API.user.nickname || API.user.username;
      box.innerHTML = `
        <span class="avatar">${esc(name.slice(0, 1))}</span>
        <span class="uname">${esc(name)}</span>
        <button class="link" id="btnLogout">退出</button>
      `;
      const b = $('#btnLogout');
      if (b) b.onclick = async () => {
        const sure = await confirmSheet({
          title: '退出登录？',
          body: '本地进度会保留，下次登录仍可同步回来。',
          ok: '退出',
        });
        if (!sure) return;
        await API.logout();
        updateUserChip();
        toast('已退出登录');
        render();
      };
    } else if (API && API.online) {
      box.innerHTML = `<button class="btn sm primary" id="btnToLogin">登录 / 注册</button>`;
      const b = $('#btnToLogin');
      if (b) b.onclick = () => { authMode = 'login'; renderAuth(); };
    } else {
      box.innerHTML = `<span class="tiny">离线模式</span>`;
    }
  }

  /* =========================================================
     ROUTER
     ========================================================= */
  const routes = [];
  function route(pattern, handler) { routes.push({ pattern, handler }); }

  function parseHash() {
    const raw = location.hash.replace(/^#/, '') || '/home';
    const [path, qs] = raw.split('?');
    const parts = path.split('/').filter(Boolean);
    const query = {};
    (qs || '').split('&').filter(Boolean).forEach(kv => {
      const idx = kv.indexOf('=');
      const k = idx >= 0 ? kv.slice(0, idx) : kv;
      const v = idx >= 0 ? kv.slice(idx + 1) : '';
      query[decodeURIComponent(k)] = decodeURIComponent(v || '');
    });
    return { parts, query, path };
  }

  function render() {
    const { parts, query } = parseHash();
    const head = parts[0] || 'home';
    

    if (needAuth()) {
      renderAuth();
      return;
    }
    document.body.classList.remove('guest');

    for (const r of routes) {
      if (r.pattern[0] !== head) continue;
      if (r.pattern.length !== parts.length) continue;
      // handler 可能是 async（如速查/错题/收藏需要等待真题分片加载）
      const ret = r.handler(parts, query);
      if (ret && typeof ret.catch === 'function') {
        ret.catch(err => console.error('route error', err));
      }
      return;
    }
    viewHome();
  }

  function setActiveNav(name) {
    $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.route === name));
    const map = {
      home: '首页', cats: '分类刷题', sets: '资料分析套题', practice: '答题',
      wrong: '错题本', fav: '我的收藏', search: '题库速查', stats: '学习统计',
      import: '题库管理', auth: '登录', drillrun: '分类答题', news: '时政资讯',
      shenlun: '申论批改',
      cidian: '常考词汇',
      fanwen: '申论范文',
      law: '法律专业科目',
      papers: '真题套卷',
    };
    const c = $('#crumb');
    if (c) c.textContent = map[name] || '首页';
  }

  const view = () => $('#view');

  /* =========================================================
     HOME
     ========================================================= */
  function viewHome() {
    setActiveNav('home');
    const s = statsAll();
    const wrong = wrongIds().length;
    const fav = favIds().length;
    const acc = accuracy();
    const last = null;

    // 分类真题概览（只读索引，不拉全量题库）
    const ZT = window.__ZHENTI__ || { categories: [], questions: [] };
    const ztCatsList = (ZT.categories || []).filter(c => c.count > 0);
    const ztTotal = ztCatsList.reduce((a, c) => a + (c.count || 0), 0);
    const ztCats = ztCatsList.length;
    const ICONS = { politics: '★', common: '◈', verbal: '文', quantity: '∑', graph: '◫', judge: '⊹', data: '▤' };
    const catMini = ztCatsList.map(c => `
      <button class="cat-card" data-gocat="${c.key}">
        <span class="cat-ico">${ICONS[c.key] || '·'}</span>
        <span class="cat-name">${esc(c.name)}</span>
        <span class="cat-n">${c.count} 题</span>
      </button>`).join('') || '<p class="tiny">真题库尚未导入</p>';

    const recentSets = '';  // 资料分析套题已移除

    view().innerHTML = `
      <section class="hero">
        <h1>行测分类真题</h1>
        <p class="sub">政治理论 / 常识判断 / 言语理解 / 数量关系 / 图形推理 / 判断推理 / 资料分析 · 2023–2026 国考 + 省考真题</p>
        <div class="hero-grid">
          <div class="hero-stat"><b>${ztTotal}</b><span>真题道数</span></div>
          <div class="hero-stat"><b>${ztCats}</b><span>已导入分类</span></div>
          <div class="hero-stat"><b>${s.done}</b><span>已练题目</span></div>
          <div class="hero-stat"><b>${acc}%</b><span>正确率</span></div>
        </div>
        <div class="hero-cta">
          <button class="btn primary" onclick="location.hash='#/cats'">开始分类刷题</button>
          <button class="btn" onclick="location.hash='#/wrong'">错题复习（${wrong}）</button>
                  </div>
      </section>

      <div class="grid g4" style="margin-top:16px">
        <div class="card stat-card">
          <div class="k">今日练习</div>
          <div class="v">${state.streak[todayKey()] || 0}</div>
          <div class="d">连续打卡 ${streakDays()} 天</div>
        </div>
        <div class="card stat-card">
          <div class="k">答对 / 答错</div>
          <div class="v">${s.ok} <span style="font-size:14px;color:var(--text-3)">/ ${s.bad}</span></div>
          <div class="d">累计作答 ${s.done} 次记录</div>
        </div>
        <div class="card stat-card">
          <div class="k">答题累计用时</div>
          <div class="v" style="font-size:19px">${fmtDuration(s.secs)}</div>
          <div class="d">平均 ${s.done ? fmtDuration(Math.round(s.secs / s.done)) + '/题' : '—'}</div>
        </div>
        <div class="card stat-card">
          <div class="k">错题 / 收藏</div>
          <div class="v"><span style="color:var(--bad)">${wrong}</span> <span style="font-size:15px;color:var(--text-3)">/ ${fav}</span></div>
          <div class="d">答对后需手动移出错题</div>
        </div>
      </div>

      <div class="grid g2" style="margin-top:16px">
        <div class="card pad">
          <div class="spread" style="margin-bottom:12px">
            <h2 style="margin:0">分类入口</h2>
            <a class="tiny" href="#/cats">自定义题数 →</a>
          </div>
          <div class="cat-grid mini">${catMini}</div>
          <div class="hr"></div>
          <div class="quick">
            <a href="#/wrong"><span class="qi">✦</span><span><b>错题重练</b><span>${wrong} 道错题待消化</span></span></a>
            <a href="#/stats"><span class="qi">◔</span><span><b>学习统计</b><span>正确率趋势与用时分布</span></span></a>
          </div>
        </div>
        </div>
    `;
    $$('#view [data-gocat]').forEach(b => b.onclick = () => {
      const ZH = window.ZLFX_ZHENTI;
      if (ZH && ZH.state) {
        // 预选分类后再进分类页
        const st = ZH.state();
        if (st && st.selected) st.selected.cat = b.dataset.gocat;
      }
      location.hash = '#/cats';
    });
  }

  function renderRecent(n) {
    const list = Object.keys(state.answers)
      .map(id => ({ id, a: state.answers[id] }))
      .filter(x => qIndex.has(x.id))
      .sort((a, b) => (b.a.ts || 0) - (a.a.ts || 0))
      .slice(0, n);
    if (!list.length) return `<p class="tiny">还没有作答记录，选一套开始吧。</p>`;
    return `<div class="rows">` + list.map(({ id, a }) => {
      const q = qIndex.get(id);
      return `<div class="rowitem">
        <span class="rno">${q.set}-${q.no}</span>
        <span class="rtxt">${esc((q.stem || '（图题）').slice(0, 46))}</span>
        <span class="pill ${a.ok ? 'ok' : 'bad'}">${a.ok ? '对' : '错'}</span>
        <span class="tiny">${a.secs ? fmtDuration(a.secs) : ''}</span>
        <span class="tiny">${fmtDate(a.ts)}</span>
      </div>`;
    }).join('') + `</div>`;
  }

  function streakDays() {
    let n = 0;
    const d = new Date();
    while (state.streak[todayKey(d)]) {
      n++;
      d.setDate(d.getDate() - 1);
    }
    return n;
  }

  /* =========================================================
     WRONG BOOK
     ========================================================= */
  /* 真题题库索引（用于错题本/收藏兼容两种题库） */
  function ztIndex() {
    const Z = window.__ZHENTI__ || { questions: [] };
    const map = new Map();
    (Z.questions || []).forEach(q => map.set(q.id, q));
    return map;
  }

  /** 异步加载真题全量映射（分片按需） */
  async function ztIndexAsync() {
    const ZH = window.ZLFX_ZHENTI;
    if (ZH && typeof ZH.ensureIndex === 'function') {
      try {
        return await ZH.ensureIndex();
      } catch (e) { /* 忽略，回退到内联 */ }
    }
    return ztIndex();
  }

  async function viewWrong(parts, query) {
    setActiveNav('wrong');
    const filter = query.set;
    const ZT = await ztIndexAsync();

    // 合并两类错题：资料分析套题 + 分类真题
    let ids = Object.keys(state.wrong).filter(id => {
      const w = state.wrong[id];
      if (!w || !(w.wrongCount > 0) || w.cleared) return false;
      return qIndex.has(id) || ZT.has(id);
    });
    if (filter) ids = ids.filter(id => {
      const q = qIndex.get(id);
      return q && q.set === Number(filter);
    });
    ids.sort((a, b) => (state.wrong[b].lastTs || 0) - (state.wrong[a].lastTs || 0));

    const rows = ids.map(id => {
      const q = qIndex.get(id);
      const z = ZT.get(id);
      const w = state.wrong[id];
      const label = q ? `${q.set}-${String(q.no).padStart(2, '0')}` : '真题';
      const text = q ? (q.stem || '（图题）') : (z ? z.stem : '（题目缺失）');
      return `<div class="rowitem">
        <span class="rno">${label}</span>
        <span class="rtxt">${esc((text || '').slice(0, 60))}</span>
        ${z ? `<span class="pill">${esc((z.cat || ''))}</span>` : ''}
        <span class="pill bad">错 ${w.wrongCount} 次</span>
        <span class="tiny">${w.lastTs ? fmtDate(w.lastTs) : ''}</span>
        <span class="rops">
          <button class="btn sm" data-open="${id}" data-kind="${q ? 'set' : 'zt'}">重做</button>
          <button class="btn sm" data-drop="${id}">移出</button>
        </span>
      </div>`;
    }).join('');

    view().innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div>
          <h1>错题本</h1>
          <p class="sub">做错自动收录 · 共 ${ids.length} 道（含分类真题）${filter ? '（已筛选第 ' + filter + ' 套）' : ''}</p>
        </div>
        <div class="row">
          <button class="btn primary" id="wrongPractice" ${ids.length ? '' : 'disabled'}>顺序重练</button>
          <button class="btn" id="wrongRandom" ${ids.length ? '' : 'disabled'}>随机 10 题</button>
          ${filter ? '<button class="btn" onclick="location.hash=\'#/wrong\'">清除筛选</button>' : ''}
        </div>
      </div>
      ${ids.length ? `<div class="rows">${rows}</div>`
        : `<div class="empty"><div class="big">✦</div><p>错题本是空的 —— 继续保持。</p>
           <button class="btn" onclick="location.hash='#/cats'">去练真题</button></div>`}
    `;

    $$('[data-open]').forEach(b => b.onclick = () => {
      const id = b.dataset.open;
      const ZH = window.ZLFX_ZHENTI;
      if (ZH && ZH.practiceOne) {
        ZH.practiceOne(id);
      } else {
        toast('真题模块未加载');
      }
    });
    $$('[data-drop]').forEach(b => b.onclick = () => {
      dropWrong(b.dataset.drop);
      persist();
      updateBadges();
      viewWrong([], query);
    });

    const wp = $('#wrongPractice');
    if (wp) wp.onclick = () => {
      const ZH = window.ZLFX_ZHENTI;
      const ztIds = ids.filter(id => !qIndex.has(id));
      if (ztIds.length && ZH && ZH.practiceList) {
        ZH.practiceList(ztIds);
      } else {
        window.ZLFX_ZHENTI && window.ZLFX_ZHENTI.practiceList && window.ZLFX_ZHENTI.practiceList(ids);
      }
    };
    const wr = $('#wrongRandom');
    if (wr) wr.onclick = () => {
      const pick = ids.slice().sort(() => Math.random() - 0.5).slice(0, 10);
      const ZH = window.ZLFX_ZHENTI;
      if (pick.some(id => !qIndex.has(id)) && ZH && ZH.practiceList) {
        ZH.practiceList(pick);
      } else {
        window.ZLFX_ZHENTI && window.ZLFX_ZHENTI.practiceList && window.ZLFX_ZHENTI.practiceList(pick);
      }
    };
  }

  

  /* =========================================================
     FAVORITES
     ========================================================= */
  async function viewFav() {
    setActiveNav('fav');
    const ZT = await ztIndexAsync();
    // 兼容两类题库：资料分析套题 + 分类真题
    const ids = Object.keys(state.marks)
      .filter(id => state.marks[id] && (qIndex.has(id) || ZT.has(id)))
      .sort((a, b) => {
        const qa = qIndex.get(a), qb = qIndex.get(b);
        if (qa && qb) return (qa.set - qb.set) || (qa.no - qb.no);
        return a < b ? -1 : 1;
      });

    const rows = ids.map(id => {
      const q = qIndex.get(id);
      const z = ZT.get(id);
      const label = q ? `${q.set}-${String(q.no).padStart(2, '0')}` : '真题';
      const text = q ? (q.stem || '（图题）') : (z ? z.stem : '（题目缺失）');
      return `<div class="rowitem">
        <span class="rno">${label}</span>
        <span class="rtxt">${esc((text || '').slice(0, 60))}</span>
        ${z ? `<span class="pill">${esc(z.cat || '')}</span>` : ''}
        ${isWrong(id) ? '<span class="pill bad">错题</span>' : ''}
        <span class="rops">
          <button class="btn sm" data-open="${id}" data-kind="${q ? 'set' : 'zt'}">打开</button>
          <button class="btn sm danger" data-unfav="${id}">取消</button>
        </span>
      </div>`;
    }).join('');

    view().innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div><h1>我的收藏</h1><p class="sub">共 ${ids.length} 道（含分类真题）</p></div>
        <div class="row">
          <button class="btn primary" id="favPractice" ${ids.length ? '' : 'disabled'}>连续演练</button>
          <button class="btn" id="favExport" ${ids.length ? '' : 'disabled'}>导出</button>
        </div>
      </div>
      ${ids.length ? `<div class="rows">${rows}</div>`
        : `<div class="empty"><div class="big">★</div><p>还没有收藏的题目。答题时点右上角「☆ 收藏」即可。</p></div>`}
    `;

    $$('[data-open]').forEach(b => b.onclick = () => {
      const id = b.dataset.open;
      const ZH = window.ZLFX_ZHENTI;
      if (ZH && ZH.practiceOne) {
        ZH.practiceOne(id);
      } else {
        toast('真题模块未加载');
      }
    });
    $$('[data-unfav]').forEach(b => b.onclick = () => {
      state.marks[b.dataset.unfav] = 0;
      if (API && API.token) API.favorite(b.dataset.unfav, false, 'builtin');
      persist(); updateBadges(); viewFav();
    });
    const fp = $('#favPractice');
    if (fp) fp.onclick = () => {
      const ZH = window.ZLFX_ZHENTI;
      if (ids.some(id => !qIndex.has(id)) && ZH && ZH.practiceList) ZH.practiceList(ids);
      else window.ZLFX_ZHENTI && window.ZLFX_ZHENTI.practiceList && window.ZLFX_ZHENTI.practiceList(ids);
    };
    const fe = $('#favExport');
    if (fe) fe.onclick = () => {
      const data = ids.map(id => {
        const q = qIndex.get(id);
        if (q) return { set: q.set, no: q.no, stem: q.stem, options: q.options, answer: q.answer };
        const z = ZT.get(id) || {};
        return { cat: z.cat, paper: z.paper, stem: z.stem, options: z.options, answer: z.answer };
      });
      downloadJSON(data, 'favorites.json');
    };
  }

  /* =========================================================
     SEARCH
     ========================================================= */
  async function viewSearch(parts, query) {
    setActiveNav('search');
    const kw = query.q || '';
    const onlyWrong = query.w === '1';

    // 合并两类题库：资料分析套题（bank.questions）+ 分类真题（分片加载）
    // 注意：真题分片必须 await，否则只能搜到资料分析那 600 题
    const ZT = await ztIndexAsync();
    const ztList = Array.from(ZT.values()).map(z => ({
      id: String(z.id),
      set: (z.year || '') + (z.region || ''),
      no: z.no || 0,
      stem: z.stem || '',
      options: z.options || ['', '', '', ''],
      answer: z.answer || '',
      isZT: true,
    }));
    let list = ztList;  // 仅使用分类真题

    if (onlyWrong) list = list.filter(q => isWrong(q.id));
    if (kw) {
      const k = kw.toLowerCase();
      list = list.filter(q => {
        if (q.id.toLowerCase().includes(k)) return true;
        if (q.stem && q.stem.toLowerCase().includes(k)) return true;
        if (q.answer === kw.toUpperCase()) return true;
        return q.options.some(o => String(o).toLowerCase().includes(k));
      });
    }
    const limited = list.slice(0, 200);

    view().innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div><h1>题库速查</h1><p class="sub">按题号 / 题干 / 选项 / 答案检索全库 <b>${ztList.length}</b> 题</p></div>
      </div>
      <div class="card pad" style="margin-bottom:14px">
        <div class="row">
          <input id="kw" class="btn" style="flex:1;text-align:left;min-width:180px" placeholder="输入关键词，如：环比、政府债券、s01q03" value="${esc(kw)}">
          <label class="pill" style="cursor:pointer"><input type="checkbox" id="onlyWrong" ${onlyWrong ? 'checked' : ''} style="margin-right:5px">仅错题</label>
          <button class="btn primary" id="btnSearch">搜索</button>
        </div>
      </div>
      <p class="tiny" style="margin-bottom:10px">共命中 ${list.length} 题${list.length > 200 ? '，仅显示前 200' : ''}</p>
      <div class="rows">
        ${limited.map(q => {
      const a = state.answers[q.id];
      const rno = q.isZT ? `${esc(q.set)} · ${q.no}` : `${q.set}-${String(q.no).padStart(2, '0')}`;
      return `<div class="rowitem">
            <span class="rno">${rno}</span>
            <span class="rtxt">${esc((q.stem || '（图题）').slice(0, 70))}</span>
            ${q.isZT ? '<span class="pill brand">真题</span>' : ''}
            <span class="pill">答案 ${q.answer || '?'}</span>
            ${isWrong(q.id) ? '<span class="pill bad">错题</span>' : ''}
            ${state.marks[q.id] ? '<span class="pill brand">★</span>' : ''}
            ${a ? `<span class="pill ${a.ok ? 'ok' : 'bad'}">${a.ok ? '对' : '错'}</span>` : ''}
            <button class="btn sm" data-open="${q.id}" data-iszt="${q.isZT ? '1' : '0'}">打开</button>
          </div>`;
    }).join('') || `<div class="empty"><div class="big">⌕</div><p>没有匹配的题目</p></div>`}
      </div>
    `;

    const go = () => {
      const v = $('#kw').value.trim();
      const w = $('#onlyWrong').checked ? '1' : '0';
      location.hash = `#/search?q=${encodeURIComponent(v)}&w=${w}`;
    };
    $('#btnSearch').onclick = go;
    $('#kw').onkeydown = e => { if (e.key === 'Enter') go(); };
    $('#onlyWrong').onchange = go;
    $$('[data-open]').forEach(b => b.onclick = () => {
      const id = b.dataset.open;
      // 分类真题：用分类练习打开
      if (b.dataset.iszt === '1') {
        const ZH = window.ZLFX_ZHENTI;
        if (ZH && typeof ZH.practiceOne === 'function') {
          ZH.practiceOne(id);
        } else {
          toast('该题暂无法打开');
        }
        return;
      }
      // 导入题库/资料分析套题：定位跳转
      if (qIndex.get(id)) {
        location.hash = '#/drillrun';
        return;
      }
      toast('该题暂无法打开');
    });
  }

  /* =========================================================
     STATS
     ========================================================= */
  function viewStats() {
    setActiveNav('stats');
    const s = statsAll();
    const acc = accuracy();
    const sets = setList();

    const perSet = sets.map(no => {
      const st = statsSet(no);
      const t = setTime(no);
      return {
        no, ...st,
        acc: st.done ? Math.round((st.ok / st.done) * 100) : 0,
        elapsed: t.elapsed || 0,
        submitted: !!t.submitted,
      };
    });

    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      days.push({ key: todayKey(d), label: `${d.getMonth() + 1}/${d.getDate()}`, n: state.streak[todayKey(d)] || 0 });
    }
    const maxDay = Math.max(1, ...days.map(d => d.n));

    const wrongBySet = {};
    wrongIds().forEach(id => {
      const q = qIndex.get(id);
      const key = q ? (q.paper || q.year || q.set || '未知') : '未知';
      wrongBySet[key] = (wrongBySet[key] || 0) + 1;
    });
    const wrongTop = Object.entries(wrongBySet).sort((a, b) => b[1] - a[1]).slice(0, 6);

    const timeTop = perSet.filter(x => x.elapsed > 0).sort((a, b) => b.elapsed - a.elapsed).slice(0, 5);
    const maxTime = Math.max(1, ...timeTop.map(x => x.elapsed));

    view().innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div><h1>学习统计</h1>
          <p class="sub">${API && API.token ? '已登录：' + esc(API.user.nickname || API.user.username) + '（数据已同步到服务器）' : '离线模式，数据保存在本机'}</p></div>
        <div class="row">
          <button class="btn" id="btnExport">导出进度</button>
          <button class="btn danger" id="btnReset">清空进度</button>
        </div>
      </div>

      <div class="grid g4">
        <div class="card stat-card"><div class="k">已作答</div><div class="v">${s.done}</div><div class="d">/ ${s.total} 题</div></div>
        <div class="card stat-card"><div class="k">正确率</div><div class="v">${acc}%</div>
          <div class="bar ${acc >= 70 ? 'ok' : ''}"><i style="width:${acc}%"></i></div></div>
        <div class="card stat-card"><div class="k">答题累计用时</div><div class="v" style="font-size:19px">${fmtDuration(s.secs)}</div>
          <div class="d">平均 ${s.done ? fmtDuration(Math.round(s.secs / s.done)) + '/题' : '—'}</div></div>
        <div class="card stat-card"><div class="k">错题 / 收藏</div>
          <div class="v"><span style="color:var(--bad)">${wrongIds().length}</span> <span style="font-size:15px;color:var(--text-3)">/ ${favIds().length}</span></div>
          <div class="d">答对后需手动移出错题</div></div>
      </div>

      <div class="grid g2" style="margin-top:16px">
        <div class="card pad">
          <h2>近 7 天练习量</h2>
          <div class="chart">
            ${days.map(d => `<div class="col"><i style="height:${Math.round((d.n / maxDay) * 100)}%"></i><span class="lbl">${d.label}</span></div>`).join('')}
          </div>
          <p class="tiny" style="margin-top:8px">按每次作答计，共 ${days.reduce((a, c) => a + c.n, 0)} 次</p>
        </div>
        <div class="card pad">
          <h2>耗时最多的套题</h2>
          ${timeTop.length ? timeTop.map(x => `
            <div style="margin-bottom:9px">
              <div class="spread" style="font-size:13px"><span>第 ${x.no} 套${x.submitted ? ' · 已交卷' : ''}</span><span class="tiny">${fmtClock(x.elapsed)}</span></div>
              <div class="bar"><i style="width:${pct(x.elapsed, maxTime)}%"></i></div>
            </div>`).join('') : '<p class="tiny">还没有计时数据，去练一套吧。</p>'}
          ${wrongTop.length ? `<div class="hr"></div><h3>错题集中套数</h3>` +
            wrongTop.map(([no, n]) => `
              <div style="margin-bottom:9px">
                <div class="spread" style="font-size:13px"><span>第 ${no} 套</span><span class="tiny">${n} 题</span></div>
                <div class="bar"><i style="width:${pct(n, Math.max(...wrongTop.map(x => x[1])))}%;background:var(--bad)"></i></div>
              </div>`).join('') : ''}
        </div>
      </div>

      <div class="card pad" style="margin-top:16px">
        <h2>各套完成度与用时</h2>
        <div class="heat">
          ${perSet.map(x => {
      const cls = x.done === 0 ? 'none' : x.acc >= 80 ? 'h3' : x.acc >= 50 ? 'h2' : 'h1';
      return `<div class="${cls}" title="第${x.no}套：${x.done}/${x.total}，正确率${x.acc}%${x.elapsed ? '，用时' + fmtClock(x.elapsed) : ''}">${x.no}</div>`;
    }).join('')}
        </div>
        <div class="legend" style="margin-top:12px">
          <span><i style="background:var(--ok-soft)"></i>≥80%</span>
          <span><i style="background:var(--warn-soft)"></i>50–79%</span>
          <span><i style="background:var(--bad-soft)"></i>&lt;50%</span>
          <span><i style="background:var(--bg-soft)"></i>未练习</span>
        </div>
        <div class="hr"></div>
        <div class="rows">
          ${perSet.filter(x => x.elapsed > 0).slice(0, 10).map(x => `<div class="rowitem">
            <span class="rno">第 ${x.no} 套</span>
            <span class="rtxt">${x.done}/${x.total} 题 · 正确 ${x.acc}%</span>
            <span class="pill">${x.submitted ? '已交卷' : '计时中'}</span>
            <span class="tiny">用时 ${fmtClock(x.elapsed)}</span>
          </div>`).join('') || '<p class="tiny">暂无套题计时记录。</p>'}
        </div>
      </div>
    `;

    $('#btnExport').onclick = () => {
      downloadJSON({ state, pref, exportedAt: new Date().toISOString() }, 'zlfx-progress.json');
    };
    $('#btnReset').onclick = () => {
      openSheet(`
        <h2>清空全部学习进度？</h2>
        <p class="sub">将删除作答记录、错题本、收藏与计时${API && API.token ? '，并同步清空服务器数据' : ''}。不可撤销。</p>
        <div class="row" style="margin-top:14px">
          <button class="btn danger" id="doReset">确认清空</button>
          <button class="btn" onclick="document.getElementById('sheetClose').click()">取消</button>
        </div>
      `);
      $('#doReset').onclick = async () => {
        if (API && API.token) await API.resetProgress().catch(() => null);
        state = JSON.parse(JSON.stringify(DEFAULT_STATE));
        persist();
        updateBadges();
        closeSheet();
        viewStats();
        toast('已清空');
      };
    };
  }

  /* =========================================================
     IMPORT
     ========================================================= */
  function viewImport() {
    setActiveNav('import');
    const customs = loadJSON(LS.custom, []);
    view().innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div><h1>题库管理</h1><p class="sub">可导入外部题库</p></div>
        <div class="row">
          <button class="btn" id="btnExportBank">导出当前题库</button>
        </div>
      </div>

      <div class="grid g2">
        <div class="card pad">
          <h2>导入题库</h2>
          <p class="tiny" style="margin-bottom:10px">支持 JSON（数组或 {questions:[...]}）与 CSV。字段：set, no, stem, options(A–D 或数组), answer。</p>
          <div class="drop" id="drop">
            <div style="font-size:26px;opacity:.6">⇪</div>
            <p>拖拽文件到此处，或点击选择</p>
            <input type="file" id="file" accept=".json,.csv,.txt" class="hidden">
          </div>
          <div class="hr"></div>
          <h3>或粘贴文本</h3>
          <textarea id="pasteBox" placeholder='[{"set":1,"no":1,"stem":"题干","options":["A内容","B内容","C内容","D内容"],"answer":"A"}]'></textarea>
          <div class="row" style="margin-top:10px">
            <button class="btn primary" id="btnPasteImport">解析并导入</button>
            <button class="btn" id="btnFormat">查看格式示例</button>
          </div>
        </div>

        <div class="card pad">
          <h2>我的题库</h2>
          <div class="rows" id="bankList">
            <div class="rowitem">
              <span class="rno">内置</span>
              <span class="rtxt">分类真题题库</span>
              <span class="pill ok">使用中</span>
            </div>
            ${customs.map(b => `<div class="rowitem">
              <span class="rno">自建</span>
              <span class="rtxt">${esc(b.name)} · ${(b.questions || []).length} 题</span>
              <span class="rops">
                <button class="btn sm" data-use="${b.id}">切换</button>
                <button class="btn sm danger" data-del="${b.id}">删除</button>
              </span>
            </div>`).join('') || '<p class="tiny">还没有导入过题库。</p>'}
          </div>
          <div class="hr"></div>
          <h3>说明</h3>
          <ul class="tiny" style="margin:0;padding-left:18px;line-height:1.9">
            <li>导入的题库保存在浏览器本地（localStorage）。</li>
            <li>大题库请优先使用 JSON 文件，CSV 适合纯文字题。</li>
            <li>题目图片字段 <code>imgs</code> 可填相对路径数组。</li>
            <li>无 <code>answer</code> 的题仍可练习，但不计对错。</li>
          </ul>
        </div>
      </div>
    `;

    const fileInput = $('#file');
    const drop = $('#drop');
    drop.onclick = () => fileInput.click();
    drop.ondragover = e => { e.preventDefault(); drop.classList.add('hover'); };
    drop.ondragleave = () => drop.classList.remove('hover');
    drop.ondrop = e => {
      e.preventDefault(); drop.classList.remove('hover');
      const f = e.dataTransfer.files[0];
      if (f) readBankFile(f);
    };
    fileInput.onchange = () => { if (fileInput.files[0]) readBankFile(fileInput.files[0]); };

    $('#btnPasteImport').onclick = () => {
      const txt = $('#pasteBox').value.trim();
      if (!txt) { toast('请先粘贴内容'); return; }
      try {
        saveCustomBank(parseBankText(txt));
      } catch (e) {
        toast('解析失败：' + e.message);
      }
    };

    $('#btnFormat').onclick = () => openSheet(`
      <h2>题库格式</h2>
      <h3>JSON</h3>
      <pre>{
  "name": "我的题库",
  "questions": [
    {
      "id": "c1",
      "set": 1, "no": 1,
      "stem": "题干文字",
      "options": ["A项", "B项", "C项", "D项"],
      "answer": "B",
      "imgs": ["assets/my/q1.jpg"]
    }
  ]
}</pre>
      <h3>CSV</h3>
      <pre>set,no,stem,A,B,C,D,answer
1,1,"题干","选项A","选项B","选项C","选项D",B</pre>
      <p class="tiny">第一行可为表头。含逗号的字段请用双引号包裹。</p>
    `);

    $$('[data-use]').forEach(b => b.onclick = () => {
      const list = loadJSON(LS.custom, []);
      const found = list.find(x => x.id === b.dataset.use);
      if (!found) return;
      applyBank(normalizeBank(found, found.id, found.name));
      toast('已切换到：' + found.name);
      location.hash = '#/home';
    });
    $$('[data-del]').forEach(b => b.onclick = () => {
      const list = loadJSON(LS.custom, []).filter(x => x.id !== b.dataset.del);
      saveJSON(LS.custom, list);
      viewImport();
      toast('已删除');
    });

    $('#btnExportBank').onclick = () => downloadJSON(bank, (bank.name || 'bank') + '.json');
  }

  function readBankFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const text = String(reader.result || '');
        const name = file.name.replace(/\.(json|csv|txt)$/i, '');
        saveCustomBank(parseBankText(text), name);
      } catch (e) {
        toast('文件解析失败：' + e.message);
      }
    };
    reader.readAsText(file, 'utf-8');
  }

  function parseBankText(text) {
    const t = text.trim();
    if (!t) throw new Error('内容为空');
    if (t.startsWith('{') || t.startsWith('[')) {
      const obj = JSON.parse(t);
      const arr = Array.isArray(obj) ? obj : (obj.questions || []);
      if (!Array.isArray(arr) || !arr.length) throw new Error('没有找到 questions 数组');
      const materials = (!Array.isArray(obj) && Array.isArray(obj.materials)) ? obj.materials : [];
      return {
        name: (!Array.isArray(obj) && obj.name) || '导入题库',
        meta: (!Array.isArray(obj) && obj.meta) || {},
        materials, questions: arr,
      };
    }
    const lines = t.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) throw new Error('CSV 行数不足');
    const split = (line) => {
      const out = [];
      let c = '', inQ = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') {
          if (inQ && line[i + 1] === '"') { c += '"'; i++; }
          else inQ = !inQ;
        } else if (ch === ',' && !inQ) { out.push(c); c = ''; }
        else c += ch;
      }
      out.push(c);
      return out;
    };
    const head = split(lines[0]).map(s => s.trim().toLowerCase());
    const hasHead = head.includes('stem') || head.includes('answer');
    const body = hasHead ? lines.slice(1) : lines;
    const questions = body.map((line, i) => {
      const c = split(line);
      const idx = (name, dflt) => {
        const k = hasHead ? head.indexOf(name) : -1;
        return k >= 0 ? c[k] : c[dflt];
      };
      return {
        id: `csv-${i + 1}`,
        set: Number(idx('set', 0)) || 1,
        no: Number(idx('no', 1)) || i + 1,
        stem: idx('stem', 2) || '',
        options: [idx('a', 3), idx('b', 4), idx('c', 5), idx('d', 6)],
        answer: (idx('answer', 7) || '').trim().toUpperCase(),
      };
    });
    return { name: 'CSV 导入题库', meta: {}, materials: [], questions };
  }

  function saveCustomBank(data) {
    const parsed = normalizeBank(data, uid(), data.name || '导入题库');
    const list = loadJSON(LS.custom, []);
    list.unshift({
      id: parsed.id, name: parsed.name, meta: parsed.meta,
      materials: parsed.materials, questions: parsed.questions,
    });
    const trimmed = list.slice(0, 6);
    if (!saveJSON(LS.custom, trimmed)) {
      saveJSON(LS.custom, [{
        id: parsed.id, name: parsed.name, meta: {}, materials: [], questions: parsed.questions,
      }]);
    }
    toast(`已导入 ${parsed.questions.length} 题`);
    viewImport();
  }

  function applyBank(b) {
    indexBank(b);
    state.lastQ = null;
    persist();
    updateBadges();
    updateBrandSub();
  }

  /** 侧栏文案：优先展示真题分类总数，其次资料分析套题数 */
  function updateBrandSub() {
    const sub = $('#brandSub');
    if (!sub) return;
    const ZT = window.__ZHENTI__ || { categories: [] };
    const ztTotal = (ZT.categories || []).reduce((a, c) => a + (c.count || 0), 0);
    const ztCats = (ZT.categories || []).filter(c => c.count > 0).length;
    if (ztTotal > 0) {
      sub.textContent = `${ztTotal} 题 · ${ztCats} 大类`;
    } else if (bank) {
      sub.textContent = `${bank.questions.length} 题`;
    }
  }

  function downloadJSON(obj, filename) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  /* =========================================================
     SHEET / THEME / INIT
     ========================================================= */
  function openSheet(html) {
    $('#sheetBody').innerHTML = html;
    $('#sheet').classList.remove('hidden');
  }

  function closeSheet() { $('#sheet').classList.add('hidden'); }

  /** 移动端抽屉：打开时显示遮罩，点击空白 / 选择导航后关闭 */
  function toggleDrawer(force) {
    const side = $('.sidebar');
    const scrim = $('#scrim');
    if (!side) return;
    const willOpen = typeof force === 'boolean' ? force : !side.classList.contains('open');
    side.classList.toggle('open', willOpen);
    if (scrim) scrim.classList.toggle('show', willOpen);
    document.body.style.overflow = willOpen ? 'hidden' : '';
  }

  /** 用自绘弹窗代替原生 confirm（原生会阻塞页面，样式也不统一） */
  function confirmSheet(opts) {
    return new Promise(resolve => {
      openSheet(`
        <h2>${esc(opts.title || '确认')}</h2>
        <p class="sub">${esc(opts.body || '')}</p>
        <div class="row" style="margin-top:16px">
          <button class="btn ${opts.danger ? 'danger' : 'primary'}" id="csOk">${esc(opts.ok || '确定')}</button>
          <button class="btn" id="csCancel">取消</button>
        </div>
      `);
      let done = false;
      const finish = (val) => {
        if (done) return;
        done = true;
        closeSheet();
        resolve(val);
      };
      $('#csOk').onclick = () => finish(true);
      $('#csCancel').onclick = () => finish(false);
      $('#sheet').onclick = (e) => { if (e.target.id === 'sheet') finish(false); };
    });
  }

  function applyTheme() {
    document.documentElement.dataset.theme = pref.theme === 'dark' ? 'dark' : 'light';
    const b = $('#btnTheme');
    if (b) b.textContent = pref.theme === 'dark' ? '☀ 浅色' : '🌗 深色';
  }

  function bindChrome() {
    $('#btnTheme').onclick = () => {
      pref.theme = pref.theme === 'dark' ? 'light' : 'dark';
      savePref(); applyTheme();
    };
    $('#sheetClose').onclick = closeSheet;
    $('#sheet').onclick = e => { if (e.target.id === 'sheet') closeSheet(); };
    $('#btnMenu').onclick = () => toggleDrawer();
    const scrim = $('#scrim');
    if (scrim) scrim.onclick = () => toggleDrawer(false);
    $('#btnHelp').onclick = () => {
      openSheet(`
        <h2>快捷键与设置</h2>
        <div class="rows">
          <div class="rowitem"><span class="rno">A B C D</span><span class="rtxt">选择选项</span></div>
          <div class="rowitem"><span class="rno">← →</span><span class="rtxt">上一题 / 下一题</span></div>
          <div class="rowitem"><span class="rno">空格</span><span class="rtxt">对答案</span></div>
          <div class="rowitem"><span class="rno">F</span><span class="rtxt">收藏 / 取消收藏</span></div>
          <div class="rowitem"><span class="rno">M</span><span class="rtxt">显示 / 隐藏资料文字</span></div>
          <div class="rowitem"><span class="rno">R</span><span class="rtxt">重做本题</span></div>
          <div class="rowitem"><span class="rno">T</span><span class="rtxt">暂停 / 继续计时</span></div>
        </div>
        <div class="hr"></div>
        <h3>设置</h3>
        <label class="row" style="margin-bottom:8px;cursor:pointer">
          <input type="checkbox" id="pfInstant" ${pref.instantJudge ? 'checked' : ''}>
          <span>选完即时判定（关闭后需手动点「对答案」）</span>
        </label>
        <label class="row" style="margin-bottom:8px;cursor:pointer">
          <input type="checkbox" id="pfAuto" ${pref.autoNext ? 'checked' : ''}>
          <span>答对后自动跳下一题</span>
        </label>
        <label class="row" style="cursor:pointer">
          <input type="checkbox" id="pfMat" ${pref.showMaterialText ? 'checked' : ''}>
          <span>默认展开资料 OCR 文字</span>
        </label>
        <p class="tiny" style="margin-top:14px">
          题目文字由 PDF 扫描件 OCR 生成，可能存在识别误差，每题均附原书截图，以截图为准。
          答案来自书末「参考答案」页。计时按套累计，可设置限时，时间到自动交卷。
        </p>
      `);
      setTimeout(() => {
        const a = $('#pfInstant'), b = $('#pfAuto'), c = $('#pfMat');
        if (a) a.onchange = () => { pref.instantJudge = a.checked; savePref(); };
        if (b) b.onchange = () => { pref.autoNext = b.checked; savePref(); };
        if (c) c.onchange = () => {
          pref.showMaterialText = c.checked; savePref();
          
        };
      }, 0);
    };
  }

  function bindKeys() {
    document.addEventListener('keydown', e => {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.metaKey || e.ctrlKey || e.altKey) return;
      const routeName = parseHash().parts[0] || 'home';
      const inDrill = routeName === 'drillrun';

      if (inDrill) {
        const k = e.key.toLowerCase();
        if (k === 'a' || k === 'b' || k === 'c' || k === 'd') {
          const btn = $(`.opt[data-letter="${k.toUpperCase()}"]`);
          if (btn && !btn.classList.contains('locked')) { btn.click(); e.preventDefault(); }
        } else if (e.key === 'ArrowLeft') {
          const b = $('#dPrev');
          if (b && !b.disabled) { b.click(); e.preventDefault(); }
        } else if (e.key === 'ArrowRight') {
          const b = $('#dNext');
          if (b && !b.disabled) { b.click(); e.preventDefault(); }
        } else if (e.key === ' ') {
          const b = $('#dCheck');
          if (b) { b.click(); e.preventDefault(); }
        } else if (k === 'f') {
          const b = $('#btnFav2') || $('#dFav');
          if (b) { b.click(); e.preventDefault(); }
        } else if (k === 'r') {
          const b = $('#dRetry');
          if (b) { b.click(); e.preventDefault(); }
        }
      }
    });
  }

  /* ---------------- boot ---------------- */
  async function boot() {
    applyTheme();
    bindChrome();
    bindKeys();

    route(['home'], viewHome);
    route(['wrong'], viewWrong);
    route(['fav'], viewFav);
    route(['search'], viewSearch);
    route(['stats'], viewStats);
    route(['news'], () => {
      setActiveNav('news');
      // 先立刻渲染已有数据，再强制拉最新（不用等）
      ZLFX_NEWS.viewNews();
      ZLFX_NEWS.refresh();
    });
    route(['shenlun'], () => { setActiveNav('shenlun'); ZLFX_SHENLUN.viewList(); });
    route(['cidian'], () => { setActiveNav('cidian'); ZLFX_CIDIAN.view(); });
    route(['fanwen'], () => { setActiveNav('fanwen'); ZLFX_FANWEN.view(); });
    route(['law'], () => { setActiveNav('law'); ZLFX_LAW.view(); });
    route(['papers'], () => { setActiveNav('papers'); ZLFX_PAPERS.view(); });
    route(['import'], viewImport);

    _syncBank().then(() => { render(); updateBadges(); });

    // ---- 分类真题（由 assets/zhenti.js 提供）----
    const ZH = window.ZLFX_ZHENTI;
    if (ZH) {
      route(['cats'], () => { setActiveNav('cats'); ZH.viewCats(); });
      route(['drillrun'], () => { setActiveNav('cats'); ZH.viewDrill(); });
    }

    window.addEventListener('hashchange', () => {
      render();
      toggleDrawer(false);
    });

    if (API) {
      const ok = await API.probe();
      if (ok && API.token) {
        try {
          await API.me();
          await syncWithServer().catch(() => null);
        } catch (e) {
          API.clearAuth();
        }
      }
    }

    updateUserChip();
    render();
    updateBadges();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();

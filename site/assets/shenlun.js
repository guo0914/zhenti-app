/* =========================================================
   申论 AI 批改 · 单页应用
   数据: window.__SHENLUN__          真题库
   API:  DeepSeek Chat API + Vision  批改引擎 + OCR
   功能: 文字输入 / 图片上传 / OCR 识别 / AI 批改
   ========================================================= */
(function () {
  'use strict';

  const SL = window.ZLFX_SHENLUN = {};
  // AI 请求走本地服务器代理（/api/ai/chat），
  // API Key 保存在服务器端，前端不再接触，开源也不会泄漏。
  const AI_ENDPOINT = '/api/ai/chat';
  const LS_KEY = 'zlfx.shenlun.apikey';
  const LS_ANSWERS = 'zlfx.shenlun.answers';
  const LS_GRADES = 'zlfx.shenlun.grades';

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function getApiKey() {
    try { return localStorage.getItem(LS_KEY) || ''; }
    catch (e) { return ''; }
  }

  /** 构造 AI 请求头：带上用户自己的 Key */
  function buildAIHeaders() {
    var h = { 'Content-Type': 'application/json' };
    var k = getApiKey().trim();
    if (k) h['X-User-Api-Key'] = k;
    return h;
  }

  /** 未填 Key 时抛出可读错误 */
  function requireApiKey() {
    var k = getApiKey().trim();
    if (!k) {
      throw new Error('请先在「⚙ 设置」里填入你的 DeepSeek API Key（platform.deepseek.com 免费申请）');
    }
    return k;
  }
  function setApiKey(k) { try { localStorage.setItem(LS_KEY, k); } catch (e) {} }

  function getAnswers() { try { return JSON.parse(localStorage.getItem(LS_ANSWERS) || '{}'); } catch (e) { return {}; } }
  function setAnswers(obj) { try { localStorage.setItem(LS_ANSWERS, JSON.stringify(obj)); } catch (e) {} }
  function saveAnswer(id, text) { const a = getAnswers(); a[id] = text; setAnswers(a); }

  function getGrades() { try { return JSON.parse(localStorage.getItem(LS_GRADES) || '{}'); } catch (e) { return {}; } }
  function setGrades(obj) { try { localStorage.setItem(LS_GRADES, JSON.stringify(obj)); } catch (e) {} }

  /* ----- 图片工具 ----- */
  function imgToBase64(file, maxW, maxH) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          let w = img.width, h = img.height;
          if (w > maxW) { h = h * maxW / w; w = maxW; }
          if (h > maxH) { w = w * maxH / h; h = maxH; }
          const cv = document.createElement('canvas');
          cv.width = w; cv.height = h;
          cv.getContext('2d').drawImage(img, 0, 0, w, h);
          resolve(cv.toDataURL('image/jpeg', 0.85));
        };
        img.onerror = reject;
        img.src = reader.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /* ═══════════════════════════════════
     真题列表
     ═══════════════════════════════════ */
  SL.viewList = function () {
    const all = window.__SHENLUN__ || [];
    const v = $('#view'); if (!v) return;
    const answers = getAnswers(), grades = getGrades();

    // 年份筛选
    let curYear = SL._filterYear || 'all';
    const years = Array.from(new Set(all.map(q => q.year))).sort((a, b) => b.localeCompare(a));
    const totalDone = all.filter(q => grades[q.id]).length;

    const data = curYear === 'all' ? all : all.filter(q => q.year === curYear);

    // 按试卷分组（保持原顺序）
    const papers = {};
    data.forEach(q => {
      const key = q.paper || (q.year + ' ' + q.exam);
      if (!papers[key]) papers[key] = [];
      papers[key].push(q);
    });
    const groups = Object.entries(papers);

    v.innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div><h1>申论练习</h1>
          <p class="sub">${all.length} 道真题 · 覆盖 2023—2026 年 · 完整给定资料 · AI 智能批改</p></div>
        <div class="row"><button class="btn sm" id="btnSlSettings">⚙ 设置</button></div>
      </div>
      <div class="row" style="gap:6px;flex-wrap:wrap;margin-bottom:14px">
        <button class="btn sm ${curYear === 'all' ? 'primary' : ''}" data-yr="all">全部 ${all.length}</button>
        ${years.map(y => {
          const n = all.filter(q => q.year === y).length;
          return `<button class="btn sm ${curYear === y ? 'primary' : ''}" data-yr="${y}">${y} <span class="tiny">${n}</span></button>`;
        }).join('')}
        <span class="tiny" style="margin-left:auto;align-self:center">累计已批改 ${totalDone}/${all.length} 题</span>
      </div>
      ${groups.length === 0 ? '<p class="tiny">该年份暂无题目</p>' : groups.map(([paper, qs]) => {
        const total = qs.reduce((s, q) => s + q.score, 0);
        const done = qs.filter(q => grades[q.id]).length;
        const sum = qs.reduce((s, q) => s + (grades[q.id] ? Number(grades[q.id].score) || 0 : 0), 0);
        return `
        <div style="margin-bottom:18px">
          <h2 style="font-size:15px;margin:0 0 8px 0;color:var(--text-2);display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            📄 ${esc(paper)}
            <span class="tiny" style="font-weight:400">${qs.length}题 · 满分${total}分 · 已批改${done}题${done ? ' · 得分' + sum : ''}</span>
          </h2>
          <div class="rows">${qs.map((q, i) => {
            const hasAnswer = answers[q.id], g = grades[q.id];
            let badge = g ? `<span class="pill ok">${g.score}/${q.score}分</span>` : hasAnswer ? `<span class="pill">待批改</span>` : `<span class="pill dim">未作答</span>`;
            return `<div class="rowitem" style="cursor:pointer" data-open="${q.id}">
              <span class="rno">第${i + 1}题</span>
              <div style="flex:1;min-width:0"><div class="rtxt" style="margin-bottom:2px">${esc(q.type)}：${esc(q.title.slice(0, 42))}…</div>
              <span class="tiny">${q.score}分 · ${q.wordLimit ? q.wordLimit[1] + '字以内' : ''} · 材料${q.materials.length}字</span></div>${badge}</div>`;
          }).join('')}</div></div>`;
      }).join('')}`;

    $$('[data-open]', v).forEach(el => el.onclick = () => SL.viewWrite(el.dataset.open));
    $$('[data-yr]', v).forEach(el => el.onclick = () => { SL._filterYear = el.dataset.yr; SL.viewList(); });
    const bs = $('#btnSlSettings', v); if (bs) bs.onclick = SL.showSettings;
  };

  /* ═══════════════════════════════════
     作答页面（含图片上传）
     ═══════════════════════════════════ */
  SL.viewWrite = function (id) {
    const data = window.__SHENLUN__ || [];
    const q = data.find(x => x.id === id);
    if (!q) { SL.viewList(); return; }

    const v = $('#view'); if (!v) return;
    const answers = getAnswers(), grades = getGrades();
    const prevAnswer = answers[id] || '', grade = grades[id];
    const isDazuowen = q.type === '文章写作（大作文）';
    const taH = isDazuowen ? 360 : 180;

    v.innerHTML = `
      <div class="spread" style="margin-bottom:14px">
        <div><h1>${esc(q.type)}</h1><p class="sub">${esc(q.paper || q.exam)} · ${q.score}分 · ${q.wordLimit ? '约 ' + q.wordLimit[1] + ' 字' : ''} · 材料${q.materials.length}字</p></div>
        <div class="row"><button class="btn sm" id="btnBack">&larr; 返回列表</button></div>
      </div>
      <div class="card pad" style="margin-bottom:14px;border-left:4px solid var(--brand)">
        <h3 style="margin-top:0">📋 题干</h3>
        <p style="white-space:pre-wrap;line-height:1.8;font-weight:500">${esc(q.title)}</p>
        <p class="tiny" style="white-space:pre-wrap;line-height:1.8;color:var(--brand);font-weight:500">${esc(q.requirements)}</p>
      </div>
      <div class="card pad" style="margin-bottom:14px">
        <div class="spread" style="margin-bottom:8px">
          <h3 style="margin:0">📄 给定资料</h3>
          <div class="row" style="gap:6px">
            <button class="btn sm" id="btnMatSearch">🔍 找关键句</button>
            <button class="btn sm" id="btnMatAll">展开/收起全文</button>
          </div>
        </div>
        <div id="slMatSearchBar" style="display:none;margin-bottom:8px">
          <input id="slMatSearchInput" placeholder="输入关键词，高亮定位资料中的句子…" style="width:100%;box-sizing:border-box;padding:8px 12px;border:1px solid var(--line);border-radius:6px;font-size:13px">
          <div id="slMatSearchInfo" class="tiny" style="margin-top:4px"></div>
        </div>
        <div id="slMatBody" style="max-height:340px;overflow:auto;white-space:pre-wrap;line-height:1.9;font-size:14px;padding:10px;background:var(--bg-0);border-radius:6px;border:1px solid var(--line)">${esc(q.materials)}</div>
      </div>
      <div class="card pad" style="margin-bottom:14px">
        <h3 style="margin-top:0">📝 我的作答</h3>
        <textarea id="slAnswer" placeholder="在此作答…或上传手写图片自动识别" style="width:100%;height:${taH}px;box-sizing:border-box;font-size:14px;line-height:1.8;padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--bg-1);color:var(--text-1);font-family:inherit;resize:vertical">${esc(prevAnswer)}</textarea>
        <div id="slUploadArea" style="margin-top:10px">
          <div id="slUploadZone" style="border:2px dashed var(--line);border-radius:8px;padding:16px;text-align:center;cursor:pointer;transition:border-color .2s;background:var(--bg-0)">
            <div style="font-size:28px;margin-bottom:4px">📸</div>
            <div style="font-size:13px;color:var(--text-2)">上传手写答卷 · 拖拽 / 点击 / 粘贴图片</div>
            <div class="tiny" style="margin-top:4px">支持 JPG/PNG，自动压缩识别，多张可上传</div>
            <input type="file" id="slFileInput" accept="image/*" multiple style="display:none">
          </div>
          <div id="slPreviewBox" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"></div>
        </div>
        <div class="row" style="margin-top:10px;gap:8px;flex-wrap:wrap">
          <button class="btn primary" id="btnSubmit">🤖 AI 批改</button>
          <button class="btn" id="btnOcr">📷 OCR 识别图片</button>
          <button class="btn" id="btnSaveDraft">💾 保存草稿</button>
          <span class="tiny" id="slWordCount" style="margin-left:auto">0 / ${q.wordLimit ? q.wordLimit[1] : '—'} 字</span>
        </div>
      </div>
      ${grade ? `<div class="card pad" style="margin-bottom:14px;border-left:4px solid var(--brand)">
        <h3 style="margin-top:0">📊 上次批改结果 <span class="pill ok">${grade.score} 分</span></h3>
        <div style="white-space:pre-wrap;line-height:1.8;font-size:14px">${esc(grade.feedback || '')}</div>
        ${grade.tokens ? `<p class="tiny" style="margin-top:8px">消耗 ${grade.tokens} tokens · ${grade.time || ''}</p>` : ''}
      </div>` : ''}`;

    // ----- 资料搜索 / 展开收起 -----
    const matBody = $('#slMatBody', v);
    const searchBar = $('#slMatSearchBar', v);
    let matExpanded = false;
    let rawMatHtml = esc(q.materials);

    $('#btnMatAll', v).onclick = () => {
      matExpanded = !matExpanded;
      matBody.style.maxHeight = matExpanded ? 'none' : '340px';
    };
    $('#btnMatSearch', v).onclick = () => {
      const show = searchBar.style.display === 'none';
      searchBar.style.display = show ? 'block' : 'none';
      if (show) $('#slMatSearchInput', v).focus();
    };

    let searchTimer = null;
    $('#slMatSearchInput', v).addEventListener('input', (e) => {
      clearTimeout(searchTimer);
      const kw = e.target.value.trim();
      const info = $('#slMatSearchInfo', v);
      if (!kw) { matBody.innerHTML = rawMatHtml; info.textContent = ''; return; }
      searchTimer = setTimeout(() => {
        // 按句子切分，标出含关键词的句子
        const parts = q.materials.split(/(?<=[。！？\n])/);
        let hit = 0;
        const out = parts.map(s => {
          if (s.includes(kw)) {
            hit++;
            return `<mark style="background:#fde68a;color:#000;padding:0 2px">${esc(s)}</mark>`;
          }
          return esc(s);
        }).join('');
        matBody.innerHTML = out;
        info.textContent = hit ? `找到 ${hit} 处，已高亮` : '未找到该关键词';
        matBody.style.maxHeight = 'none';
        const first = matBody.querySelector('mark');
        if (first) first.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }, 250);
    });

    // ----- 图片上传逻辑 -----
    const uploadedPics = [];
    const previewBox = $('#slPreviewBox', v);
    const fileInput = $('#slFileInput', v);
    const uploadZone = $('#slUploadZone', v);

    function addPic(dataUrl, name) {
      uploadedPics.push(dataUrl);
      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:relative;width:80px;height:80px;border-radius:6px;overflow:hidden;border:1px solid var(--line);flex-shrink:0';
      wrap.innerHTML = `<img src="${dataUrl}" style="width:100%;height:100%;object-fit:cover">
        <button class="sl-pic-del" style="position:absolute;top:2px;right:2px;width:20px;height:20px;border-radius:50%;border:none;background:rgba(0,0,0,.6);color:#fff;font-size:12px;cursor:pointer;line-height:1">×</button>`;
      wrap.querySelector('.sl-pic-del').onclick = (e) => {
        e.stopPropagation();
        const idx = uploadedPics.indexOf(dataUrl);
        if (idx >= 0) uploadedPics.splice(idx, 1);
        wrap.remove();
        if (!uploadedPics.length) previewBox.innerHTML = '';
      };
      previewBox.appendChild(wrap);
    }

    // 点击上传
    uploadZone.onclick = () => fileInput.click();
    fileInput.onchange = () => {
      Array.from(fileInput.files).forEach(f => {
        imgToBase64(f, 1024, 1536).then(b64 => addPic(b64, f.name)).catch(() => {});
      });
      fileInput.value = '';
    };
    // 拖拽
    uploadZone.ondragover = (e) => { e.preventDefault(); uploadZone.style.borderColor = 'var(--brand)'; };
    uploadZone.ondragleave = () => { uploadZone.style.borderColor = ''; };
    uploadZone.ondrop = (e) => {
      e.preventDefault(); uploadZone.style.borderColor = '';
      Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/')).forEach(f => {
        imgToBase64(f, 1024, 1536).then(b64 => addPic(b64, f.name)).catch(() => {});
      });
    };
    // 粘贴图片
    document.addEventListener('paste', function onPaste(e) {
      if (!v.contains(document.activeElement)) return;
      const items = e.clipboardData && e.clipboardData.items;
      if (!items) return;
      Array.from(items).forEach(item => {
        if (item.type.startsWith('image/')) {
          const blob = item.getAsFile();
          imgToBase64(blob, 1024, 1536).then(b64 => addPic(b64, '剪贴板')).catch(() => {});
        }
      });
    });

    // ----- 字数统计 -----
    const ta = $('#slAnswer', v);
    const wc = $('#slWordCount', v);
    function updateCount() {
      const text = ta ? ta.value : '';
      const len = text.replace(/\s/g, '').length;
      const max = q.wordLimit ? q.wordLimit[1] : Infinity;
      if (wc) { wc.textContent = len + ' / ' + (q.wordLimit ? q.wordLimit[1] : '—') + ' 字'; wc.style.color = len > max ? 'var(--danger)' : ''; }
    }
    if (ta) { ta.addEventListener('input', updateCount); updateCount(); }

    // ----- 按钮事件 -----
    $('#btnBack', v).onclick = () => SL.viewList();
    $('#btnSaveDraft', v).onclick = () => { if (ta) saveAnswer(id, ta.value); window.toast ? window.toast('草稿已保存') : alert('草稿已保存'); };

    // OCR 识别
    $('#btnOcr', v).onclick = async () => {
      if (!uploadedPics.length) { alert('请先上传手写答卷图片'); return; }
      const btn = $('#btnOcr', v);
      btn.disabled = true; btn.textContent = '⏳ 识别中…';
      try {
        const ocrText = await runOCR(q, uploadedPics);
        if (ta) {
          const existing = ta.value.trim();
          ta.value = existing ? existing + '\n\n[OCR 识别内容]\n' + ocrText : ocrText;
          updateCount(); saveAnswer(id, ta.value);
        }
        window.toast ? window.toast('OCR 识别完成，请核对并修改') : alert('识别完成，请核对');
      } catch (e) {
        alert('OCR 识别失败：' + (e.message || '网络错误'));
      }
      btn.disabled = false; btn.textContent = '📷 OCR 识别图片';
    };

    // AI 批改
    $('#btnSubmit', v).onclick = async () => {
      const answerText = ta ? ta.value.trim() : '';
      if (!answerText) { alert('请先作答或上传图片'); return; }
      const maxWords = q.wordLimit ? q.wordLimit[1] : Infinity;
      const wordCount = answerText.replace(/\s/g, '').length;
      if (wordCount > maxWords && q.type !== '文章写作（大作文）') {
        alert(`字数超出要求（${wordCount}/${maxWords}），请精简后再提交`); return;
      }
      saveAnswer(id, answerText);
      const btn = $('#btnSubmit', v);
      btn.disabled = true; btn.textContent = '⏳ AI 批改中…';
      try {
        const result = await gradeEssay(q, answerText, uploadedPics);
        const grades = getGrades(); grades[id] = result; setGrades(grades);
        SL.viewWrite(id);
      } catch (e) {
        alert('批改失败：' + (e.message || '网络错误'));
        btn.disabled = false; btn.textContent = '🤖 AI 批改';
      }
    };
  };

  /* ═══════════════════════════════════
     OCR —— 图片文字识别
     ═══════════════════════════════════ */
  async function runOCR(q, pics) {
    requireApiKey();   // 未填 Key 时报错

    const imageContents = pics.map(b64 => ({
      type: 'image_url',
      image_url: { url: b64, detail: 'high' }
    }));

    const resp = await fetch(AI_ENDPOINT, {
      method: 'POST',
      headers: buildAIHeaders(),
      body: JSON.stringify({
        model: 'deepseek-chat',
        messages: [{
          role: 'user',
          content: [
            { type: 'text', text: `请将以下手写申论答卷图片中的文字逐字识别出来。

【题目】${q.title}
【作答要求】${q.requirements}

要求：
1. 逐字识别，不要概括、不要润色、不要添加任何评价
2. 保留原文的段落结构和标点
3. 字迹模糊处标注 [?]
4. 只输出识别出的答卷内容，不要加任何前缀说明` },
            ...imageContents
          ]
        }],
        temperature: 0.1,
        max_tokens: 3000
      })
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error?.message || `OCR 错误 ${resp.status}`);
    }
    const data = await resp.json();
    return (data.choices?.[0]?.message?.content || '').trim();
  }

  /* ═══════════════════════════════════
     AI 批改引擎（含图片）
     ═══════════════════════════════════ */
  async function gradeEssay(q, answerText, pics) {
    requireApiKey();   // 未填 Key 时报错

    const promptText = buildPrompt(q, answerText);
    let userContent;
    if (pics && pics.length) {
      userContent = [
        { type: 'text', text: promptText },
        { type: 'text', text: '\n\n【附：考生手写答卷原件（供参考卷面）】' },
        ...pics.map(b64 => ({ type: 'image_url', image_url: { url: b64, detail: 'low' } }))
      ];
    } else {
      userContent = promptText;
    }

    const resp = await fetch(AI_ENDPOINT, {
      method: 'POST',
      headers: buildAIHeaders(),
      body: JSON.stringify({
        model: 'deepseek-chat',
        messages: [
          { role: 'system', content: '你是一位资深的公务员考试申论阅卷专家，精通申论评分标准和答题技巧。请严格按照评分标准批改，给出具体、有建设性的改进建议。' },
          { role: 'user', content: userContent }
        ],
        temperature: 0.3,
        max_tokens: 4096
      })
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error?.message || `API 错误 ${resp.status}`);
    }

    const data = await resp.json();
    const content = data.choices?.[0]?.message?.content || '';
    const tokens = data.usage?.total_tokens || 0;
    const scoreMatch = content.match(/(?:总分|综合得分|得分)[：:]\s*(\d+)/) || content.match(/[（(](\d+)\s*分[)）]/);
    return { score: scoreMatch ? parseInt(scoreMatch[1]) : 0, feedback: content, tokens, time: new Date().toLocaleString('zh-CN') };
  }

  function buildPrompt(q, answerText) {
    const fullScore = q.score || 0;
    const wordInfo = q.wordLimit ? `要求 ${q.wordLimit[0]}-${q.wordLimit[1]} 字` : '';
    // 材料全文传入（申论材料是评分核心依据，不可截断）
    const mats = q.materials || '';
    let p = `请批改以下申论${q.type}题目的作答。\n\n`;
    p += `【题干】${q.title}\n\n【作答要求】${q.requirements}\n\n【满分】${fullScore}分 ${wordInfo}\n\n`;
    p += `【给定资料（全文）】\n${mats}\n\n`;
    p += `【考生作答】\n${answerText}\n\n`;
    p += `【评分参考要点】\n${(q.refPoints || []).map((pt, i) => `${i + 1}. ${pt}`).join('\n')}\n\n`;
    if (q.refAnswer && q.type !== '文章写作（大作文）') p += `【参考答案】\n${q.refAnswer}\n\n`;
    p += `请严格按以下要求批改：\n`;
    p += `1. 逐条核对考生作答是否覆盖"评分参考要点"，明确指出漏掉哪些要点、哪些表述不准确；\n`;
    p += `2. 核对字数是否符合"作答要求"，超字数或严重不足要指出；\n`;
    p += `3. 检查是否紧密结合给定资料，有无脱离材料空谈；\n`;
    p += `4. 公文写作题须检查格式要素（标题、称谓、正文层次、落款等）是否齐全规范；\n\n`;
    p += `输出格式：\n\n一、总体评价（2-3句话概括作答水平）\n\n`;
    p += `二、分项评分（每项给出具体分数和建议分值占比）\n  · 要点覆盖（对照参考要点逐条核对）\n  · 逻辑结构\n  · 语言表达\n  · ${q.type === '文章写作（大作文）' ? '立意深度（是否切题、见解是否深刻）' : '格式规范（是否符合题型要求）'}\n\n`;
    p += `三、具体改进建议（逐条指出不足和优化方向，给出改写示范）\n\n四、参考范文要点提示（高分作答应包含的核心内容）\n\n最后请在单独一行写明：总分：XX分`;
    return p;
  }

  /* ═══════════════════════════════════
     设置弹窗
     ═══════════════════════════════════ */
  SL.showSettings = function () {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;z-index:10000;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = `<div class="card pad" style="max-width:460px;width:90%;max-height:80vh;overflow:auto">
      <h2 style="margin-top:0">⚙ 申论批改设置</h2>
      <label style="display:block;margin-bottom:4px;font-weight:600">DeepSeek API Key</label>
      <input type="password" id="slApiKey"
        style="width:100%;box-sizing:border-box;padding:8px 10px;border:1.5px solid var(--line,#c5cddd);border-radius:8px;font-size:13px"
        value="${esc(getApiKey())}" placeholder="sk-xxxxxxxxxxxxxxxx">
      <p class="tiny" style="margin:6px 0 4px 0">
        在 <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener">platform.deepseek.com</a>
        申请（约 ¥1 起充）。Key 只保存在你自己的设备上，不会上传。
      </p>
      <p class="tiny" style="margin:0 0 12px 0;color:var(--text-3,#8b94a8)">
        OCR 识别与批改会消耗你账户的 token。
      </p>
      <div class="row" style="gap:8px">
        <button class="btn primary" id="btnSaveSettings">保存</button>
        <button class="btn" id="btnCloseSettings">取消</button>
      </div></div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#btnSaveSettings').onclick = () => {
      var v = (overlay.querySelector('#slApiKey').value || '').trim();
      if (v && !/^[\w-]{8,}$/.test(v)) {
        alert('Key 格式不正确，应以 sk- 开头且无空格');
        return;
      }
      setApiKey(v);
      overlay.remove();
      window.toast ? window.toast(v ? 'API Key 已保存' : '已清空 API Key') : alert('已保存');
    };
    overlay.querySelector('#btnCloseSettings').onclick = () => overlay.remove();
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  };

})();
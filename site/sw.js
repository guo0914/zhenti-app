/* ===== 分类真题刷题 · Service Worker =====
 * 策略：
 *   - HTML / JS / CSS：Network First（每次都问服务器，失败才用缓存）
 *   - 数据 JSON：Network First + 4 秒超时回退缓存
 *   - 图片 / 字体：Cache First（体积大、变动少）
 *   - /api/：直连网络，永不缓存
 *
 * 注意 0：数据 JSON 绝不能走 Cache First。
 * 早期版本对 JSON 用 Cache First，而前端请求 URL 上写死了 ?v=17，
 * 于是旧 JSON 进缓存后 URL 永不变 → 永远命中旧数据，
 * 表现为「材料张冠李戴」「改了数据但手机端看不到」。
 *
 * 注意 1：绝不在 install 阶段 addAll 预缓存代码文件。
 * 早期版本用 addAll 缓存了旧 CSS/JS，一旦文件更新而缓存名没变，
 * 就会长期用旧文件，表现为「样式丢失 / 布局崩坏」。
 *
 * 注意 2：CACHE 名必须固定，不能带 Date.now()。
 * 早期版本写成 'zlfx-v3.6-' + Date.now()，导致每次 SW 安装都
 * 生成一个新缓存名，旧缓存永远删不掉，多个缓存互相污染。
 */

const CACHE = 'zlfx-data-v9.5';   // 固定名，只存数据/图片
const CACHE_PREFIX = 'zlfx-';     // 清理时按前缀删所有旧缓存

// 数据 JSON 走 Network First 时的网络等待上限（毫秒）。
// 超时立刻回退缓存，避免弱网下白屏。
const DATA_NET_TIMEOUT = 4000;

// 体积大且变动少的数据文件（可以预缓存）
const PRE_CACHE_DATA = [
  'data/zt-papers.js',
  'data/zt-guokao-papers.js',
  'data/zt/guokao.json',
];

self.addEventListener('install', (e) => {
  // 只预缓存数据文件，代码/HTML 一律不预缓存
  e.waitUntil(
    caches.open(CACHE)
      .then(c => Promise.all(
        PRE_CACHE_DATA.map(u => c.add(u).catch(() => {}))
      ))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k.startsWith(CACHE_PREFIX) && k !== CACHE)
            .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);

  // 实时接口：直连
  if (url.pathname.indexOf('/api/') === 0) {
    e.respondWith(fetch(e.request));
    return;
  }

  // 自愈脚本：永不拦截、永不缓存。它是修复死锁的最后一道门，
  // 一旦被旧 SW 缓存住就彻底失效，所以这里必须完全放行。
  if (url.pathname.indexOf('selfheal.js') >= 0) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .catch(() => caches.match(e.request).then(hit => hit || Response.error()))
    );
    return;
  }

  // 代码与 HTML：Network First，且不把响应写回缓存以外的旧副本
  const isCode = /\.(html|js|css|webmanifest)$/i.test(url.pathname) ||
                 url.pathname === '/' ||
                 url.pathname.endsWith('index.html');

  if (isCode) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' })
        .then(res => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(e.request).then(hit => hit || Response.error()))
    );
    return;
  }

  // 数据 JSON：Network First + 超时回退缓存。
  // 早期这里是 Cache First，配合 URL 上写死的 ?v=17，
  // 一旦旧 JSON 进了缓存就永远命中旧数据（表现为「题目材料张冠李戴、
  // 改了数据手机端永远看不到」）。数据体积不大，每次都问服务器是值得的。
  const isData = /\.json$/i.test(url.pathname);

  if (isData) {
    e.respondWith(
      Promise.race([
        fetch(e.request, { cache: 'no-store' }).then(res => {
          if (res && res.ok) {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone)).catch(() => {});
          }
          return res;
        }),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('data-timeout')), DATA_NET_TIMEOUT)
        ),
      ]).catch(() =>
        caches.match(e.request, { ignoreSearch: true }).then(hit => hit || Response.error())
      )
    );
    return;
  }

  // 其它（图片、字体）：Cache First，回退网络
  e.respondWith(
    caches.match(e.request).then(hit => {
      if (hit) return hit;
      return fetch(e.request).then(res => {
        if (res.ok && res.type === 'basic') {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone)).catch(() => {});
        }
        return res;
      });
    })
  );
});

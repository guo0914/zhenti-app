#!/usr/bin/env python3
"""时政资讯抓取核心模块 —— 可被 fetch_news.py CLI 和 serve.py API 共用。

对外接口：
    fetch_all(sources=None, fetch_content=False, max_per=30) -> dict
        返回 {updated, total, sources, topics, articles}
"""

import json, re, time, random
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

# ═══════════════ 源配置 ═══════════════
SOURCES = [
    # 求是网
    {"id": "qsyw", "src": "求是网", "name": "要闻", "mode": "qs",
     "url": "https://www.qstheory.cn/qsyw/index.htm"},
    {"id": "qswp", "src": "求是网", "name": "评论", "mode": "qs",
     "url": "https://www.qstheory.cn/qswp.htm"},
    {"id": "qszz", "src": "求是网", "name": "政治", "mode": "qs",
     "url": "https://www.qstheory.cn/politics/index.htm"},
    {"id": "qsjj", "src": "求是网", "name": "经济", "mode": "qs",
     "url": "https://www.qstheory.cn/economy/index.htm"},
    {"id": "qsdj", "src": "求是网", "name": "党建", "mode": "qs",
     "url": "https://www.qstheory.cn/cpc/index.htm"},
    {"id": "qswh", "src": "求是网", "name": "文化", "mode": "qs",
     "url": "https://www.qstheory.cn/culture/index.htm"},
    {"id": "qsgj", "src": "求是网", "name": "国际", "mode": "qs",
     "url": "https://www.qstheory.cn/international/index.htm"},
    {"id": "qssh", "src": "求是网", "name": "社会", "mode": "qs",
     "url": "https://www.qstheory.cn/society/index.htm"},
    {"id": "qskj", "src": "求是网", "name": "科技", "mode": "qs",
     "url": "https://www.qstheory.cn/science/index.htm"},
    # 央视网（JSONP）
    {"id": "cctv-news", "src": "央视网", "name": "要闻", "mode": "jsonp",
     "url": "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/news_1.jsonp?cb=news"},
    {"id": "cctv-cn", "src": "央视网", "name": "中国", "mode": "jsonp",
     "url": "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/china_1.jsonp?cb=china"},
    {"id": "cctv-world", "src": "央视网", "name": "国际", "mode": "jsonp",
     "url": "https://news.cctv.com/2019/07/gaiban/cmsdatainterface/page/world_1.jsonp?cb=world"},
    # 其他
    {"id": "youth", "src": "中国青年网", "name": "国内", "mode": "date",
     "url": "http://news.youth.cn/gn/"},
    {"id": "cpc", "src": "中国共产党新闻网", "name": "要闻", "mode": "date",
     "url": "http://cpc.people.com.cn/"},
    {"id": "opinion", "src": "人民网", "name": "评论", "mode": "date",
     "url": "http://opinion.people.com.cn/"},
    {"id": "theory", "src": "人民网", "name": "理论", "mode": "date",
     "url": "http://theory.people.com.cn/"},
]

TOPICS = [
    ("中国式现代化", ["中国式现代化", "高质量发展", "现代化", "新发展格局", "十五五", "规划"]),
    ("新质生产力", ["新质生产力", "科技创新", "人工智能", "算力", "产业升级", "未来产业", "数字经济", "科技成果", "智能"]),
    ("文化自信", ["文化", "文明", "文物", "非遗", "传承", "文艺", "文旅"]),
    ("民生保障", ["民生", "就业", "养老", "教育", "医疗", "社保", "住房", "收入", "医保", "托育"]),
    ("生态文明", ["生态", "绿色", "碳", "环保", "污染防治", "绿水青山", "减排", "环境"]),
    ("党的建设", ["党建", "从严治党", "巡视", "党风", "党纪", "自我革命", "八项规定", "党组织"]),
    ("乡村振兴", ["乡村", "三农", "农业", "农村", "粮食", "耕地", "脱贫"]),
    ("改革开放", ["改革", "开放", "营商环境", "市场", "民营经济", "统一大市场", "自贸"]),
    ("大国外交", ["外交", "国际合作", "全球治理", "一带一路", "命运共同体", "联合国", "论坛"]),
    ("法治建设", ["法治", "依法", "法律", "立法", "执法", "司法", "条例"]),
    ("基层治理", ["基层", "治理", "社区", "网格", "群众", "服务"]),
    ("安全发展", ["安全", "应急", "防灾", "救灾", "抗震", "能源安全", "生产安全"]),
]

BAD_EXT = (".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
           ".pdf", ".zip", ".rar", ".mp4", ".mp3", ".woff", ".ttf", ".webp")
BAD_PATH = ("/img/", "/images/", "/css/", "/js/", "/style/", "/static/",
            "/uploadfiles/", "/favicon", "/ad/", "/ads/", "/photo/")

_TOPIC_KW = [(t, kws) for t, kws in TOPICS]


def detect_topics(title, content=""):
    text = title + " " + content
    return [t for t, kws in _TOPIC_KW if any(k in text for k in kws)]


# ═══════════════ HTTP ═══════════════
def fetch_html(url, timeout=12):
    req = Request(url, headers={
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gb2312", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._cur = None
        self._buf = []
        self._seen = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href and not href.startswith(("javascript:", "#", "mailto:")):
                self._cur = href
                self._buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self._cur is not None:
            title = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if 8 <= len(title) <= 100 and re.search(r"[\u4e00-\u9fff]{8,}", title):
                if self._cur not in self._seen:
                    self._seen.add(self._cur)
                    self.links.append((self._cur, title))
            self._cur = None
            self._buf = []

    def handle_data(self, data):
        if self._cur is not None:
            self._buf.append(data)


class ContentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._in = False
        self._skip = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = (d.get("class", "") + " " + d.get("id", "")).lower()
        if tag in ("div", "article", "section") and any(
                k in cls for k in ("content", "article", "text", "detail", "main", "body")):
            if not self._in:
                self._in = True
                self._depth = 0
        if self._in:
            if tag in ("script", "style", "nav", "footer", "header", "aside"):
                self._skip = True
            self._depth += 1

    def handle_endtag(self, tag):
        if self._in:
            self._depth -= 1
            if self._depth <= 0:
                self._in = False
            if self._skip and tag in ("script", "style", "nav", "footer", "header", "aside"):
                self._skip = False

    def handle_data(self, data):
        if self._in and not self._skip:
            t = data.strip()
            if len(t) > 1:
                self.parts.append(t)


def parse_date(url):
    for pat in (r"/(\d{8})/", r"/(\d{4})/(\d{2})(\d{2})/", r"/(\d{4})/(\d{2})/(\d{2})/",
                r"(\d{8})_", r"/t(\d{8})", r"/(\d{4})(\d{2})/"):
        m = re.search(pat, url)
        if m:
            s = "".join(m.groups())
            if len(s) == 6:
                s += "01"
            if len(s) >= 8:
                return s[:8]
    return ""


def is_article_url(url):
    low = url.lower()
    base = low.split("?")[0]
    if base.endswith(BAD_EXT):
        return False
    if any(p in low for p in BAD_PATH):
        return False
    return bool(re.search(r"\.(html?|shtml)$", base))


def normalize(href, base_url):
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base_url, href)


# ═══════════════ 抓取 ═══════════════
def fetch_jsonp(cfg, max_per):
    try:
        raw = fetch_html(cfg["url"])
    except Exception:
        return []
    m = re.search(r"\((\{.*\})\)\s*;?\s*$", raw, re.S)
    try:
        data = json.loads(m.group(1) if m else raw)
    except Exception:
        return []

    out = []
    for it in ((data.get("data") or {}).get("list") or [])[:max_per]:
        title = re.sub(r"\s+", " ", (it.get("title") or "").strip())
        url = (it.get("url") or "").strip()
        if not title or not url:
            continue
        d = (it.get("focus_date") or "")[:10].replace("-", "")
        if len(d) != 8:
            d = parse_date(url)
        if not d or not d.startswith("20"):
            continue
        brief = (it.get("brief") or "").strip()
        item = {
            "title": title,
            "url": normalize(url, cfg["url"]),
            "date": d,
            "source": cfg["src"],
            "channel": cfg["name"],
            "topics": detect_topics(title, brief),
        }
        if brief:
            item["content"] = brief[:400] + ("…" if len(brief) > 400 else "")
        out.append(item)
    return out


def fetch_source(cfg, max_per):
    if cfg.get("mode") == "jsonp":
        return fetch_jsonp(cfg, max_per)
    try:
        html = fetch_html(cfg["url"])
    except Exception:
        return []

    p = LinkParser()
    try:
        p.feed(html)
    except Exception:
        pass

    out, seen = [], set()
    for href, title in p.links:
        if cfg["mode"] == "qs":
            if not re.match(r"^(\.\./)?\d{8}/[a-f0-9]+/c\.html$", href):
                continue
        else:
            if not is_article_url(normalize(href, cfg["url"])):
                continue

        full = normalize(href, cfg["url"])
        d = parse_date(full)
        if not d or len(d) != 8 or not d.startswith("20") or d < "20230101":
            continue
        if title in seen:
            continue
        if any(x in title for x in ("查看更多", "下一页", "上一页", "返回首页", "网站地图", "点击查看")):
            continue

        seen.add(title)
        out.append({
            "title": title,
            "url": full,
            "date": d,
            "source": cfg["src"],
            "channel": cfg["name"],
            "topics": detect_topics(title),
        })
        if len(out) >= max_per:
            break
    return out


def fetch_content(art, limit=400, timeout=10):
    try:
        html = fetch_html(art["url"], timeout=timeout)
    except Exception:
        return ""
    p = ContentParser()
    try:
        p.feed(html)
    except Exception:
        pass
    text = re.sub(r"\s{2,}", " ", "".join(p.parts)).strip()
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


# ═══════════════ 主接口 ═══════════════
def fetch_all(sources=None, fetch_content_flag=False, max_per=30,
              content_limit=0, deadline=None, on_progress=None):
    """抓取全部源并返回聚合数据。

    deadline: time.time() 时间戳；超时后停止抓取（用于 API 快速返回）
    on_progress: 回调 (source_name, count) 
    """
    started = time.time()
    picked = [s for s in SOURCES if not sources or s["id"] in sources
              or s["src"] in sources]

    all_arts = []
    for cfg in picked:
        if deadline and time.time() > deadline:
            break
        arts = fetch_source(cfg, max_per)
        all_arts.extend(arts)
        if on_progress:
            on_progress(cfg["src"] + "·" + cfg["name"], len(arts))
        time.sleep(0.12)

    # 标题去重
    seen, dedup = set(), []
    for a in all_arts:
        k = a["title"][:30]
        if k in seen:
            continue
        seen.add(k)
        dedup.append(a)
    all_arts = dedup

    # 正文
    if fetch_content_flag:
        for a in all_arts:
            if deadline and time.time() > deadline:
                break
            c = fetch_content(a, limit=content_limit or 400)
            if c:
                a["content"] = c
                a["topics"] = detect_topics(a["title"], c)
            time.sleep(0.08)

    all_arts.sort(key=lambda x: x["date"], reverse=True)

    topic_count, src_count = {}, {}
    for a in all_arts:
        for t in a.get("topics", []):
            topic_count[t] = topic_count.get(t, 0) + 1
        src_count[a["source"]] = src_count.get(a["source"], 0) + 1

    return {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(all_arts),
        "elapsed": round(time.time() - started, 1),
        "sources": [{"name": k, "count": v} for k, v in
                    sorted(src_count.items(), key=lambda x: -x[1])],
        "topics": [{"name": k, "count": v} for k, v in
                   sorted(topic_count.items(), key=lambda x: -x[1])],
        "articles": all_arts,
    }

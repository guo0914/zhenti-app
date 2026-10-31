#!/usr/bin/env python3
"""抓取优秀时评/申论范文，生成 site/data/fanwen-mined.js

来源（实测可用）：
  求是网 8 个栏目（各栏目约 50 篇，合计 ~400 篇）
    网评 / 政治 / 经济 / 党建 / 文化 / 国际 / 社会 / 科技
  人民网 3 个栏目
    人民时评 / 人民网评 / 人民论坛

筛选：正文 >= --min-words 字（默认 700）

用法：
  python scripts/fetch_fanwen.py                    # 默认 200 篇
  python scripts/fetch_fanwen.py --max 300
  python scripts/fetch_fanwen.py --min-words 900    # 只要长文
"""

import json, os, re, sys, io, time
from datetime import datetime
from urllib.request import Request, urlopen
from html.parser import HTMLParser

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "https://www.qstheory.cn"
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "site", "data", "fanwen-mined.js")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

# ── 求是网栏目（mode=qs，URL 形如 /YYYYMMDD/hash/c.html）──
QS_CHANNELS = [
    ("求是网 · 网评", "/qswp.htm"),
    ("求是网 · 政治", "/politics/index.htm"),
    ("求是网 · 经济", "/economy/index.htm"),
    ("求是网 · 党建", "/cpc/index.htm"),
    ("求是网 · 文化", "/culture/index.htm"),
    ("求是网 · 国际", "/international/index.htm"),
    ("求是网 · 社会", "/society/index.htm"),
    ("求是网 · 科技", "/science/index.htm"),
]

# ── 人民网栏目（mode=people，URL 形如 /n1/YYYY/MMDD/cXXXXXX-NNNNNNNN.html）──
PEOPLE_CHANNELS = [
    ("人民时评", "http://opinion.people.com.cn/GB/223228/index.html"),
    ("人民网评", "http://opinion.people.com.cn/GB/8213/49160/49219/index.html"),
    ("人民论坛", "http://theory.people.com.cn/"),
]

TOPICS = [
    ("中国式现代化", ["中国式现代化", "高质量发展", "现代化", "新发展格局", "十五五"]),
    ("新质生产力", ["新质生产力", "科技创新", "人工智能", "算力", "产业升级", "数字经济", "基础研究"]),
    ("乡村振兴", ["乡村", "三农", "农业", "农村", "粮食", "耕地", "脱贫"]),
    ("生态文明", ["生态", "绿色", "碳", "环保", "绿水青山", "污染防治"]),
    ("民生保障", ["民生", "就业", "养老", "教育", "医疗", "社保", "住房"]),
    ("文化自信", ["文化", "文明", "文物", "非遗", "传承", "文艺"]),
    ("党的建设", ["党建", "从严治党", "巡视", "党风", "党纪", "自我革命"]),
    ("改革开放", ["改革", "开放", "营商环境", "市场", "民营经济"]),
    ("大国外交", ["外交", "全球治理", "一带一路", "命运共同体", "联合国", "中美", "国际"]),
    ("法治建设", ["法治", "依法", "法律", "立法", "执法", "司法"]),
    ("基层治理", ["基层", "治理", "社区", "网格", "群众"]),
    ("长征精神", ["长征", "红军", "革命", "初心", "使命"]),
    ("青年成长", ["青年", "青春", "学生", "成长", "担当"]),
    ("安全发展", ["安全", "应急", "防灾", "救灾", "能源安全"]),
    ("经济发展", ["经济", "增速", "消费", "投资", "金融", "贸易", "产业"]),
]


def detect_topics(text):
    return [t for t, kws in TOPICS if any(k in text for k in kws)]


def fetch_html(url, timeout=15):
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": url,
    })
    with urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "gb2312", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def clean_text(t):
    t = re.sub(r"<[^>]+>", "", t)
    for a, b in [("&emsp;", ""), ("&nbsp;", " "), ("&ldquo;", "“"), ("&rdquo;", "”"),
                 ("&mdash;", "—"), ("&hellip;", "…"), ("&quot;", '"'), ("&amp;", "&"),
                 ("&lt;", "<"), ("&gt;", ">"), ("&rsquo;", "’"), ("&lsquo;", "‘")]:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def extract_article(html):
    """从文章页提取标题和正文段落。"""
    title = ""
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        title = clean_text(m.group(1))
    if not title:
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            title = clean_text(m.group(1)).split("_")[0].split("--")[0].strip()

    # 正文容器：优先 class 含 content / rm_txt_con / text
    body = ""
    for pat in [
        r'<div[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>(.*?)</div>\s*(?:</div>|<div[^>]*class="[^"]*(?:share|foot|related))',
        r'<div[^>]*class="[^"]*\brm_txt_con\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*id="[^"]*\bcontent\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*\btext\b[^"]*"[^>]*>(.*?)</div>',
    ]:
        m = re.search(pat, html, re.S)
        if m and len(m.group(1)) > 200:
            body = m.group(1)
            break
    if not body:
        body = html

    paras = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S):
        t = clean_text(p)
        if len(t) >= 15:
            paras.append(t)
    return title, paras


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._cur = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._cur = dict(attrs).get("href", "")
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self._cur is not None:
            t = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if 8 <= len(t) <= 100:
                self.links.append((self._cur, t))
            self._cur = None
            self._buf = []

    def handle_data(self, data):
        if self._cur is not None:
            self._buf.append(data)


def collect_qs(name, path):
    """求是网栏目"""
    try:
        html = fetch_html(BASE + path)
    except Exception as e:
        print(f"  x {name}: {e}")
        return []
    hrefs = re.findall(r'href="(?:\.\./)?(\d{8}/[a-f0-9]+/c\.html)"', html)
    out = []
    for h in dict.fromkeys(hrefs):   # 去重保序
        out.append({"url": BASE + "/" + h, "list": name, "date": h[:8]})
    print(f"  OK {name}: {len(out)} 篇")
    return out


def collect_people(name, url):
    """人民网栏目"""
    try:
        html = fetch_html(url)
    except Exception as e:
        print(f"  x {name}: {e}")
        return []
    m = re.findall(r'href="((?:https?:)?//[^"]*?/n1/(\d{4})/(\d{4})/c\d+-\d+\.html)"', html)
    out = []
    seen = set()
    for full, y, md in m:
        if full.startswith("//"):
            full = "http:" + full
        if full in seen:
            continue
        seen.add(full)
        out.append({"url": full, "list": name, "date": y + md})
    # 同栏目下补抓翻页
    base = url.rsplit("/", 1)[0]
    for i in (1, 2):
        try:
            h2 = fetch_html(f"{base}/index{i}.html")
        except Exception:
            continue
        for full, y, md in re.findall(r'href="((?:https?:)?//[^"]*?/n1/(\d{4})/(\d{4})/c\d+-\d+\.html)"', h2):
            if full.startswith("//"):
                full = "http:" + full
            if full in seen:
                continue
            seen.add(full)
            out.append({"url": full, "list": name, "date": y + md})
        time.sleep(0.2)
    print(f"  OK {name}: {len(out)} 篇")
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=200, help="最多入库篇数")
    ap.add_argument("--min-words", type=int, default=700, help="正文最少字数")
    args = ap.parse_args()

    print("=" * 60)
    print(f"范文抓取 · 目标 {args.max} 篇 · 最少 {args.min_words} 字")
    print("=" * 60)

    cands = []
    print("\n[求是网]")
    for name, path in QS_CHANNELS:
        cands.extend(collect_qs(name, path))
        time.sleep(0.15)

    print("\n[人民网]")
    for name, url in PEOPLE_CHANNELS:
        cands.extend(collect_people(name, url))
        time.sleep(0.15)

    # URL 去重
    seen, uniq = set(), []
    for c in cands:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        uniq.append(c)
    cands = uniq
    print(f"\n候选合计: {len(cands)} 篇（去重后）")

    # 按来源分组，轮流取，保证各栏目均衡
    by_src = {}
    for c in cands:
        by_src.setdefault(c["list"], []).append(c)
    order = sorted(by_src.keys(), key=lambda k: -len(by_src[k]))
    interleaved = []
    idx = 0
    while True:
        added = False
        for k in order:
            arr = by_src[k]
            if idx < len(arr):
                interleaved.append(arr[idx])
                added = True
        if not added:
            break
        idx += 1
    cands = interleaved
    print(f"来源 {len(by_src)} 个，按栏目轮流抓取\n")
    print(f"开始抓正文（目标 {args.max} 篇）...\n")

    out = []
    title_seen = set()
    fail = 0
    for i, c in enumerate(cands, 1):
        if len(out) >= args.max:
            break
        try:
            html = fetch_html(c["url"], timeout=12)
        except Exception:
            fail += 1
            continue

        title, paras = extract_article(html)
        if not paras:
            fail += 1
            continue
        wc = sum(len(re.sub(r"\s", "", p)) for p in paras)
        if wc < args.min_words:
            continue
        # 标题去重
        key = title[:24]
        if key in title_seen:
            continue
        title_seen.add(key)

        out.append({
            "title": title,
            "source": c["list"],
            "url": c["url"],
            "date": c["date"],
            "words": wc,
            "topics": detect_topics(title + " " + " ".join(paras[:3])),
            "paras": paras,
        })

        if len(out) % 20 == 0:
            print(f"  已入库 {len(out)} 篇（扫描 {i}/{len(cands)}）")
        time.sleep(0.22)

    print(f"\n完成：入库 {len(out)} 篇，失败 {fail} 次")

    payload = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "求是网 + 人民网",
        "total": len(out),
        "articles": out,
    }

    js = f"""/* ===== 申论范文（自动抓取）=====
 * 由 scripts/fetch_fanwen.py 生成 — {payload['updated']}
 * 来源：{payload['source']}
 * 共 {len(out)} 篇
 */

window.__FANWEN_MINED__ = """
    js += json.dumps(payload, ensure_ascii=False, indent=0, separators=(",", ":"))
    js += ";\n"

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(js)

    size = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"[DONE] -> {OUTPUT} ({size:.2f} MB)")
    if out:
        ws = [a["words"] for a in out]
        print(f"  平均字数: {sum(ws)//len(ws)} · 最长: {max(ws)} · 最短: {min(ws)}")
        src = {}
        for a in out:
            src[a["source"]] = src.get(a["source"], 0) + 1
        print("  来源分布: " + ", ".join(f"{k} {v}" for k, v in src.items()))


if __name__ == "__main__":
    main()

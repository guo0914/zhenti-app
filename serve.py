#!/usr/bin/env python3
"""一键启动服务器：静态站点 + 时政实时抓取 API。

用法:
    python serve.py [端口]

页面访问 http://本机IP:端口
实时接口 GET /api/news?fast=1&limit=30
"""

import http.server, os, sys, json, threading, time
from urllib.parse import urlparse, parse_qs
import socket

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

try:
    from news_core import fetch_all
    HAS_CORE = True
except Exception as e:
    HAS_CORE = False
    print(f"[warn] news_core 加载失败，实时抓取不可用: {e}")

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
try:
    HOST = socket.gethostbyname(socket.gethostname())
except Exception:
    HOST = "127.0.0.1"

SITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

# 法律题库真金题 PDF（用于按需生成原书页面图片）
# 代码 → (PDF 路径, 书印页码偏移)。PDF 缺失时该科不生成图片，前端优雅降级。
LAW_BOOKS = {
    "xf":    (r"C:\Users\严睿霖\Desktop\真金题-刑法-柏浪涛.pdf", 11),
    "mf":    (r"C:\Users\严睿霖\Desktop\真金题-民法-孟献贵.pdf", 11),
    "msf":   (r"C:\Users\严睿霖\Desktop\真金题-民诉法-戴鹏.pdf", 7),
    "xsf":   (r"C:\Users\严睿霖\Desktop\真金题-刑诉法-左宁.pdf", 9),
    "xzf":   (r"C:\Users\严睿霖\Desktop\真金题-行政法-李佳.pdf", 9),
    "sxz":   (r"C:\Users\严睿霖\Desktop\真金题-商经知-郄鹏恩.pdf", 13),
    "sgf":   (r"C:\Users\严睿霖\Desktop\真金题-三国法-杨帆.pdf", 9),
    "lilun": (r"C:\Users\严睿霖\Desktop\真金题-理论法-马峰.pdf", 11),
}

# ── 内存缓存：避免重复抓取 ──
_cache = {"data": None, "ts": 0, "lock": threading.Lock()}
CACHE_TTL = 180          # 3 分钟内的请求直接返回缓存
INFLIGHT = {"running": False}


def get_news(fast=True, limit=30, content=False, timeout=45, force=False):
    """带缓存与去重的抓取。"""
    now = time.time()
    if not force and _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        d = dict(_cache["data"])
        d["cached"] = True
        d["cache_age"] = round(now - _cache["ts"])
        return d

    with _cache["lock"]:
        # 拿到锁后再检查一次
        now = time.time()
        if not force and _cache["data"] and now - _cache["ts"] < CACHE_TTL:
            d = dict(_cache["data"])
            d["cached"] = True
            d["cache_age"] = round(now - _cache["ts"])
            return d

        try:
            data = fetch_all(
                fetch_content_flag=content,
                max_per=limit,
                content_limit=300 if content else 0,
                deadline=time.time() + timeout,
            )
        except Exception:
            if _cache["data"]:
                d = dict(_cache["data"])
                d["cached"] = True
                d["cache_age"] = round(time.time() - _cache["ts"])
                d["stale"] = True
                return d
            raise

        _cache["data"] = data
        _cache["ts"] = time.time()
        d = dict(data)
        d["cached"] = False
        return d


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.webmanifest': 'application/manifest+json',
        '.json': 'application/json',
    }

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, fmt, *args):
        # 只打 API 日志，静态资源静默
        if '/api/' in (args[0] if args else ''):
            sys.stderr.write("[api] " + (fmt % args) + "\n")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/news':
            self.handle_api_news(parsed)
            return
        if parsed.path == '/api/status':
            self.send_json({
                "ok": True,
                "has_core": HAS_CORE,
                "cache_age": round(time.time() - _cache["ts"]) if _cache["data"] else None,
                "cached_total": (_cache["data"] or {}).get("total"),
            })
            return
        # 法律题库原书图片按需生成
        if self.try_gen_lawimg(parsed.path):
            return
        super().do_GET()

    def try_gen_lawimg(self, path):
        """路径形如 /data/zt/law_img/xf-0123.webp 时，实时从 PDF 生成。"""
        import re as _re
        m = _re.match(r'^/data/zt/law_img/([a-z]+)-(\d{4})\.(webp|jpg)$', path)
        if not m:
            return False
        code, label, ext = m.group(1), int(m.group(2)), m.group(3)

        book = LAW_BOOKS.get(code)
        if not book:
            return False
        pdf_path, offset = book
        if not os.path.isfile(pdf_path):
            return False

        try:
            import pymupdf
            from PIL import Image
        except ImportError:
            return False

        pdf_page = label + offset
        try:
            doc = pymupdf.open(pdf_path)
            if not (1 <= pdf_page <= doc.page_count):
                doc.close()
                return False
            page = doc[pdf_page - 1]
            pix = page.get_pixmap(dpi=int(760 / (595 / 72)))
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
            doc.close()
        except Exception:
            return False

        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'site', 'data', 'zt', 'law_img')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{code}-{label:04d}.{ext}")
        try:
            if ext == 'webp':
                img.save(out_path, 'WEBP', quality=72, method=4)
                ctype = 'image/webp'
            else:
                img.save(out_path, 'JPEG', quality=72, optimize=True)
                ctype = 'image/jpeg'
            with open(out_path, 'rb') as f:
                body = f.read()
        except Exception:
            return False

        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        return True

    def handle_api_news(self, parsed):
        if not HAS_CORE:
            self.send_json({"ok": False, "error": "抓取模块不可用"}, status=503)
            return
        q = parse_qs(parsed.query)
        try:
            limit = int(q.get('limit', ['30'])[0])
            limit = max(5, min(limit, 60))
            content = q.get('content', ['0'])[0] in ('1', 'true', 'yes')
            timeout = int(q.get('timeout', ['45'])[0])
            timeout = max(10, min(timeout, 120))
            force = q.get('force', ['0'])[0] in ('1', 'true', 'yes')
        except ValueError:
            limit, content, timeout, force = 30, False, 45, False

        try:
            data = get_news(fast=True, limit=limit, content=content,
                            timeout=timeout, force=force)
            self.send_json({"ok": True, **data})
        except Exception as e:
            self.send_json({"ok": False, "error": str(e)[:200]}, status=500)

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    os.chdir(SITE_DIR)
    print(f"""
╔══════════════════════════════════════════╗
║   分类真题刷题 · 局域网 + 实时资讯        ║
╠══════════════════════════════════════════╣
║                                          ║
║   PC 浏览器:  http://{HOST}:{PORT}
║   手机访问:    http://{HOST}:{PORT}
║                                          ║
║   实时资讯接口: /api/news                 ║
║   抓取模块:    {'已启用' if HAS_CORE else '未启用'}
║   缓存有效期:  {CACHE_TTL} 秒
║                                          ║
║   手机需与电脑同一 WiFi/热点              ║
║   iPhone:  Safari → 分享 → 添加到主屏幕   ║
║   Android: Chrome → 更多 → 添加到主屏幕   ║
║                                          ║
║   按 Ctrl+C 停止服务                      ║
╚══════════════════════════════════════════╝
""")
    srv = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == '__main__':
    main()

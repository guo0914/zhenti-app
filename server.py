"""
资料分析刷题 · 后端服务
仅依赖 Python 标准库（http.server + sqlite3），无需 pip 安装任何东西。

用法：
    python server.py                 # 默认 http://127.0.0.1:8000
    python server.py --port 8000 --host 127.0.0.1 --open

数据全部落库在同目录下的 quiz.db（SQLite）。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import random
import re
import secrets
import sqlite3
import string
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quiz.db")

# ── DeepSeek API 配置（从环境变量读取，不要写死在代码里）──
# 设置方式：
#   Windows:  set DEEPSEEK_API_KEY=sk-xxxx  然后重启服务器
#   或写入 ai_key.txt（仅本机，不要提交到仓库）
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

_AI_KEY_FILE = os.path.join(BASE_DIR, "ai_key.txt")
if not DEEPSEEK_API_KEY and os.path.exists(_AI_KEY_FILE):
    try:
        # 注意：用 utf-8-sig 读，自动去掉 BOM（\ufeff）；
        # 否则 BOM 会混进 Authorization 头，导致
        # UnicodeEncodeError: 'latin-1' codec can't encode
        DEEPSEEK_API_KEY = open(_AI_KEY_FILE, encoding="utf-8-sig").read().strip()
        # 再做一层保险：去掉所有不可见字符
        DEEPSEEK_API_KEY = DEEPSEEK_API_KEY.strip("\ufeff\u200b \t\r\n")
    except Exception:
        pass
STATIC_DIR = os.path.join(BASE_DIR, "site")
ZHENTI_PATH = os.path.join(STATIC_DIR, "data", "zhenti.json")

# 法律题库真金题 PDF（用于按需生成原书页面图片）
# 代码 → (PDF 路径, 书印页码偏移)。PDF 缺失时该科不生成图片，前端会优雅降级。
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

# 时政资讯抓取核心（可选依赖，缺失时 /api/news 不可用）
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
try:
    from news_core import fetch_all as _fetch_news_all
    HAS_NEWS_CORE = True
except Exception:
    HAS_NEWS_CORE = False
    _fetch_news_all = None

TOKEN_TTL = 60 * 60 * 24 * 30          # 30 天
PBKDF2_ROUNDS = 160_000
MAX_BODY = 4 * 1024 * 1024

# ---------------------------------------------------------------- 数据库


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT    NOT NULL,
    username_key TEXT    NOT NULL UNIQUE,      -- 小写，用于查重与登录
    nickname     TEXT    NOT NULL DEFAULT '',
    pass_hash    TEXT    NOT NULL,
    pass_salt    TEXT    NOT NULL,
    created_at   INTEGER NOT NULL,
    last_login   INTEGER,
    avatar       TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    ua         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS answers (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    qid      TEXT    NOT NULL,
    sel      TEXT    NOT NULL DEFAULT '',
    ok       INTEGER NOT NULL DEFAULT 0,
    secs     INTEGER NOT NULL DEFAULT 0,       -- 本题用时（秒）
    ts       INTEGER NOT NULL,
    bank     TEXT    NOT NULL DEFAULT 'builtin',
    PRIMARY KEY (user_id, qid)
);

CREATE TABLE IF NOT EXISTS marks (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    qid     TEXT    NOT NULL,
    ts      INTEGER NOT NULL,
    bank    TEXT    NOT NULL DEFAULT 'builtin',
    PRIMARY KEY (user_id, qid)
);

CREATE TABLE IF NOT EXISTS wrongs (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    qid         TEXT    NOT NULL,
    wrong_count INTEGER NOT NULL DEFAULT 1,
    fixed       INTEGER NOT NULL DEFAULT 0,
    cleared     INTEGER NOT NULL DEFAULT 0,
    last_ts     INTEGER NOT NULL,
    bank        TEXT    NOT NULL DEFAULT 'builtin',
    PRIMARY KEY (user_id, qid)
);

CREATE TABLE IF NOT EXISTS sets_time (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    set_no      INTEGER NOT NULL,
    elapsed     INTEGER NOT NULL DEFAULT 0,    -- 累计用时（秒）
    limit_secs  INTEGER NOT NULL DEFAULT 0,    -- 0 表示不限时
    submitted   INTEGER NOT NULL DEFAULT 0,
    submit_ts   INTEGER,
    bank        TEXT    NOT NULL DEFAULT 'builtin',
    PRIMARY KEY (user_id, set_no, bank)
);

CREATE TABLE IF NOT EXISTS day_stats (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day     TEXT    NOT NULL,
    n       INTEGER NOT NULL DEFAULT 0,
    ok      INTEGER NOT NULL DEFAULT 0,
    secs    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

CREATE TABLE IF NOT EXISTS question_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    qid     TEXT    NOT NULL,
    sel     TEXT    NOT NULL DEFAULT '',
    ok      INTEGER NOT NULL DEFAULT 0,
    secs    INTEGER NOT NULL DEFAULT 0,
    ts      INTEGER NOT NULL,
    bank    TEXT    NOT NULL DEFAULT 'builtin'
);
CREATE INDEX IF NOT EXISTS idx_log_user_ts ON question_log(user_id, ts);

-- 分类刷题：用户自选组数的一次练习记录
CREATE TABLE IF NOT EXISTS drills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cat         TEXT    NOT NULL,               -- 分类 key
    total       INTEGER NOT NULL,               -- 自选组数
    qids        TEXT    NOT NULL,               -- JSON 数组，本次抽到的题目
    done        INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0,
    elapsed     INTEGER NOT NULL DEFAULT 0,     -- 秒
    created_at  INTEGER NOT NULL,
    finished_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_drills_user ON drills(user_id, created_at);
"""


def now() -> int:
    return int(time.time())


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- 分类题库

_zhenti_cache: dict | None = None
_zhenti_mtime: float = 0.0


def load_zhenti() -> dict:
    """加载真题库（按文件修改时间缓存，改题库后无需重启）。"""
    global _zhenti_cache, _zhenti_mtime
    try:
        mtime = os.path.getmtime(ZHENTI_PATH)
    except OSError:
        return {"meta": {}, "categories": [], "questions": []}
    if _zhenti_cache is not None and mtime == _zhenti_mtime:
        return _zhenti_cache
    try:
        with open(ZHENTI_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        print(f"[zhenti] 读取失败: {exc}")
        return {"meta": {}, "categories": [], "questions": []}
    data.setdefault("questions", [])
    data.setdefault("categories", [])
    by_cat: dict[str, list[dict]] = {}
    for q in data["questions"]:
        by_cat.setdefault(q.get("cat", ""), []).append(q)
    data["_by_cat"] = by_cat
    _zhenti_cache = data
    _zhenti_mtime = mtime
    return data


# ---------------------------------------------------------------- 密码

def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return digest, salt


def verify_password(password: str, digest: str, salt: str) -> bool:
    calc = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    ).hex()
    return hmac.compare_digest(calc, digest)


USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5]{3,20}$")


def check_username(name: str) -> str | None:
    if not USERNAME_RE.match(name or ""):
        return "用户名需为 3–20 位中文、字母、数字或下划线"
    return None


def check_password(pw: str) -> str | None:
    if not isinstance(pw, str) or len(pw) < 6:
        return "密码至少 6 位"
    if len(pw) > 64:
        return "密码太长（最多 64 位）"
    return None


# ---------------------------------------------------------------- 时政资讯缓存

NEWS_CACHE_TTL = 60           # 秒；TTL 内直接返回缓存（60 秒，保证足够新）
NEWS_PREWARM_INTERVAL = 120   # 秒；后台预热间隔，让请求永远拿到新鲜数据
_NEWS_CACHE = {"data": None, "ts": 0.0, "sig": ""}
_NEWS_LOCK = threading.Lock()
_NEWS_PREWARM = {"stop": False}


def _news_signature(data) -> str:
    """用最新文章的 url 生成签名，用于判断是否有新内容。"""
    arts = (data or {}).get("articles") or []
    if not arts:
        return ""
    return "%s|%d" % (arts[0].get("url", ""), len(arts))


def news_cache_get(limit: int = 30, content: bool = False,
                   timeout: int = 45, force: bool = False) -> dict:
    """带缓存与并发去重的时政抓取。"""
    if not HAS_NEWS_CORE:
        raise ApiError(503, "抓取模块不可用")

    # 快速路径：不加锁
    if not force and _NEWS_CACHE["data"] and time.time() - _NEWS_CACHE["ts"] < NEWS_CACHE_TTL:
        d = dict(_NEWS_CACHE["data"])
        d["cached"] = True
        d["cache_age"] = int(time.time() - _NEWS_CACHE["ts"])
        d["first_article"] = ((d.get("articles") or [{}])[0]).get("date", "")
        return d

    with _NEWS_LOCK:
        # 拿到锁后再判断，避免并发重复抓取
        if not force and _NEWS_CACHE["data"] and time.time() - _NEWS_CACHE["ts"] < NEWS_CACHE_TTL:
            d = dict(_NEWS_CACHE["data"])
            d["cached"] = True
            d["cache_age"] = int(time.time() - _NEWS_CACHE["ts"])
            d["first_article"] = ((d.get("articles") or [{}])[0]).get("date", "")
            return d

        prev_sig = _NEWS_CACHE.get("sig", "")
        try:
            data = _fetch_news_all(
                fetch_content_flag=content,
                max_per=limit,
                content_limit=300 if content else 0,
                deadline=time.time() + timeout,
            )
        except Exception as exc:
            # 抓取失败时，若有旧缓存则降级返回
            if _NEWS_CACHE["data"]:
                d = dict(_NEWS_CACHE["data"])
                d["cached"] = True
                d["cache_age"] = int(time.time() - _NEWS_CACHE["ts"])
                d["stale"] = True
                d["error"] = str(exc)[:200]
                return d
            raise ApiError(502, "抓取失败：" + str(exc)[:150])

        new_sig = _news_signature(data)
        _NEWS_CACHE["data"] = data
        _NEWS_CACHE["ts"] = time.time()
        _NEWS_CACHE["sig"] = new_sig
        d = dict(data)
        d["cached"] = False
        d["changed"] = bool(prev_sig and new_sig != prev_sig)
        d["first_article"] = (data.get("articles") or [{}])[0].get("date", "")
        return d


def news_prewarm_loop():
    """后台预热：定时静默抓取，让用户请求总是命中新鲜缓存。"""
    global _NEWS_CACHE
    # 启动后先等 5 秒，避免和启动流程抢资源
    time.sleep(5)
    while not _NEWS_PREWARM["stop"]:
        try:
            if HAS_NEWS_CORE:
                with _NEWS_LOCK:
                    data = _fetch_news_all(
                        fetch_content_flag=False,
                        max_per=30,
                        deadline=time.time() + 40,
                    )
                    _NEWS_CACHE["data"] = data
                    _NEWS_CACHE["ts"] = time.time()
                    _NEWS_CACHE["sig"] = _news_signature(data)
                    sys.stderr.write("[news] 预热完成 %d 篇 最新 %s\n" % (
                        data.get("total", 0),
                        (data.get("articles") or [{}])[0].get("date", "-")))
        except Exception as exc:
            sys.stderr.write("[news] 预热失败: %s\n" % str(exc)[:120])
        # 分段 sleep，便于快速退出
        for _ in range(NEWS_PREWARM_INTERVAL):
            if _NEWS_PREWARM["stop"]:
                break
            time.sleep(1)


def start_news_prewarm():
    if not HAS_NEWS_CORE:
        return
    t = threading.Thread(target=news_prewarm_loop, daemon=True)
    t.start()


# ---------------------------------------------------------------- HTTP 基类

class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "ZLFXP/2.0"
    protocol_version = "HTTP/1.1"

    # ---------- 基础响应 ----------
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        # App（capacitor://localhost）跨域调用 API 需要这些头
        try:
            self._cors_headers()
        except Exception:
            pass
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def error(self, status: int, message: str) -> None:
        self.json({"ok": False, "error": message}, status)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ApiError(413, "请求体过大")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ApiError(400, "请求体不是合法 JSON")
        if not isinstance(data, dict):
            raise ApiError(400, "请求体必须是 JSON 对象")
        return data

    # ---------- 认证 ----------
    def current_user_id(self) -> int | None:
        auth = self.headers.get("Authorization") or ""
        token = ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            token = self.headers.get("X-Token") or ""
        if not token:
            return None
        conn = db()
        try:
            row = conn.execute(
                "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
            ).fetchone()
            if not row:
                return None
            if row["expires_at"] < now():
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                return None
            return int(row["user_id"])
        finally:
            conn.close()

    def require_user(self) -> int:
        uid = self.current_user_id()
        if uid is None:
            raise ApiError(401, "登录已失效，请重新登录")
        return uid

    # ---------- 路由 ----------
    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _cors_headers(self):
        origin = self.headers.get("Origin") or "*"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type,Authorization,X-Requested-With,X-User-Api-Key")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET,POST,PUT,DELETE,OPTIONS")
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _dispatch(self, method: str) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self.handle_api(method, path[4:], query)
            elif method in ("GET", "HEAD"):
                self.serve_static(path)
            else:
                self.error(405, "不支持的方法")
        except ApiError as exc:
            self.error(exc.status, exc.message)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            traceback.print_exc()
            try:
                self.error(500, "服务器内部错误")
            except Exception:
                pass

    # ---------- 静态文件 ----------
    def serve_static(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"
        rel = path.lstrip("/")
        target = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not target.startswith(STATIC_DIR):
            self.error(403, "禁止访问")
            return
        if not os.path.isfile(target):
            # 法律题库原书图片按需生成：/data/zt/law_img/{code}-{page}.webp
            if self._try_gen_lawimg(path):
                return
            self.error(404, "文件不存在")
            return
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        # PWA 需要的 MIME 类型
        if target.endswith(".webmanifest"):
            ctype = "application/manifest+json"
        elif target.endswith(".ico"):
            ctype = "image/x-icon"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json",
                                                  "application/manifest+json"):
            ctype += "; charset=utf-8"
        with open(target, "rb") as fh:
            body = fh.read()

        # 内容哈希做 ETag，配合 no-cache：文件变了 URL 不变也会重新拉取
        etag = '"' + hashlib.md5(body).hexdigest()[:16] + '"'
        inm = self.headers.get("If-None-Match")
        if inm == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # 代码/样式/HTML 一律 no-cache（每次问服务器，用 ETag 304 省流量）；
        # 图片（路径含 assets/zt、mat、q）是静态的，可缓存一天
        is_html = target.endswith(".html")
        is_selfheal = "selfheal.js" in path
        is_sw = target.endswith("sw.js")
        if ctype.startswith("image/") and any(s in path for s in ("/zt/", "/mat/", "/q/")):
            cache = "public, max-age=86400"
        elif is_html or is_selfheal or is_sw:
            # HTML / 自愈脚本 / Service Worker 必须每次校验，否则会长期停留旧版本
            cache = "no-cache, no-store, must-revalidate"
        else:
            cache = "no-cache"
        extra = {"Cache-Control": cache, "ETag": etag}
        if is_html or is_selfheal or is_sw:
            extra["Pragma"] = "no-cache"
            extra["Expires"] = "0"
        # Service Worker 必须允许跨源更新检查
        if is_sw:
            extra["Service-Worker-Allowed"] = "/"
        self._send(200, body, ctype, extra)

    # ---------- 法律题库原书图片按需生成 ----------
    def _try_gen_lawimg(self, path: str) -> bool:
        """路径形如 /data/zt/law_img/xf-0123.webp 时，实时从 PDF 生成。

        这样不必把所有题页都打包进仓库（1500 页约 71MB），
        用户点哪页就生成哪页，并写入磁盘缓存供后续复用。
        """
        import re as _re
        m = _re.match(r"^/data/zt/law_img/([a-z]+)-(\d{4})\.(webp|jpg)$", path)
        if not m:
            return False
        code, label, ext = m.group(1), int(m.group(2)), m.group(3)

        # 科目代码 → (PDF 路径, 页码偏移)
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
            dpi = int(760 / (595 / 72))
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
            doc.close()

            # 写入 site/data/zt/law_img/ 缓存
            out_dir = os.path.join(STATIC_DIR, "data", "zt", "law_img")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{code}-{label:04d}.{ext}")
            if ext == "webp":
                img.save(out_path, "WEBP", quality=72, method=4)
            else:
                img.save(out_path, "JPEG", quality=72, optimize=True)

            with open(out_path, "rb") as f:
                body = f.read()
            ctype = "image/webp" if ext == "webp" else "image/jpeg"
            self._send(200, body, ctype,
                       {"Cache-Control": "public, max-age=86400"})
            return True
        except Exception:
            traceback.print_exc()
            return False

    # ---------- API ----------
    def api_ai_chat(self) -> None:
        """代理 DeepSeek chat/completions 请求。

        前端 POST 过来的 body 就是原本要发给 DeepSeek 的 JSON，
        这里补上 Authorization 头再转发，把响应原样返回。
        key 只存在服务器上，开源后也不会泄漏。
        """
        # 优先使用用户自带的 Key（前端通过 X-User-Api-Key 传入）
        # 服务器不保存它，只用于本次转发
        user_key = ""
        try:
            user_key = (self.headers.get("X-User-Api-Key") or "").strip()
        except Exception:
            user_key = ""

        active_key = user_key or DEEPSEEK_API_KEY
        if not active_key:
            self.json({
                "error": {
                    "message": "未设置 API Key。请在申论批改的设置里填入你自己的 "
                               "DeepSeek API Key（在 platform.deepseek.com 申请）。"
                }
            }, status=503)
            return
        if not user_key and not DEEPSEEK_API_KEY:
            active_key = ""

        try:
            body = self.read_json()
        except Exception as e:
            self.json({"error": {"message": f"请求体解析失败: {e}"}}, status=400)
            return

        # 限制单次请求体（截图 base64 可能很大）
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if len(payload) > 25 * 1024 * 1024:
            self.json({"error": {"message": "请求体过大（上限 25MB）"}}, status=413)
            return

        import urllib.request as _ur

        url = DEEPSEEK_API_BASE.rstrip("/") + "/chat/completions"
        req = _ur.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + active_key,
            },
            method="POST",
        )

        try:
            with _ur.urlopen(req, timeout=180) as resp:
                raw = resp.read()
                status = resp.status
        except Exception as exc:
            # 上游返回了 HTTP 错误（如 401 key 无效 / 402 余额不足 / 429 限流）
            up_code = getattr(exc, "code", None)
            up_body = ""
            try:
                if hasattr(exc, "read"):
                    up_body = exc.read().decode("utf-8", "replace")
            except Exception:
                pass

            # 上游给了 JSON 错误信息就原样转发
            if up_body.strip():
                try:
                    parsed = json.loads(up_body)
                    msg = (parsed.get("error") or {}).get("message") or up_body[:400]
                except Exception:
                    msg = up_body[:400]
                self._send(int(up_code or 502), up_body.encode("utf-8"),
                           "application/json; charset=utf-8")
                return

            # 上游响应体为空，按状态码给出可读提示
            HINTS = {
                401: "API Key 无效或已失效，请管理员更新 ai_key.txt",
                402: "DeepSeek 账户余额不足，请充值后再使用 AI 批改",
                403: "API Key 无权限访问该模型",
                429: "请求过于频繁（限流），请稍后再试",
                500: "DeepSeek 服务器内部错误，请稍后再试",
                503: "DeepSeek 服务暂时不可用，请稍后再试",
            }
            code = int(up_code or 502)
            msg = HINTS.get(code, "AI 调用失败：" + str(exc)[:200])
            self.json({"error": {"message": msg, "upstream": code}}, status=code)
            return

        self._send(status, raw, "application/json; charset=utf-8")

    def handle_api(self, method: str, route: str, query: dict) -> None:
        route = route.strip("/")

        if route == "health" and method == "GET":
            self.json({"ok": True, "time": now(), "db": os.path.basename(DB_PATH)})
            return

        # ── AI 代理：把 API Key 留在服务器端，前端不再接触 ──
        if route == "ai/chat" and method == "POST":
            return self.api_ai_chat()
        if route == "ai/status" and method == "GET":
            return self.json({
                "serverKey": bool(DEEPSEEK_API_KEY),
                "needUserKey": not bool(DEEPSEEK_API_KEY),
                "model": "deepseek-chat",
            })

        if route == "auth/register" and method == "POST":
            return self.api_register()
        if route == "auth/login" and method == "POST":
            return self.api_login()
        if route == "auth/logout" and method == "POST":
            return self.api_logout()
        if route == "auth/me" and method == "GET":
            return self.api_me()

        if route == "progress" and method == "GET":
            return self.api_get_progress()
        if route == "progress" and method == "POST":
            return self.api_put_progress()
        if route == "answer" and method == "POST":
            return self.api_answer()
        if route == "favorite" and method == "POST":
            return self.api_favorite()
        if route == "wrong" and method == "POST":
            return self.api_wrong()
        if route == "timer" and method == "POST":
            return self.api_timer()
        if route == "stats" and method == "GET":
            return self.api_stats()
        if route == "reset" and method == "POST":
            return self.api_reset()

        # ---- 分类真题 ----
        if route == "cats" and method == "GET":
            return self.api_cats()
        if route == "zhenti" and method == "GET":
            return self.api_zhenti(query)
        if route == "drill" and method == "POST":
            return self.api_drill_start()
        if route == "drill" and method == "PUT":
            return self.api_drill_update()
        if route == "drills" and method == "GET":
            return self.api_drill_list()

        # ---- 时政资讯（实时抓取）----
        if route == "news" and method == "GET":
            return self.api_news(query)
        if route == "news/status" and method == "GET":
            return self.api_news_status()

        self.error(404, "接口不存在")

    # ---------- 账号 ----------
    def api_register(self) -> None:
        data = self.read_json()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        nickname = (data.get("nickname") or "").strip()[:20]

        err = check_username(username) or check_password(password)
        if err:
            raise ApiError(400, err)

        key = username.lower()
        digest, salt = hash_password(password)
        conn = db()
        try:
            exists = conn.execute(
                "SELECT id FROM users WHERE username_key = ?", (key,)
            ).fetchone()
            if exists:
                raise ApiError(409, "该用户名已被注册")
            cur = conn.execute(
                "INSERT INTO users (username, username_key, nickname, pass_hash, pass_salt, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (username, key, nickname or username, digest, salt, now()),
            )
            uid = int(cur.lastrowid)
            token = self.new_session(conn, uid)
            conn.commit()
        finally:
            conn.close()

        self.json({
            "ok": True,
            "token": token,
            "user": {"id": uid, "username": username, "nickname": nickname or username},
        })

    def api_login(self) -> None:
        data = self.read_json()
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            raise ApiError(400, "请输入用户名和密码")

        conn = db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username_key = ?", (username.lower(),)
            ).fetchone()
            if not row or not verify_password(password, row["pass_hash"], row["pass_salt"]):
                raise ApiError(401, "用户名或密码错误")
            uid = int(row["id"])
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now(), uid))
            token = self.new_session(conn, uid)
            conn.commit()
            user = {
                "id": uid,
                "username": row["username"],
                "nickname": row["nickname"] or row["username"],
            }
        finally:
            conn.close()

        self.json({"ok": True, "token": token, "user": user})

    def new_session(self, conn: sqlite3.Connection, uid: int) -> str:
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at, ua) VALUES (?,?,?,?,?)",
            (token, uid, now(), now() + TOKEN_TTL, (self.headers.get("User-Agent") or "")[:200]),
        )
        # 顺手清理过期会话
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        return token

    def api_logout(self) -> None:
        auth = self.headers.get("Authorization") or ""
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if token:
            conn = db()
            try:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
            finally:
                conn.close()
        self.json({"ok": True})

    def api_me(self) -> None:
        uid = self.require_user()
        conn = db()
        try:
            row = conn.execute(
                "SELECT id, username, nickname, created_at, last_login FROM users WHERE id = ?",
                (uid,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            raise ApiError(401, "用户不存在")
        self.json({"ok": True, "user": dict(row)})

    # ---------- 进度 ----------
    def api_get_progress(self) -> None:
        uid = self.require_user()
        conn = db()
        try:
            answers = {}
            for r in conn.execute(
                "SELECT qid, sel, ok, secs, ts, bank FROM answers WHERE user_id = ?", (uid,)
            ):
                answers[r["qid"]] = {
                    "sel": r["sel"], "ok": bool(r["ok"]), "ts": r["ts"] * 1000,
                    "secs": r["secs"], "bank": r["bank"],
                }
            marks = {
                r["qid"]: 1
                for r in conn.execute("SELECT qid FROM marks WHERE user_id = ?", (uid,))
            }
            wrong = {}
            for r in conn.execute(
                "SELECT qid, wrong_count, fixed, cleared, last_ts FROM wrongs WHERE user_id = ?",
                (uid,),
            ):
                wrong[r["qid"]] = {
                    "wrongCount": r["wrong_count"],
                    "fixed": bool(r["fixed"]),
                    "cleared": bool(r["cleared"]),
                    "lastTs": r["last_ts"] * 1000,
                }
            sets = {}
            for r in conn.execute(
                "SELECT set_no, elapsed, limit_secs, submitted, submit_ts FROM sets_time WHERE user_id = ?",
                (uid,),
            ):
                sets[str(r["set_no"])] = {
                    "elapsed": r["elapsed"],
                    "limit": r["limit_secs"],
                    "submitted": bool(r["submitted"]),
                    "submitTs": (r["submit_ts"] or 0) * 1000,
                }
            days = {
                r["day"]: {"n": r["n"], "ok": r["ok"], "secs": r["secs"]}
                for r in conn.execute(
                    "SELECT day, n, ok, secs FROM day_stats WHERE user_id = ?", (uid,)
                )
            }
        finally:
            conn.close()

        self.json({"ok": True, "answers": answers, "marks": marks, "wrong": wrong,
                   "sets": sets, "days": days})

    def api_put_progress(self) -> None:
        """整包覆盖式同步（登录时把本地进度推到服务器用）。"""
        uid = self.require_user()
        data = self.read_json()
        answers = data.get("answers") or {}
        marks = data.get("marks") or {}
        wrong = data.get("wrong") or {}

        conn = db()
        try:
            ts = now()
            for qid, a in answers.items():
                if not isinstance(a, dict):
                    continue
                conn.execute(
                    "INSERT INTO answers (user_id, qid, sel, ok, secs, ts, bank) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(user_id, qid) DO UPDATE SET sel=excluded.sel, ok=excluded.ok, "
                    "secs=excluded.secs, ts=excluded.ts",
                    (uid, str(qid), str(a.get("sel") or ""), 1 if a.get("ok") else 0,
                     int(a.get("secs") or 0), int(a.get("ts") or ts * 1000) // 1000, "builtin"),
                )
            for qid, v in marks.items():
                if v:
                    conn.execute(
                        "INSERT OR IGNORE INTO marks (user_id, qid, ts, bank) VALUES (?,?,?,?)",
                        (uid, str(qid), ts, "builtin"),
                    )
                else:
                    conn.execute("DELETE FROM marks WHERE user_id = ? AND qid = ?", (uid, str(qid)))
            for qid, w in wrong.items():
                if not isinstance(w, dict):
                    continue
                conn.execute(
                    "INSERT INTO wrongs (user_id, qid, wrong_count, fixed, cleared, last_ts, bank) "
                    "VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id, qid) DO UPDATE SET "
                    "wrong_count=excluded.wrong_count, fixed=excluded.fixed, cleared=excluded.cleared, "
                    "last_ts=excluded.last_ts",
                    (uid, str(qid), int(w.get("wrongCount") or 0),
                     1 if w.get("fixed") else 0, 1 if w.get("cleared") else 0,
                     int(w.get("lastTs") or ts * 1000) // 1000, "builtin"),
                )
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})

    def api_answer(self) -> None:
        uid = self.require_user()
        d = self.read_json()
        qid = str(d.get("qid") or "").strip()
        if not qid:
            raise ApiError(400, "缺少题目 ID")
        sel = str(d.get("sel") or "").strip().upper()[:1]
        ok = bool(d.get("ok"))
        secs = max(0, min(3600, int(d.get("secs") or 0)))
        bank = str(d.get("bank") or "builtin")[:32]

        conn = db()
        try:
            ts = now()
            conn.execute(
                "INSERT INTO answers (user_id, qid, sel, ok, secs, ts, bank) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(user_id, qid) DO UPDATE SET sel=excluded.sel, ok=excluded.ok, "
                "secs=excluded.secs, ts=excluded.ts",
                (uid, qid, sel, 1 if ok else 0, secs, ts, bank),
            )
            conn.execute(
                "INSERT INTO question_log (user_id, qid, sel, ok, secs, ts, bank) VALUES (?,?,?,?,?,?,?)",
                (uid, qid, sel, 1 if ok else 0, secs, ts, bank),
            )
            day = time.strftime("%Y-%m-%d", time.localtime())
            conn.execute(
                "INSERT INTO day_stats (user_id, day, n, ok, secs) VALUES (?,?,1,?,?) "
                "ON CONFLICT(user_id, day) DO UPDATE SET n=n+1, ok=ok+excluded.ok, secs=secs+excluded.secs",
                (uid, day, 1 if ok else 0, secs),
            )
            if not ok:
                conn.execute(
                    "INSERT INTO wrongs (user_id, qid, wrong_count, last_ts, bank) VALUES (?,?,1,?,?) "
                    "ON CONFLICT(user_id, qid) DO UPDATE SET wrong_count=wrong_count+1, "
                    "last_ts=excluded.last_ts, cleared=0",
                    (uid, qid, ts, bank),
                )
            else:
                conn.execute(
                    "UPDATE wrongs SET fixed = 1 WHERE user_id = ? AND qid = ?", (uid, qid)
                )
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})

    def api_favorite(self) -> None:
        uid = self.require_user()
        d = self.read_json()
        qid = str(d.get("qid") or "").strip()
        if not qid:
            raise ApiError(400, "缺少题目 ID")
        want = bool(d.get("fav"))
        conn = db()
        try:
            if want:
                conn.execute(
                    "INSERT OR IGNORE INTO marks (user_id, qid, ts, bank) VALUES (?,?,?,?)",
                    (uid, qid, now(), str(d.get("bank") or "builtin")[:32]),
                )
            else:
                conn.execute("DELETE FROM marks WHERE user_id = ? AND qid = ?", (uid, qid))
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True, "fav": want})

    def api_wrong(self) -> None:
        uid = self.require_user()
        d = self.read_json()
        qid = str(d.get("qid") or "").strip()
        action = str(d.get("action") or "").strip()
        if not qid:
            raise ApiError(400, "缺少题目 ID")
        conn = db()
        try:
            if action == "clear":
                conn.execute(
                    "UPDATE wrongs SET cleared = 1 WHERE user_id = ? AND qid = ?", (uid, qid)
                )
            elif action == "drop":
                conn.execute("DELETE FROM wrongs WHERE user_id = ? AND qid = ?", (uid, qid))
            else:
                raise ApiError(400, "未知操作")
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})

    def api_timer(self) -> None:
        """上报/读取某套题的计时。"""
        uid = self.require_user()
        d = self.read_json()
        set_no = int(d.get("set") or 0)
        if set_no <= 0:
            raise ApiError(400, "缺少套题号")
        elapsed = max(0, min(60 * 60 * 6, int(d.get("elapsed") or 0)))
        limit = max(0, min(60 * 60 * 3, int(d.get("limit") or 0)))
        submitted = bool(d.get("submitted"))
        bank = str(d.get("bank") or "builtin")[:32]

        conn = db()
        try:
            conn.execute(
                "INSERT INTO sets_time (user_id, set_no, elapsed, limit_secs, submitted, submit_ts, bank) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id, set_no, bank) DO UPDATE SET "
                "elapsed=MAX(sets_time.elapsed, excluded.elapsed), "
                "limit_secs=excluded.limit_secs, submitted=excluded.submitted, submit_ts=excluded.submit_ts",
                (uid, set_no, elapsed, limit, 1 if submitted else 0,
                 now() if submitted else None, bank),
            )
            conn.commit()
            row = conn.execute(
                "SELECT elapsed, limit_secs, submitted FROM sets_time WHERE user_id = ? AND set_no = ? AND bank = ?",
                (uid, set_no, bank),
            ).fetchone()
        finally:
            conn.close()
        self.json({"ok": True, "elapsed": row["elapsed"], "limit": row["limit_secs"],
                   "submitted": bool(row["submitted"])})

    def api_stats(self) -> None:
        uid = self.require_user()
        conn = db()
        try:
            a = conn.execute(
                "SELECT COUNT(*) n, COALESCE(SUM(ok),0) ok, COALESCE(SUM(secs),0) secs "
                "FROM answers WHERE user_id = ?", (uid,)
            ).fetchone()
            wrong = conn.execute(
                "SELECT COUNT(*) FROM wrongs WHERE user_id = ? AND cleared = 0 AND wrong_count > 0",
                (uid,),
            ).fetchone()[0]
            fav = conn.execute("SELECT COUNT(*) FROM marks WHERE user_id = ?", (uid,)).fetchone()[0]
            days = [
                {"day": r["day"], "n": r["n"], "ok": r["ok"], "secs": r["secs"]}
                for r in conn.execute(
                    "SELECT day, n, ok, secs FROM day_stats WHERE user_id = ? ORDER BY day DESC LIMIT 30",
                    (uid,),
                )
            ]
            sets = [
                {"set": r["set_no"], "elapsed": r["elapsed"], "submitted": bool(r["submitted"])}
                for r in conn.execute(
                    "SELECT set_no, elapsed, submitted FROM sets_time WHERE user_id = ? ORDER BY set_no",
                    (uid,),
                )
            ]
        finally:
            conn.close()
        self.json({"ok": True, "done": a["n"], "correct": a["ok"], "secs": a["secs"],
                   "wrong": wrong, "fav": fav, "days": days, "sets": sets})

    def api_reset(self) -> None:
        uid = self.require_user()
        conn = db()
        try:
            for table in ("answers", "marks", "wrongs", "sets_time", "day_stats", "question_log", "drills"):
                conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,))
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})

    # ---------- 分类真题 ----------
    def api_cats(self) -> None:
        data = load_zhenti()
        cats = []
        by_cat = data.get("_by_cat", {})
        for c in data.get("categories", []):
            key = c.get("key")
            cats.append({
                "key": key,
                "name": c.get("name", key),
                "short": c.get("short", ""),
                "count": len(by_cat.get(key, [])),
                "papers": c.get("papers", 0),
                "years": c.get("years", {}),
            })
        self.json({
            "ok": True,
            "meta": data.get("meta", {}),
            "categories": [c for c in cats if c["count"] > 0],
        })

    def api_zhenti(self, query: dict) -> None:
        """按分类取题：cat、n（自选组数）、mode=random|seq、sub、year"""
        uid = self.require_user()
        data = load_zhenti()
        cat = (query.get("cat") or [""])[0].strip()
        if not cat:
            raise ApiError(400, "缺少分类参数 cat")
        pool = data.get("_by_cat", {}).get(cat, [])
        if not pool:
            raise ApiError(404, f"分类 {cat} 暂无题目")

        sub = (query.get("sub") or [""])[0].strip()
        year = (query.get("year") or [""])[0].strip()
        if sub:
            pool = [q for q in pool if q.get("sub") == sub]
        if year:
            pool = [q for q in pool if str(q.get("year")) == year]
        if not pool:
            raise ApiError(404, "该筛选条件下没有题目")

        try:
            n = int((query.get("n") or ["10"])[0])
        except ValueError:
            n = 10
        n = max(1, min(100, n))

        mode = (query.get("mode") or ["random"])[0]
        pool = list(pool)
        if mode == "random":
            random.shuffle(pool)
        picked = pool[:n]

        # 去掉已答过的（可选 avoid=done），不够时用剩余题目补足
        avoid = (query.get("avoid") or [""])[0]
        if avoid == "done":
            conn = db()
            try:
                done = {r["qid"] for r in conn.execute(
                    "SELECT qid FROM answers WHERE user_id = ?", (uid,)
                )}
            finally:
                conn.close()
            fresh = [q for q in pool if q["id"] not in done]
            if len(fresh) >= min(n, len(pool)):
                picked = fresh[:n]
            else:
                picked = (fresh + [q for q in pool if q["id"] in done])[:n]

        # 创建一次练习记录（便于统计与续做）
        conn = db()
        try:
            cur = conn.execute(
                "INSERT INTO drills (user_id, cat, total, qids, created_at) VALUES (?,?,?,?,?)",
                (uid, cat, len(picked), json.dumps([q["id"] for q in picked]), now()),
            )
            drill_id = int(cur.lastrowid)
            conn.commit()
        finally:
            conn.close()

        self.json({
            "ok": True,
            "drill": drill_id,
            "cat": cat,
            "total": len(picked),
            "pool": len(pool),
            "questions": picked,
        })

    def api_drill_start(self) -> None:
        """兼容用：显式创建练习（目前 api_zhenti 已自动创建）。"""
        self.api_zhenti(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query))

    def api_drill_update(self) -> None:
        uid = self.require_user()
        d = self.read_json()
        drill_id = int(d.get("drill") or 0)
        if drill_id <= 0:
            raise ApiError(400, "缺少练习 ID")
        done = max(0, int(d.get("done") or 0))
        correct = max(0, int(d.get("correct") or 0))
        elapsed = max(0, int(d.get("elapsed") or 0))
        finished = bool(d.get("finished"))
        conn = db()
        try:
            row = conn.execute(
                "SELECT id FROM drills WHERE id = ? AND user_id = ?", (drill_id, uid)
            ).fetchone()
            if not row:
                raise ApiError(404, "练习不存在")
            conn.execute(
                "UPDATE drills SET done = ?, correct = ?, elapsed = ?, finished_at = ? WHERE id = ?",
                (done, correct, elapsed, now() if finished else None, drill_id),
            )
            conn.commit()
        finally:
            conn.close()
        self.json({"ok": True})

    def api_drill_list(self) -> None:
        uid = self.require_user()
        conn = db()
        try:
            rows = conn.execute(
                "SELECT id, cat, total, done, correct, elapsed, created_at, finished_at "
                "FROM drills WHERE user_id = ? ORDER BY created_at DESC LIMIT 30", (uid,)
            ).fetchall()
        finally:
            conn.close()
        self.json({"ok": True, "drills": [dict(r) for r in rows]})

    # ---------- 时政资讯 ----------
    def api_news(self, query: dict) -> None:
        """实时抓取时政资讯。

        GET /api/news?limit=30&content=0&timeout=45&force=0
        - limit    每源最多篇数（5-60）
        - content  是否抓正文摘要（1/0）
        - timeout  抓取超时秒数（10-120）
        - force    强制跳过缓存（1/0）
        """
        if not HAS_NEWS_CORE:
            raise ApiError(503, "抓取模块不可用：scripts/news_core.py 未找到")

        def _int(name, default, lo, hi):
            try:
                v = int((query.get(name) or [str(default)])[0])
            except (TypeError, ValueError):
                v = default
            return max(lo, min(v, hi))

        limit = _int("limit", 30, 5, 60)
        timeout = _int("timeout", 45, 10, 120)
        want_content = (query.get("content") or ["0"])[0] in ("1", "true", "yes")
        force = (query.get("force") or ["0"])[0] in ("1", "true", "yes")

        data = news_cache_get(
            limit=limit, content=want_content, timeout=timeout, force=force
        )
        self.json({"ok": True, **data})

    def api_news_status(self) -> None:
        with _NEWS_LOCK:
            age = int(time.time() - _NEWS_CACHE["ts"]) if _NEWS_CACHE["data"] else None
            total = (_NEWS_CACHE["data"] or {}).get("total")
        self.json({
            "ok": True,
            "has_core": HAS_NEWS_CORE,
            "cache_age": age,
            "cached_total": total,
            "ttl": NEWS_CACHE_TTL,
        })

    # ---------- 日志 ----------
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))


class QuizHTTPServer(ThreadingHTTPServer):
    # Windows 下 SO_REUSEADDR 允许两个进程绑同一端口，会让“端口顺延”失效，
    # 因此这里关闭复用，端口被占用时直接绑定失败，再走后面的自动换端口逻辑。
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


def lan_ips() -> list[str]:
    """获取本机所有 IPv4 地址（排除回环与链路本地），用于展示局域网访问地址。"""
    import socket
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def main() -> None:
    ap = argparse.ArgumentParser(description="资料分析刷题后端")
    ap.add_argument("--host", default="0.0.0.0",
                    help="监听地址，0.0.0.0 表示局域网设备也能访问；仅本机用 127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = ap.parse_args()

    init_db()
    os.makedirs(STATIC_DIR, exist_ok=True)

    # 端口被占用时，自动向后找一个空闲端口，避免“打不开”
    httpd = None
    port = args.port
    last_err = None
    for candidate in range(args.port, args.port + 12):
        try:
            httpd = QuizHTTPServer((args.host, candidate), Handler)
            port = candidate
            break
        except OSError as exc:
            last_err = exc
            continue
    if httpd is None:
        print(f"\n[错误] 端口 {args.port}–{args.port + 11} 都被占用：{last_err}")
        print("请换一个端口：python server.py --port 9000 --open\n")
        sys.exit(1)

    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{port}/"
    print("=" * 60)
    print("  资料分析刷题服务已启动")
    print(f"  本机访问：{url}")
    if args.host in ("0.0.0.0", "::"):
        print("  局域网访问（手机/平板连同一 WiFi）：")
        for ip in lan_ips():
            print(f"    http://{ip}:{port}/")
        if not lan_ips():
            print("    （未检测到内网 IP，请确认已联网）")
    if port != args.port:
        print(f"  （端口 {args.port} 被占用，已自动改用 {port}）")
    print(f"  数据库：{DB_PATH}")
    print("  提示：不同 WiFi（跨网络）需内网穿透/公网，见 README「不同网络使用」")
    print("  Ctrl+C 停止")
    print("=" * 60)
    if args.open:
        webbrowser.open(url)
    # 后台预热时政资讯，让前台请求秒开且内容新鲜
    start_news_prewarm()
    if HAS_NEWS_CORE:
        print("  时政资讯：后台自动抓取已启动（每 %d 秒刷新）" % NEWS_PREWARM_INTERVAL)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _NEWS_PREWARM["stop"] = True
        print("\n已停止")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()

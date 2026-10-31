"""在 server.py 中加入 DeepSeek API 代理
目的：把 API Key 从前端移到服务器端，避免开源后被滥用。

前端改为调用 /api/ai/chat，服务器用自己的 key 转发到 DeepSeek。
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "server.py")

s = open(P, encoding="utf-8").read()
orig = s

# ── 1. 头部加常量 ──
OLD1 = """BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "quiz.db")"""

NEW1 = """BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
        DEEPSEEK_API_KEY = open(_AI_KEY_FILE, encoding="utf-8").read().strip()
    except Exception:
        pass"""

if OLD1 in s:
    s = s.replace(OLD1, NEW1)
    print("[1] 已加 DeepSeek 配置常量")
else:
    print("[1] 未匹配常量区")

# ── 2. 加路由 ──
OLD2 = """        if route == "health" and method == "GET":
            self.json({"ok": True, "time": now(), "db": os.path.basename(DB_PATH)})
            return"""

NEW2 = """        if route == "health" and method == "GET":
            self.json({"ok": True, "time": now(), "db": os.path.basename(DB_PATH)})
            return

        # ── AI 代理：把 API Key 留在服务器端，前端不再接触 ──
        if route == "ai/chat" and method == "POST":
            return self.api_ai_chat()
        if route == "ai/status" and method == "GET":
            return self.json({
                "configured": bool(DEEPSEEK_API_KEY),
                "model": "deepseek-chat",
            })"""

if OLD2 in s:
    s = s.replace(OLD2, NEW2)
    print("[2] 已加路由")
else:
    print("[2] 未匹配路由区")

# ── 3. 加处理方法（插在 handle_api 之前）──
OLD3 = """    def handle_api(self, method: str, route: str, query: dict) -> None:"""
NEW3 = '''    def api_ai_chat(self) -> None:
        """代理 DeepSeek chat/completions 请求。

        前端 POST 过来的 body 就是原本要发给 DeepSeek 的 JSON，
        这里补上 Authorization 头再转发，把响应原样返回。
        key 只存在服务器上，开源后也不会泄漏。
        """
        if not DEEPSEEK_API_KEY:
            self.json({
                "error": {
                    "message": "服务器未配置 AI Key。管理员请设置环境变量 "
                               "DEEPSEEK_API_KEY，或在项目目录放 ai_key.txt。"
                }
            }, status=503)
            return

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
                "Authorization": "Bearer " + DEEPSEEK_API_KEY,
            },
            method="POST",
        )

        try:
            with _ur.urlopen(req, timeout=180) as resp:
                raw = resp.read()
                status = resp.status
        except Exception as e:
            # 转发上游错误信息，便于前端排查
            detail = str(e)
            code = 502
            try:
                if hasattr(e, "code"):
                    code = int(e.code)
                if hasattr(e, "read"):
                    body2 = e.read().decode("utf-8", "replace")
                    parsed = json.loads(body2)
                    detail = parsed.get("error", {}).get("message") or body2[:400]
                    self._send(code, body2.encode("utf-8"),
                               "application/json; charset=utf-8")
                    return
            except Exception:
                pass
            self.json({"error": {"message": "AI 调用失败：" + detail}}, status=code)
            return

        self._send(status, raw, "application/json; charset=utf-8")

    def handle_api(self, method: str, route: str, query: dict) -> None:'''

if OLD3 in s:
    s = s.replace(OLD3, NEW3, 1)
    print("[3] 已加 api_ai_chat 方法")
else:
    print("[3] 未匹配 handle_api")

if s != orig:
    open(P, "w", encoding="utf-8").write(s)
    print("\n已写入 server.py")
else:
    print("\n无改动")

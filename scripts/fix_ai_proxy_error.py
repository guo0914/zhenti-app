"""修复 AI 代理的错误转发

问题：
  上游 DeepSeek 返回 402（余额不足），但代理返回 502 且响应体为空。
  原因：urllib 抛出 HTTPError，代码里 e.read() 后把 body2 原样返回，
  但 body2 本身是空的（DeepSeek 的 402 响应体为空），
  于是前端只看到 502 和空内容，无从判断。

修复：
  1. 明确转发上游状态码
  2. 上游响应体为空时，构造可读的错误信息
  3. 针对常见状态码给出中文说明
"""

import sys
import io
import os
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "server.py")

s = open(P, encoding="utf-8").read()

# 替换 except 块
OLD = """        try:
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

        self._send(status, raw, "application/json; charset=utf-8")"""

NEW = '''        try:
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

        self._send(status, raw, "application/json; charset=utf-8")'''

if OLD in s:
    s = s.replace(OLD, NEW)
    open(P, "w", encoding="utf-8").write(s)
    print("已修复代理错误转发")
else:
    print("未匹配，可能是缩进差异")
    i = s.find("with _ur.urlopen")
    print(repr(s[max(0,i - 200):i + 600]))

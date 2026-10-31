"""改造：支持用户自带 API Key（BYOK）

目标：
  每个用户在自己的设备上填自己的 DeepSeek API Key，
  服务器不使用自己的 Key，也不保存用户的 Key。

实现：
  1. 前端设置页恢复 API Key 输入框，存 localStorage（仅本机）
  2. 前端请求 /api/ai/chat 时带上 X-User-Api-Key 头
  3. 服务器优先用用户提供的 Key；没有时才回退到服务器自己的 Key
  4. 服务器不记录、不写入数据库

安全性：
  · 用户 Key 只存在用户自己的 localStorage
  · 通过 HTTPS 传输到服务器再转发给 DeepSeek
  · 服务器不落盘、只用于单次转发
"""

import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "server.py")

s = open(SERVER, encoding="utf-8").read()
orig = s

# ── 1. api_ai_chat：优先用用户提供的 Key ──
OLD = '''        if not DEEPSEEK_API_KEY:
            self.json({
                "error": {
                    "message": "服务器未配置 AI Key。管理员请设置环境变量 "
                               "DEEPSEEK_API_KEY，或在项目目录放 ai_key.txt。"
                }
            }, status=503)
            return'''

NEW = '''        # 优先使用用户自带的 Key（前端通过 X-User-Api-Key 传入）
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
            active_key = ""'''

if OLD in s:
    s = s.replace(OLD, NEW)
    print("[1] api_ai_chat 已支持用户 Key")
else:
    print("[1] 未匹配 Key 检查块")

# ── 2. Authorization 用 active_key ──
OLD2 = '''                "Authorization": "Bearer " + DEEPSEEK_API_KEY,'''
NEW2 = '''                "Authorization": "Bearer " + active_key,'''
if OLD2 in s:
    s = s.replace(OLD2, NEW2)
    print("[2] Authorization 已改用 active_key")
else:
    print("[2] 未匹配 Authorization")

# ── 3. CORS 允许自定义头 ──
OLD3 = '''        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Requested-With")'''
NEW3 = '''        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type,Authorization,X-Requested-With,X-User-Api-Key")'''
if OLD3 in s:
    s = s.replace(OLD3, NEW3)
    print("[3] CORS 已允许 X-User-Api-Key")
else:
    print("[3] 未匹配 CORS")

# ── 4. /api/ai/status 返回是否需要用户填 Key ──
OLD4 = '''        if route == "ai/status" and method == "GET":
            self.json({
                "configured": bool(DEEPSEEK_API_KEY),
                "model": "deepseek-chat",
            })'''
NEW4 = '''        if route == "ai/status" and method == "GET":
            self.json({
                # 服务器自带的 Key（可选，配置了就不用用户填）
                "serverKey": bool(DEEPSEEK_API_KEY),
                # 是否必须用户自己填 Key
                "needUserKey": not bool(DEEPSEEK_API_KEY),
                "model": "deepseek-chat",
            })'''
if OLD4 in s:
    s = s.replace(OLD4, NEW4)
    print("[4] ai/status 已返回 needUserKey")
else:
    print("[4] 未匹配 ai/status")

if s != orig:
    open(SERVER, "w", encoding="utf-8").write(s)
    print("\n已写入 server.py")

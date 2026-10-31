"""
行测刷题 · Windows 桌面应用启动器

作用：
  1. 若后端服务未运行，静默启动 server.py（无黑窗口）
  2. 用 Edge / Chrome 的「应用模式」打开，无地址栏、无标签页，像原生 App
  3. 首次运行自动创建桌面快捷方式

用法：
  双击「行测刷题App.cmd」即可（推荐）
  或 python launch_app.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser

APP_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}/"

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

PYTHONW = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python39", "python.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), ".dsh", "dsh-runtimes",
                 "dsh-primary-runtime", "dependencies", "python", "python.exe"),
]


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex((host, port)) == 0


def find_browser() -> str | None:
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    return None


def check_db() -> str | None:
    """启动前检查 quiz.db 是否可用。返回错误描述，None 表示正常。

    曾经的故障：quiz.db 变成 0 字节后，注册/登录全部返回 500，
    但启动器毫无提示，用户只看到"服务器内部错误"。
    """
    import sqlite3
    db = os.path.join(APP_DIR, "quiz.db")
    if not os.path.exists(db):
        return None  # 不存在没关系，server.py 会建表
    if os.path.getsize(db) == 0:
        # 0 字节 = 上次进程被强杀，WAL 未提交。直接重建即可（空库）
        try:
            os.replace(db, db + ".broken")
            for suffix in ("-wal", "-shm"):
                p = db + suffix
                if os.path.exists(p):
                    os.remove(p)
            return None
        except Exception as e:
            return f"quiz.db 为 0 字节且无法重建：{e}"
    try:
        conn = sqlite3.connect(db, timeout=3)
        conn.execute("SELECT count(*) FROM sqlite_master")
        conn.close()
        return None
    except Exception as e:
        return f"quiz.db 无法读取：{e}（可删除后重建）"


def start_server() -> subprocess.Popen | None:
    """静默启动后端。

    注意：用 python.exe（不是 pythonw.exe）——本机防火墙已放行 python.exe 的入站连接，
    而 pythonw.exe 被 Block 规则拦截，会导致手机/局域网无法访问。
    通过 CREATE_NO_WINDOW 隐藏控制台窗口。
    """
    py = next((p for p in PYTHONW if os.path.exists(p)), None)
    if not py:
        py = sys.executable

    creation = 0
    if os.name == "nt":
        creation = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.Popen(
            [py, "server.py", "--host", "0.0.0.0", "--port", str(PORT)],
            cwd=APP_DIR,
            creationflags=creation,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except Exception:
        return None


def wait_ready(timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if port_open(HOST, PORT):
            return True
        time.sleep(0.3)
    return False


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # 启动前检查数据库，避免"登录显示服务器内部错误"
    db_err = check_db()
    if db_err:
        print("=" * 56)
        print("  数据库异常：", db_err)
        print("=" * 56)

    started = None
    if not port_open(HOST, PORT):
        print("正在启动服务…")
        started = start_server()
        if not wait_ready():
            print("服务启动失败，请手动运行 启动刷题.cmd 查看错误。")
            input("按回车退出…")
            return
        print("服务已就绪。")
    else:
        print("服务已在运行。")

    # 服务起来后验证 API 真能用（登录接口）
    try:
        import json as _json
        import urllib.request as _ur
        req = _ur.Request(f"{URL}api/health")
        with _ur.urlopen(req, timeout=5) as r:
            body = _json.loads(r.read().decode())
        if not body.get("ok"):
            print("警告：服务健康检查未通过。")
    except Exception as e:
        print(f"警告：服务未响应（{e}）")

    browser = find_browser()
    if browser:
        # 应用模式：无地址栏、独立窗口、独立任务栏图标
        args = [
            browser,
            f"--app={URL}",
            "--window-size=1400,900",
            "--user-data-dir=" + os.path.join(APP_DIR, ".appdata"),
            "--no-first-run",
            "--no-default-browser-check",
        ]
        subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        print("已启动应用窗口。")
    else:
        print("未找到 Edge/Chrome，改用默认浏览器打开。")
        webbrowser.open(URL)


if __name__ == "__main__":
    main()

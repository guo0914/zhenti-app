"""
一键内网穿透：用 Cloudflare Quick Tunnel 把本机 8000 端口暴露到公网，
让手机在不同 WiFi / 流量下也能访问。

无需注册账号、无需公网 IP、无需开放防火墙端口。
首次运行会下载 cloudflared.exe（约 40MB），之后秒开。

用法：
    python 穿透.cmd              # 等价于双击 穿透.cmd（下面提供）
    python tunnel.py             # 直接运行本脚本
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED = os.path.join(ROOT, "cloudflared.exe")
PORT = "8000"

# cloudflared 下载源（按优先级，GitHub 直连在这台机器常被限速，走镜像回退）
DOWNLOAD_SOURCES = [
    "https://gh-proxy.com/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    "https://ghfast.top/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    "https://ghproxy.net/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # 1) 确保 cloudflared 存在
    if not os.path.exists(CLOUDFLARED):
        print("首次使用，正在下载 cloudflared（约 55MB，仅此一次）…")
        tmp = CLOUDFLARED + ".part"
        done = False
        for url in DOWNLOAD_SOURCES:
            try:
                print(f"  尝试：{url.split('/')[2]}")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
                    got = 0
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                os.replace(tmp, CLOUDFLARED)
                print(f"下载完成（{got/1048576:.0f} MB）。")
                done = True
                break
            except Exception as exc:
                print(f"  该源失败：{type(exc).__name__}，换下一个…")
                if os.path.exists(tmp):
                    os.remove(tmp)
        if not done:
            print("所有下载源都失败了，可能是网络问题。")
            print("请手动下载 cloudflared-windows-amd64.exe，放到本目录并改名为 cloudflared.exe")
            input("按回车退出…")
            return

    # 2) 启动 Quick Tunnel，指向本机 8000
    print("=" * 60)
    print("  正在建立内网穿透…")
    print("  成功后会出现一个 https://xxx.trycloudflare.com 地址")
    print("  手机（任意网络）打开该地址即可访问刷题服务")
    print("  关闭本窗口即断开穿透。")
    print("=" * 60)
    try:
        proc = subprocess.run(
            [CLOUDFLARED, "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"],
            cwd=ROOT,
        )
        if proc.returncode != 0:
            print()
            print("[说明] 如果上面提示 409 / provisioning failed，")
            print("       说明 Cloudflare 免费即时隧道当前不可用（服务端限制）。")
            print("       备选方案：装 Tailscale（手机装 App、电脑装客户端，")
            print("       两边登录同一账号即可组成虚拟局域网，再访问本机内网 IP）。")
            print("       详见 README「不同网络使用」。")
            input("按回车退出…")
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"启动失败：{exc}")
        input("按回车退出…")


if __name__ == "__main__":
    main()

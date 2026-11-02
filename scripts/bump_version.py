#!/usr/bin/env python3
"""版本指纹工具：把 index.html 里所有资源引用的 ?v= 换成内容哈希

问题背景：
  站点用手写的 ?v=5a1b8c3d2e 这类假哈希做缓存版本号。
  文件改了但哈希没改时，浏览器会用旧缓存，
  表现为 CSS/JS 不生效（布局崩坏、样式丢失）。

用法：
  python scripts/bump_version.py            # 只更新哈希，不动 VER
  python scripts/bump_version.py --ver v3.4 # 同时改版本号
"""

import sys
import io
import os
import re
import hashlib

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IDX = os.path.join(SITE, "index.html")


def file_hash(rel_path):
    """取文件内容的短哈希（前 10 位）。"""
    p = os.path.join(SITE, rel_path)
    if not os.path.isfile(p):
        return None
    h = hashlib.md5(open(p, "rb").read()).hexdigest()[:10]
    return h


def main():
    ver = None
    for a in sys.argv[1:]:
        if a.startswith("--ver"):
            ver = a.split("=", 1)[1] if "=" in a else None

    html = open(IDX, encoding="utf-8").read()

    # 匹配 src="assets/x.js?v=xxx" 与 href="assets/x.css?v=xxx"
    # 同时匹配 ?v=xxx 与 ?build=v5 等任意查询串，
    # 否则历史上写死的 ?build=v5 永远不会被更新（曾导致反复看到旧代码）
    pat = re.compile(
        r'((?:src|href)="((?:assets|data)/[^"?]+))(?:\?[^"]*)?(")'
    )

    changes = []

    def repl(m):
        prefix, rel, quote = m.group(1), m.group(2), m.group(3)
        hv = file_hash(rel)
        if not hv:
            return m.group(0)
        new = f'{prefix}?v={hv}{quote}'
        if m.group(0) != new:
            changes.append((rel, hv))
        return new

    html2 = pat.sub(repl, html)

    # 同步更新 VER 与 data-app-ver
    # 注意：data-app-ver 曾被写死为 v5.0，而 VER 是 v8.0，
    # selfheal.js 的 MY_VERSION 也是 v5.0 —— 三者恒等，
    # 导致「页面版本落后」这条自愈分支永远不触发，自愈机制完全失效。
    # 所以这里必须三处一起改。
    if ver:
        html2 = re.sub(r"var VER = '[^']*'", f"var VER = '{ver}'", html2)
        html2 = re.sub(r'data-app-ver="[^"]*"', f'data-app-ver="{ver}"', html2)

    open(IDX, "w", encoding="utf-8").write(html2)

    print("=" * 60)
    print("资源版本指纹更新")
    print("=" * 60)
    if changes:
        for rel, hv in changes:
            print(f"  {rel}  →  ?v={hv}")
    else:
        print("  所有引用已是最新，无需改动")
    if ver:
        print(f"\n  VER 设为 {ver}")

    # 同步 selfheal.js 的 MY_VERSION（自愈机制的判据，必须与页面版本一致演进）
    shp = os.path.join(SITE, "assets", "selfheal.js")
    if ver and os.path.isfile(shp):
        sh = open(shp, encoding="utf-8").read()
        sh2 = re.sub(r"var MY_VERSION = '[^']*'", f"var MY_VERSION = '{ver}'", sh)
        if sh2 != sh:
            open(shp, "w", encoding="utf-8").write(sh2)
            print(f"  selfheal.js MY_VERSION → {ver}")

    # 同步 sw.js 的 CACHE 名
    swp = os.path.join(SITE, "sw.js")
    sw = open(swp, encoding="utf-8").read()
    m = re.search(r"const CACHE = 'zlfx-data-v([\d.]+)'", sw)
    target = ver.lstrip("v") if ver else None
    if target and m and m.group(1) != target:
        sw = re.sub(r"const CACHE = 'zlfx-data-v[\d.]+'",
                    f"const CACHE = 'zlfx-data-v{target}'", sw)
        open(swp, "w", encoding="utf-8").write(sw)
        print(f"  sw.js CACHE → zlfx-data-v{target}")


if __name__ == "__main__":
    main()

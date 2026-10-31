"""
下载题目引用的图片（题目图 / 公式图）。

图片同样走 api.github.com（唯一稳定通道），每次请求消耗 1 次配额，
因此与文字抓取共用 60 次/小时额度。本脚本按「题目图优先、公式图其次」排序，
并支持断点续传。

用法：
    python fetch_images.py                 # 下载当前题库引用的全部图片
    python fetch_images.py --only-timu      # 只下题目图（图形推理用）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_CONTENT = "https://api.github.com/repos/ERRRC/xingcezhenti/contents/{path}?ref=main"
API_RATE = "https://api.github.com/rate_limit"
BASE = "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "cache")
IMG_DIR = os.path.join(ROOT, "site", "assets", "zt")     # 给前端用的图片目录
ZHENTI = os.path.join(ROOT, "site", "data", "zhenti.json")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rate_left() -> tuple[int, int]:
    try:
        req = urllib.request.Request(API_RATE, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        core = d.get("resources", {}).get("core", {})
        return int(core.get("remaining", 0)), int(core.get("reset", 0))
    except Exception:
        return 0, int(time.time()) + 600


def fetch(path: str) -> bytes | None:
    url = API_CONTENT.format(path=urllib.parse.quote(path))
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/vnd.github.raw",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            return b"__RATELIMIT__"
        return None
    except Exception:
        return None


def collect_images() -> tuple[list[str], list[str]]:
    """从已解析的题库里收集图片相对路径，分成题目图与公式图。"""
    if not os.path.exists(ZHENTI):
        raise SystemExit("缺少 site/data/zhenti.json，请先运行 parse_zhenti.py")
    data = json.load(open(ZHENTI, encoding="utf-8"))
    timu, formula = set(), set()
    for q in data.get("questions", []):
        for src in q.get("imgs", []) or []:
            name = os.path.basename(src)
            if "题目图" in src:
                timu.add(name)
            elif "公式图" in src:
                formula.add(name)
    return sorted(timu), sorted(formula)


def local_path(kind: str, name: str) -> str:
    return os.path.join(IMG_DIR, kind, name)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-timu", action="store_true", help="只下载题目图")
    ap.add_argument("--max-rounds", type=int, default=20)
    args = ap.parse_args()

    timu, formula = collect_images()
    tasks: list[tuple[str, str, str]] = []
    for n in timu:
        tasks.append(("题目图", n, f"90-图片/题目图/{n}"))
    if not args.only_timu:
        for n in formula:
            tasks.append(("公式图", n, f"90-图片/公式图/{n}"))

    def done(kind, name):
        p = local_path(kind, name)
        return os.path.exists(p) and os.path.getsize(p) > 0

    pending = [t for t in tasks if not done(t[0], t[1])]
    log(f"图片引用：题目图 {len(timu)}，公式图 {len(formula)}；待下载 {len(pending)}")

    round_no = 0
    while pending and round_no < args.max_rounds:
        round_no += 1
        left, reset = rate_left()
        log(f"第 {round_no} 轮：配额 {left}，重置 "
            f"{time.strftime('%H:%M:%S', time.localtime(reset))}")
        if left <= 2:
            wait = max(30, reset - int(time.time()) + 15)
            log(f"等待 {wait/60:.0f} 分钟…")
            time.sleep(min(wait, 3700))
            continue

        got = 0
        while pending and left > 2:
            kind, name, rel = pending[0]
            data = fetch(rel)
            if data == b"__RATELIMIT__":
                log("触发限流")
                break
            if data and data[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"GIF8"):
                dst = local_path(kind, name)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as fh:
                    fh.write(data)
                pending.pop(0)
                got += 1
                left -= 1
                if got % 10 == 0:
                    log(f"  {got} 张，剩余 {len(pending)}")
            else:
                pending.append(pending.pop(0))
                left -= 1
        log(f"本轮 {got} 张，剩余 {len(pending)}")
        if got == 0 and pending:
            left, reset = rate_left()
            wait = max(60, reset - int(time.time()) + 20)
            log(f"无进展，等待 {wait/60:.0f} 分钟")
            time.sleep(min(wait, 3700))

    log(f"结束：剩余 {len(pending)} 张" + ("，可重跑续传" if pending else "，全部完成"))
    # 统计
    n_t = len(os.listdir(os.path.join(IMG_DIR, "题目图"))) if os.path.isdir(os.path.join(IMG_DIR, "题目图")) else 0
    n_f = len(os.listdir(os.path.join(IMG_DIR, "公式图"))) if os.path.isdir(os.path.join(IMG_DIR, "公式图")) else 0
    log(f"本地已有：题目图 {n_t}，公式图 {n_f}")


if __name__ == "__main__":
    main()

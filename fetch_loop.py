"""
分段抓取器：GitHub 未登录 API 每小时只有 60 次配额，
本脚本会在配额耗尽时自动等待到重置，然后继续，直到抓完目标文件。

用法：
    python fetch_loop.py                      # 抓国考+主要省考，2023-2026
    python fetch_loop.py --cat 03-言语理解与表达 04-数量关系

配合 parse_zhenti.py 使用：
    python fetch_loop.py && python parse_zhenti.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"
API_CONTENT = "https://api.github.com/repos/ERRRC/xingcezhenti/contents/{path}?ref=main"
API_RATE = "https://api.github.com/rate_limit"
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "cache")
MANIFEST = os.path.join(ROOT, "manifest.json")

CATEGORIES = [
    "01-政治理论", "02-常识判断", "03-言语理解与表达",
    "04-数量关系", "05-判断推理", "06-资料分析",
]
KEYWORDS = ["国家公务员", "联考", "山东", "江苏", "浙江", "广东", "四川"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rate_left() -> tuple[int, int]:
    """返回 (剩余次数, 重置时间戳)。"""
    try:
        req = urllib.request.Request(API_RATE, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        core = d.get("resources", {}).get("core", {})
        return int(core.get("remaining", 0)), int(core.get("reset", 0))
    except Exception:
        return 0, int(time.time()) + 600


def fetch_via_api(rel: str) -> bytes | None:
    url = API_CONTENT.format(path=urllib.parse.quote(rel))
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


def fetch_via_raw(rel: str, timeout: int = 40) -> bytes | None:
    try:
        req = urllib.request.Request(BASE + urllib.parse.quote(rel),
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def target_files(cats: list[str], years: set[int]) -> list[tuple[str, str]]:
    if not os.path.exists(MANIFEST):
        raise SystemExit("缺少 manifest.json，请先运行 fetch_zhenti.py 生成清单")
    man = json.load(open(MANIFEST, encoding="utf-8"))
    out = []
    for cat in cats:
        for f in man.get(cat, {}).get("files", []):
            if f["year"] not in years:
                continue
            if not any(k in f["name"] for k in KEYWORDS):
                continue
            out.append((cat, f["name"]))
    return out


def save(cat: str, name: str, data: bytes) -> None:
    dst = os.path.join(CACHE, cat, name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dst)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", nargs="*", default=CATEGORIES)
    ap.add_argument("--years", nargs="*", type=int, default=[2023, 2024, 2025, 2026])
    ap.add_argument("--max-rounds", type=int, default=12, help="最多等几轮配额")
    args = ap.parse_args()

    todo = target_files(args.cat, set(args.years))
    # 已有文件跳过
    def exists(cat, name):
        p = os.path.join(CACHE, cat, name)
        return os.path.exists(p) and os.path.getsize(p) > 0

    pending = [(c, n) for c, n in todo if not exists(c, n)]
    log(f"目标 {len(todo)} 个文件，已完成 {len(todo)-len(pending)}，待抓 {len(pending)}")

    round_no = 0
    while pending and round_no < args.max_rounds:
        round_no += 1
        left, reset = rate_left()
        log(f"第 {round_no} 轮：配额剩余 {left}，重置于 "
            f"{time.strftime('%H:%M:%S', time.localtime(reset))}")

        if left <= 2:
            wait = max(30, reset - int(time.time()) + 20)
            log(f"配额不足，等待 {wait/60:.0f} 分钟…")
            time.sleep(min(wait, 3700))
            continue

        progressed = 0
        while pending and left > 2:
            cat, name = pending[0]
            rel = f"{cat}/{name}"
            data = fetch_via_api(rel)
            if data == b"__RATELIMIT__":
                log("触发限流，暂停本轮")
                break
            if not data:
                # API 失败，试 raw（不耗配额）
                data = fetch_via_raw(rel)
            if data:
                save(cat, name, data)
                pending.pop(0)
                progressed += 1
                left -= 1
                if progressed % 10 == 0:
                    log(f"  已抓 {progressed}，剩余 {len(pending)}")
            else:
                # 连续失败，先跳过，留到下一轮
                pending.append(pending.pop(0))
                left -= 1
                if left <= 2:
                    break
        log(f"本轮完成 {progressed} 个，待抓 {len(pending)}")
        if not pending:
            break
        if progressed == 0:
            left, reset = rate_left()
            wait = max(60, reset - int(time.time()) + 30)
            log(f"本轮无进展，等待 {wait/60:.0f} 分钟后继续")
            time.sleep(min(wait, 3700))

    log(f"结束：仍待抓 {len(pending)} 个" + ("，可再次运行本脚本继续" if pending else "，已全部完成"))


if __name__ == "__main__":
    main()

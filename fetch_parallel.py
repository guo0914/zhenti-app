"""
并行抓取器（走 raw.githubusercontent.com，不消耗 GitHub API 配额）。

该通道在本机不稳定（约 80% 成功、单线程 2KB/s），但配合小并发
（3 线程）后吞吐明显优于 API 通道，且不受 60 次/小时限制。

用法：
    python fetch_parallel.py                 # 补全所有缺失文件
    python fetch_parallel.py --workers 4
    python fetch_parallel.py --cat 03-言语理解与表达 04-数量关系
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"
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


def dst_of(cat: str, name: str) -> str:
    return os.path.join(CACHE, cat, name)


def exists(cat: str, name: str) -> bool:
    p = dst_of(cat, name)
    return os.path.exists(p) and os.path.getsize(p) > 0


def fetch_one(cat: str, name: str, tries: int = 3) -> tuple[str, int]:
    if exists(cat, name):
        return "skip", 0
    rel = f"{cat}/{name}"
    url = BASE + urllib.parse.quote(rel)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if not data:
                raise ValueError("empty")
            dst = dst_of(cat, name)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dst)
            return "ok", len(data)
        except Exception:
            if attempt == tries - 1:
                return "fail", 0
            time.sleep(0.8 * (attempt + 1))
    return "fail", 0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--cat", nargs="*", default=CATEGORIES)
    ap.add_argument("--years", nargs="*", type=int, default=[2023, 2024, 2025, 2026])
    ap.add_argument("--rounds", type=int, default=3, help="失败重试轮数")
    args = ap.parse_args()

    man = json.load(open(MANIFEST, encoding="utf-8"))
    years = set(args.years)

    tasks: list[tuple[str, str]] = []
    for cat in args.cat:
        for f in man.get(cat, {}).get("files", []):
            if f["year"] not in years:
                continue
            if not any(k in f["name"] for k in KEYWORDS):
                continue
            tasks.append((cat, f["name"]))

    pending = [t for t in tasks if not exists(*t)]
    log(f"目标 {len(tasks)}，已完成 {len(tasks)-len(pending)}，待抓 {len(pending)}")

    for rnd in range(1, args.rounds + 1):
        if not pending:
            break
        log(f"第 {rnd} 轮，{len(pending)} 个，并发 {args.workers}")
        ok = fail = 0
        started = time.time()
        remaining: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(fetch_one, c, n): (c, n) for c, n in pending}
            for i, fut in enumerate(as_completed(futs), 1):
                status, _ = fut.result()
                if status == "ok":
                    ok += 1
                elif status == "skip":
                    pass
                else:
                    fail += 1
                    remaining.append(futs[fut])
                if i % 20 == 0:
                    el = time.time() - started
                    log(f"  {i}/{len(pending)} ok={ok} fail={fail} "
                        f"{i/el:.2f} 文件/s 剩余约 {(len(pending)-i)/max(0.01, i/el)/60:.0f} 分钟")
        log(f"第 {rnd} 轮完成：成功 {ok}，失败 {fail}")
        pending = remaining
        if pending and rnd < args.rounds:
            log(f"等待 20 秒后重试 {len(pending)} 个")
            time.sleep(20)

    log(f"结束：待抓 {len(pending)}" + ("（可重跑续传）" if pending else "，已补齐"))


if __name__ == "__main__":
    main()

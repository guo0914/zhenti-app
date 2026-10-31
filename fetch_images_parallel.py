"""
并行下载题目图片（走 raw.githubusercontent.com，不消耗 API 配额）。

图形推理必须依赖图片；公式图仅用于解析展示，可按需再下。

用法：
    python fetch_images_parallel.py                 # 题目图 + 公式图
    python fetch_images_parallel.py --only-timu     # 只下题目图
    python fetch_images_parallel.py --workers 4
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
IMG_DIR = os.path.join(ROOT, "site", "assets", "zt")
ZHENTI = os.path.join(ROOT, "site", "data", "zhenti.json")
MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def collect() -> tuple[list[str], list[str]]:
    data = json.load(open(ZHENTI, encoding="utf-8"))
    timu, formula = set(), set()
    for q in data.get("questions", []):
        for src in (q.get("imgs") or []):
            name = os.path.basename(src)
            if "题目图" in src:
                timu.add(name)
            elif "公式图" in src:
                formula.add(name)
    return sorted(timu), sorted(formula)


def dst_of(kind: str, name: str) -> str:
    return os.path.join(IMG_DIR, kind, name)


def exists(kind: str, name: str) -> bool:
    p = dst_of(kind, name)
    return os.path.exists(p) and os.path.getsize(p) > 0


def fetch_one(kind: str, name: str, tries: int = 3) -> tuple[str, int]:
    if exists(kind, name):
        return "skip", 0
    rel = f"90-图片/{kind}/{name}"
    url = BASE + urllib.parse.quote(rel)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if not data or not any(data.startswith(m) for m in MAGIC):
                raise ValueError("not an image")
            dst = dst_of(kind, name)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dst)
            return "ok", len(data)
        except Exception:
            if attempt == tries - 1:
                return "fail", 0
            time.sleep(0.6 * (attempt + 1))
    return "fail", 0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-timu", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    timu, formula = collect()
    tasks = [("题目图", n) for n in timu]
    if not args.only_timu:
        tasks += [("公式图", n) for n in formula]

    pending = [t for t in tasks if not exists(*t)]
    log(f"题目图 {len(timu)}，公式图 {len(formula)}；待下载 {len(pending)}")

    for rnd in range(1, args.rounds + 1):
        if not pending:
            break
        log(f"第 {rnd} 轮，{len(pending)} 张，并发 {args.workers}")
        ok = fail = 0
        started = time.time()
        remaining: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(fetch_one, k, n): (k, n) for k, n in pending}
            for i, fut in enumerate(as_completed(futs), 1):
                status, _ = fut.result()
                if status == "ok":
                    ok += 1
                elif status == "fail":
                    fail += 1
                    remaining.append(futs[fut])
                if i % 25 == 0:
                    el = time.time() - started
                    log(f"  {i}/{len(pending)} ok={ok} fail={fail} "
                        f"{i/el:.2f} 张/s 剩余约 {(len(pending)-i)/max(0.01, i/el)/60:.0f} 分钟")
        log(f"第 {rnd} 轮：成功 {ok}，失败 {fail}")
        pending = remaining
        if pending and rnd < args.rounds:
            time.sleep(15)

    n_t = len(os.listdir(os.path.join(IMG_DIR, "题目图"))) if os.path.isdir(os.path.join(IMG_DIR, "题目图")) else 0
    n_f = len(os.listdir(os.path.join(IMG_DIR, "公式图"))) if os.path.isdir(os.path.join(IMG_DIR, "公式图")) else 0
    log(f"结束：待下 {len(pending)}；本地题目图 {n_t}，公式图 {n_f}")


if __name__ == "__main__":
    main()

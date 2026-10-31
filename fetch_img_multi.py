"""
下载题目/公式图片（多镜像回退，不消耗 GitHub API 配额）。

本机到 raw.githubusercontent.com 经常超时（15s+ 甚至失败），
实测 ghfast.top 镜像只需 1.6s，因此按 ghfast → gh-proxy → ghproxy.net → raw 的顺序回退。

用法：
    python fetch_img_multi.py                # 题目图 + 公式图
    python fetch_img_multi.py --only-timu    # 只下题目图
    python fetch_img_multi.py --workers 8
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT, "site", "assets", "zt")
DATA = os.path.join(ROOT, "site", "data", "zt")

REL = "90-图片/{kind}/{name}"

MIRRORS = [
    "https://ghfast.top/https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/{q}",
    "https://gh-proxy.com/https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/{q}",
    "https://ghproxy.net/https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/{q}",
    "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/{q}",
]

MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")

_lock = threading.Lock()
_stats = {"ok": 0, "fail": 0}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def collect(only_timu: bool) -> list[tuple[str, str]]:
    """从各分类分片中收集引用到的图片文件名（含题干、材料、解析里的公式图）。"""
    timu, formula = set(), set()
    for fn in os.listdir(DATA):
        if not fn.endswith(".json"):
            continue
        try:
            arr = json.load(open(os.path.join(DATA, fn), encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(arr, list):
            continue
        for q in arr:
            for src in (q.get("imgs") or []):
                n = os.path.basename(src)
                (timu if "题目图" in src else formula).add(n)
            for src in (q.get("materialImgs") or []):
                n = os.path.basename(src)
                (timu if "题目图" in src else formula).add(n)
            # 解析里以 markdown 图片语法保留的公式图
            for m in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", q.get("explain") or ""):
                n = os.path.basename(m)
                if n:
                    (timu if "题目图" in m else formula).add(n)
    out = [("题目图", n) for n in sorted(timu)]
    if not only_timu:
        out += [("公式图", n) for n in sorted(formula)]
    return out


def dst_of(kind: str, name: str) -> str:
    return os.path.join(IMG_DIR, kind, name)


def exists(kind: str, name: str) -> bool:
    p = dst_of(kind, name)
    return os.path.exists(p) and os.path.getsize(p) > 0


def fetch_url(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def fetch_one(kind: str, name: str) -> tuple[str, int]:
    if exists(kind, name):
        return "skip", 0
    rel = REL.format(kind=kind, name=name)
    q = urllib.parse.quote(rel)
    for tmpl in MIRRORS:
        data = fetch_url(tmpl.format(q=q))
        if data and any(data.startswith(m) for m in MAGIC):
            dst = dst_of(kind, name)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + ".part"
            with open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dst)
            return "ok", len(data)
    return "fail", 0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-timu", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=4)
    args = ap.parse_args()

    tasks = collect(args.only_timu)
    pending = [t for t in tasks if not exists(*t)]
    log(f"引用图片 {len(tasks)}，已有 {len(tasks)-len(pending)}，待下载 {len(pending)}")

    for rnd in range(1, args.rounds + 1):
        if not pending:
            break
        log(f"第 {rnd} 轮：{len(pending)} 张，并发 {args.workers}")
        ok = fail = 0
        started = time.time()
        remaining: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(fetch_one, k, n): (k, n) for k, n in pending}
            for i, fut in enumerate(as_completed(futs), 1):
                try:
                    status, _ = fut.result()
                except Exception:
                    status = "fail"
                if status == "ok":
                    ok += 1
                elif status == "fail":
                    fail += 1
                    remaining.append(futs[fut])
                if i % 20 == 0:
                    el = time.time() - started
                    log(f"  {i}/{len(pending)} ok={ok} fail={fail} "
                        f"{i/el:.2f} 张/s 剩余约 {(len(pending)-i)/max(0.01, i/el)/60:.0f} 分钟")
        log(f"第 {rnd} 轮：成功 {ok}，失败 {fail}")
        pending = remaining
        if pending and rnd < args.rounds:
            time.sleep(5)

    n_t = len(os.listdir(os.path.join(IMG_DIR, "题目图"))) if os.path.isdir(os.path.join(IMG_DIR, "题目图")) else 0
    n_f = len(os.listdir(os.path.join(IMG_DIR, "公式图"))) if os.path.isdir(os.path.join(IMG_DIR, "公式图")) else 0
    log(f"结束：待下 {len(pending)}；本地 题目图 {n_t}，公式图 {n_f}")


if __name__ == "__main__":
    main()

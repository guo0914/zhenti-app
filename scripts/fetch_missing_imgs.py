# -*- coding: utf-8 -*-
"""下载 8 个分片里被引用但本地缺失的图片（含 explain 内联图）。

fetch_images_parallel.py 只扫描 site/data/zhenti.json 的 q.imgs，
该文件早已删除（数据改成 zt/<cat>.json 分片），且不覆盖 explain 里的图，
所以解析图还原后新引用的 312 张全部缺失。本脚本直接扫分片。

用法：
  python scripts/fetch_missing_imgs.py --dry-run
  python scripts/fetch_missing_imgs.py --workers 8
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
IMG_DIR = os.path.join(ROOT, "site", "assets", "zt")
CATS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]
BASE = "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"
MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF")
MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

# 远程仓库目录名（中文，不能改）→ 本地目录名（ASCII，iOS 打包必须）
LOCAL_DIR = {"题目图": "timu", "公式图": "formula"}


def collect():
    """返回 [(kind, name)] 未去重的引用列表。kind 是本地 ASCII 目录名。"""
    refs = set()
    for cat in CATS:
        fp = os.path.join(ZT, cat + ".json")
        if not os.path.exists(fp):
            continue
        data = json.load(io.open(fp, encoding="utf-8"))
        for q in data:
            srcs = []
            srcs.extend(q.get("imgs") or [])
            srcs.extend([s for s in (q.get("optionImgs") or []) if s])
            srcs.extend([s for s in (q.get("materialImgs") or []) if s])
            # stemHtml / optionHtml 里的 <img src=...>
            for f in ("stemHtml", "optionHtml"):
                v = q.get(f)
                if isinstance(v, str):
                    srcs.extend(re.findall(r'<img[^>]*src="([^"]+)"', v, re.I))
                elif isinstance(v, list):
                    for it in v:
                        if isinstance(it, str):
                            srcs.extend(re.findall(r'<img[^>]*src="([^"]+)"', it, re.I))
            # explain 里的 markdown 图片
            srcs.extend([m[1] for m in MD_IMG.findall(q.get("explain") or "")])
            for s in srcs:
                s = str(s).replace("\\", "/")
                if "/timu/" in s or "题目图" in s:
                    refs.add(("timu", os.path.basename(s)))
                elif "/formula/" in s or "公式图" in s:
                    refs.add(("formula", os.path.basename(s)))
    return sorted(refs)


def dst_of(kind, name):
    return os.path.join(IMG_DIR, kind, name)


def missing(refs):
    out = []
    for kind, name in refs:
        p = dst_of(kind, name)
        if not (os.path.exists(p) and os.path.getsize(p) > 0):
            out.append((kind, name))
    return out


def fetch_one(kind, name, tries=3):
    # 远程仓库是中文目录，本地是 ASCII 目录
    remote_kind = "题目图" if kind == "timu" else "公式图"
    rel = "90-图片/%s/%s" % (remote_kind, name)
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
            with io.open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dst)
            return "ok", len(data)
        except Exception as e:
            if attempt == tries - 1:
                return "fail:%s" % type(e).__name__, 0
            time.sleep(0.6 * (attempt + 1))
    return "fail", 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    refs = collect()
    pend = missing(refs)
    print("引用去重 %d 张，本地缺失 %d 张" % (len(refs), len(pend)))
    if args.dry_run or not pend:
        return

    for rnd in range(1, args.rounds + 1):
        if not pend:
            break
        print("第 %d 轮：%d 张，并发 %d" % (rnd, len(pend), args.workers))
        ok = 0
        remain = []
        started = time.time()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(fetch_one, k, n): (k, n) for k, n in pend}
            for i, fut in enumerate(as_completed(futs), 1):
                status, _ = fut.result()
                if status == "ok":
                    ok += 1
                else:
                    remain.append(futs[fut])
                if i % 50 == 0:
                    el = time.time() - started
                    print("  %d/%d ok=%d fail=%d %.1f 张/s" % (
                        i, len(pend), ok, len(remain), i / max(0.01, el)))
        print("第 %d 轮结束：成功 %d，失败 %d" % (rnd, ok, len(remain)))
        pend = remain
        if pend and rnd < args.rounds:
            time.sleep(10)

    print("最终仍缺失 %d 张" % len(pend))
    if pend:
        with io.open(os.path.join(ROOT, "_missing_imgs.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join("%s/%s" % (k, n) for k, n in pend))
        print("清单 -> _missing_imgs.txt")


if __name__ == "__main__":
    main()

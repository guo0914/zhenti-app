"""
从 ERRRC/xingcezhenti 抓取 2023-2026 年行测真题。

策略：
  - 断点续传：已下载的文件记录在 cache/ 下，重跑跳过
  - 串行 + 少量并发（6），失败重试 4 次，指数退避
  - 只抓 2023 及以后的卷子
  - 图片不在此阶段下载，后续按需（题目引用的题图/公式图）单独处理

用法：
    python fetch_zhenti.py            # 抓全部
    python fetch_zhenti.py --years 2024 2025
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
# 本机到 raw.githubusercontent.com 的 TCP 握手要 8 秒以上（几乎不可用），
# 而 api.github.com 正常，因此优先走 contents API 取原始内容。
API_CONTENT = "https://api.github.com/repos/ERRRC/xingcezhenti/contents/{path}?ref=main"
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "cache")
MANIFEST = os.path.join(ROOT, "manifest.json")

CATEGORIES = [
    "01-政治理论",
    "02-常识判断",
    "03-言语理解与表达",
    "04-数量关系",
    "05-判断推理",
    "06-资料分析",
]

# 各分类目录下的 git tree sha（2026-09 抓取时取得，用于列目录）
TREE_SHA = {
    "01-政治理论": "55b21f00",
    "02-常识判断": "2100a497",
    "03-言语理解与表达": "aa13b7ea",
    "04-数量关系": "429af3de",
    "05-判断推理": "38c5cd9e",
    "06-资料分析": "14af77d1",
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def http_get(url: str, tries: int = 4, timeout: int = 30) -> bytes | None:
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            if attempt == tries - 1:
                log(f"  FAIL {url.split('/')[-1][:40]} ({type(exc).__name__})")
                return None
            time.sleep(1.2 * (attempt + 1))
    return None


def list_category(cat: str) -> list[dict]:
    """用 git tree API 列出某分类目录下的 md 文件。"""
    sha = TREE_SHA[cat]
    url = f"https://api.github.com/repos/ERRRC/xingcezhenti/git/trees/{sha}"
    raw = http_get(url, tries=5, timeout=60)
    if not raw:
        raise RuntimeError(f"无法列出目录 {cat}")
    data = json.loads(raw)
    out = []
    for item in data.get("tree", []):
        if item.get("type") != "blob":
            continue
        name = item["path"]
        if not name.endswith(".md"):
            continue
        year = name[:4]
        if not year.isdigit():
            continue
        out.append({"name": name, "year": int(year), "size": item.get("size", 0)})
    return out


def safe_name(cat: str, name: str) -> str:
    """把分类/文件名映射成缓存路径。"""
    return os.path.join(CACHE, cat, name)


def fetch_one(cat: str, name: str) -> tuple[str, int]:
    """下载单个 md 到缓存，返回 (状态, 字节数)。"""
    dst = safe_name(cat, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return "skip", os.path.getsize(dst)

    rel = f"{cat}/{name}"
    data = None
    # 1) 首选 contents API（本机唯一稳定的通道）
    url = API_CONTENT.format(path=urllib.parse.quote(rel))
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/vnd.github.raw",
            })
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
            if data and data[:3] != b"eyJ":      # 不是 base64 JSON
                break
            data = None
        except Exception:
            data = None
            time.sleep(1.0 + attempt)

    # 2) 回退 raw（慢，但偶尔能用）
    if not data:
        data = http_get(BASE + urllib.parse.quote(rel), tries=2, timeout=30)

    if not data:
        return "fail", 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, dst)
    return "ok", len(data)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int, default=[2023, 2024, 2025, 2026])
    ap.add_argument("--workers", type=int, default=1, help="并发数；网络差时保持 1")
    ap.add_argument("--only", nargs="*", default=None,
                    help="只抓卷名包含这些关键词的（如 国家公务员 联考 山东）")
    args = ap.parse_args()

    years = set(args.years)
    os.makedirs(CACHE, exist_ok=True)

    log(f"目标年份: {sorted(years)}")
    if args.only:
        log(f"关键词过滤: {args.only}")

    manifest = {}
    if os.path.exists(MANIFEST):
        try:
            manifest = json.load(open(MANIFEST, encoding="utf-8"))
        except Exception:
            manifest = {}

    tasks = []
    for cat in CATEGORIES:
        if cat in manifest and manifest[cat].get("files"):
            files = manifest[cat]["files"]
            log(f"{cat}: 用已有清单 {len(files)} 个文件")
        else:
            try:
                files = list_category(cat)
            except Exception as exc:
                log(f"{cat}: 列目录失败 {exc}")
                continue
            manifest[cat] = {"years": sorted(years), "files": files}
            log(f"{cat}: 共 {len(files)} 个文件")
            with open(MANIFEST, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=1)

        picked = [f for f in files if f["year"] in years]
        if args.only:
            picked = [f for f in picked if any(k in f["name"] for k in args.only)]
        log(f"{cat}: 命中 {len(picked)} 个")
        tasks.extend((cat, f["name"]) for f in picked)

    log(f"待下载 {len(tasks)} 个文件")

    # 2) 并发下载
    done = skip = fail = 0
    total_bytes = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_one, cat, name): (cat, name) for cat, name in tasks}
        for idx, fut in enumerate(as_completed(futures), 1):
            status, size = fut.result()
            if status == "ok":
                done += 1
                total_bytes += size
            elif status == "skip":
                skip += 1
                total_bytes += size
            else:
                fail += 1
            if idx % 20 == 0 or idx == len(tasks):
                elapsed = time.time() - started
                rate = idx / elapsed if elapsed > 0 else 0
                remain = (len(tasks) - idx) / rate if rate > 0 else 0
                log(f"进度 {idx}/{len(tasks)}  new={done} skip={skip} fail={fail} "
                    f"{total_bytes/1048576:.1f}MB {rate:.2f}文件/s 预计剩余 {remain/60:.0f} 分钟")

    log(f"完成：新下载 {done}，跳过 {skip}，失败 {fail}，共 {total_bytes/1048576:.1f} MB")
    if fail:
        log("存在失败文件，重跑本脚本会自动续传")


if __name__ == "__main__":
    main()

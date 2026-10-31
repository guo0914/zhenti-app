#!/usr/bin/env python3
"""抓取多源时政资讯，生成 site/data/news.js（离线缓存快照）。

实时更新由 serve.py 的 /api/news 接口负责，此脚本用于：
  1. 生成首次访问的本地缓存
  2. 在无服务器环境（如纯静态托管）下提供数据

用法：
  python scripts/fetch_news.py                  # 只抓标题（约 6 秒）
  python scripts/fetch_news.py --fetch-content  # 附带正文摘要（约 8 分钟）
  python scripts/fetch_news.py --only qsyw,cctv # 只抓指定源
"""

import json, os, sys, io
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from news_core import fetch_all, SOURCES

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "data", "news.js")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="多源时政资讯抓取")
    ap.add_argument("--fetch-content", action="store_true", help="附带正文摘要（慢）")
    ap.add_argument("--only", default="", help="只抓指定源 id（逗号分隔）")
    ap.add_argument("--max", type=int, default=30, help="每源最多文章数")
    args = ap.parse_args()

    only = [x.strip() for x in args.only.split(",") if x.strip()]
    picked = [s for s in SOURCES if not only or s["id"] in only]

    print("=" * 58)
    print(f"多源时政聚合 · {len(picked)} 个源 · 每源上限 {args.max}")
    print("=" * 58)

    def progress(name, n):
        print(f"   {name}: {n} 篇")

    data = fetch_all(
        sources=only or None,
        fetch_content_flag=args.fetch_content,
        max_per=args.max,
        content_limit=400,
        on_progress=progress,
    )

    js = f"""/* ===== 多源时政资讯缓存 =====
 * 由 scripts/fetch_news.py 自动生成 — {data['updated']}
 * 来源: {'、'.join(s['name'] for s in data['sources'])}
 * 总数: {data['total']} 篇 / {len(data['sources'])} 个来源 / {len(data['topics'])} 个话题
 *
 * 注：页面会优先通过 /api/news 实时抓取；此文件作为离线降级数据。
 */

window.__NEWS__ = """
    js += json.dumps(data, ensure_ascii=False, indent=2)
    js += ";\n"

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(js)

    print("\n" + "=" * 58)
    print(f"[DONE] {data['total']} 篇 · 耗时 {data['elapsed']}s -> {OUTPUT}")
    print("  来源: " + ", ".join("%s %d" % (s["name"], s["count"]) for s in data["sources"]))
    print("  话题: " + ", ".join("%s(%d)" % (t["name"], t["count"]) for t in data["topics"][:8]))
    print(f"  更新: {data['updated']}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""把图片目录改成纯 ASCII 名，彻底解决跨平台编码问题。

背景（2026-11-02 手机 App 全部图片不显示）：
  site/assets/zt/题目图、site/assets/zt/公式图 是中文目录名。
  GitHub Actions 的 macOS 上用 `zip -r -q App-unsigned.ipa Payload` 打包，
  zip 条目名写的是 UTF-8 字节但**没有置 UTF-8 标志位（flag 0x800）**，
  iOS 解压时按 cp437 解释 → 目录名变成乱码 → 运行时按
  assets/zt/题目图/xxx.png 请求必然 404 → App 内所有图片空白。

治本两步：
  1. 目录改名：题目图 → timu，公式图 → formula（纯 ASCII）
  2. 全仓库把**本地**路径引用改掉（数据分片 / 前端 JS）
另配 .github/workflows/ios.yml 用 Python zipfile 写 UTF-8 标志位，双保险。

注意：上游仓库 ERRRC/xingcezhenti 的远程路径 `90-图片/题目图/`、
`90-图片/公式图/` 是别人的目录结构，**不能改**，所以这里只替换
`assets/zt/` 前缀下的本地路径。

用法：
  python scripts/rename_img_dirs.py --dry-run
  python scripts/rename_img_dirs.py --apply
"""
import argparse
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT_IMG = os.path.join(ROOT, "site", "assets", "zt")

RENAMES = [("题目图", "timu"), ("公式图", "formula")]

# 只替换本地路径（带 assets/zt/ 前缀），绝不动远程 90-图片/ 路径
PATH_SUBS = [
    ("assets/zt/题目图/", "assets/zt/timu/"),
    ("assets/zt/公式图/", "assets/zt/formula/"),
]

# 前端判据：路径里已没有中文，改判 ASCII 目录名
JUDGE_SUBS = [
    ("indexOf('公式图')", "indexOf('/formula/')"),
    ('indexOf("公式图")', 'indexOf("/formula/")'),
]

TEXT_EXTS = (".js", ".json", ".css", ".html", ".yml", ".cjs")
PY_EXTS = (".py",)
SKIP_DIRS = {
    ".git", "node_modules", ".appdata", "cache", ".github_sources",
    ".pdfwork", "dist", "dist-single", "build", "www", "public",
    "timu", "formula", "题目图", "公式图", "mat", "law_img",
}


def walk_files(exts):
    out = []
    for dp, dn, fn in os.walk(ROOT):
        rel = os.path.relpath(dp, ROOT).replace("\\", "/")
        if rel.startswith("mobile/www") or rel.startswith("mobile/ios/App/App/public"):
            dn[:] = []
            continue
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if not f.endswith(exts) or f.startswith("_"):
                continue
            out.append(os.path.join(dp, f))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.apply:
        print("请指定 --dry-run 或 --apply")
        return

    for old, new in RENAMES:
        src = os.path.join(ZT_IMG, old)
        dst = os.path.join(ZT_IMG, new)
        if os.path.isdir(src):
            n = len([x for x in os.listdir(src) if os.path.isfile(os.path.join(src, x))])
            print("RENAME %-6s -> %-8s (%d files)" % (old, new, n))
        elif os.path.isdir(dst):
            print("ALREADY %-8s (%d files)" % (new, len(os.listdir(dst))))
        else:
            print("MISSING %s" % old)

    # 前端 / 数据文件
    web_files = walk_files(TEXT_EXTS)
    hits = []
    for fp in web_files:
        try:
            t = io.open(fp, encoding="utf-8").read()
        except Exception:
            continue
        if "assets/zt/题目图/" in t or "assets/zt/公式图/" in t or "indexOf('公式图')" in t:
            hits.append(fp)
    print("\n需要改写的 前端/数据 文件 %d 个：" % len(hits))
    for h in sorted(hits):
        print("   " + os.path.relpath(h, ROOT))

    # Python 脚本：只改本地路径拼接，远程 90-图片/ 不动
    py_files = walk_files(PY_EXTS)
    py_hits = []
    for fp in py_files:
        try:
            t = io.open(fp, encoding="utf-8").read()
        except Exception:
            continue
        if "assets/zt/题目图/" in t or "assets/zt/公式图/" in t:
            py_hits.append(fp)
    print("\n需要改写的 Python 文件 %d 个：" % len(py_hits))
    for h in sorted(py_hits):
        print("   " + os.path.relpath(h, ROOT))

    if args.dry_run:
        print("\n（dry-run，未改动任何文件）")
        return

    # 1) 目录改名（git mv 保留历史）
    for old, new in RENAMES:
        src = os.path.join(ZT_IMG, old)
        dst = os.path.join(ZT_IMG, new)
        if not os.path.isdir(src):
            continue
        try:
            subprocess.run(
                ["git", "mv", "site/assets/zt/" + old, "site/assets/zt/" + new],
                cwd=ROOT, check=True, capture_output=True)
            print("git mv %s -> %s OK" % (old, new))
        except Exception as e:
            os.rename(src, dst)
            print("os.rename %s -> %s（git mv 失败: %s）" % (old, new, e))

    # 2) 改写引用（只改 .js/.json 等前端与数据文件；
    #    Python 脚本里既有远程路径判据又有本地路径拼接，人工逐处改更安全）
    n = 0
    stats = {}
    for fp in web_files:
        if fp.endswith(".py") or os.path.basename(fp) == "rename_img_dirs.py":
            continue
        try:
            raw = io.open(fp, encoding="utf-8").read()
        except Exception:
            continue
        orig = raw
        for a, b in PATH_SUBS:
            c = raw.count(a)
            if c:
                raw = raw.replace(a, b)
                stats[a] = stats.get(a, 0) + c
        if fp.endswith(".js"):
            for a, b in JUDGE_SUBS:
                c = raw.count(a)
                if c:
                    raw = raw.replace(a, b)
                    stats[a] = stats.get(a, 0) + c
        if raw != orig:
            io.open(fp, "w", encoding="utf-8", newline="\n").write(raw)
            n += 1
    print("\n改写文件 %d 个" % n)
    for k, v in sorted(stats.items()):
        print("   %-26s %d 处" % (k, v))

    # 3) 校验残留
    left = []
    for fp in web_files:
        try:
            t = io.open(fp, encoding="utf-8").read()
        except Exception:
            continue
        if "assets/zt/题目图" in t or "assets/zt/公式图" in t:
            left.append(os.path.relpath(fp, ROOT))
    print("\n残留 assets/zt/中文目录引用：%d 个文件" % len(left))
    for x in left:
        print("   " + x)


if __name__ == "__main__":
    main()

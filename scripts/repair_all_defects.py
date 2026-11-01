"""全面修复题库渲染缺陷（一次性解决）

修复项：
  1. 选项图片丢失 —— 从缓存 markdown 重新提取，写入 optionImgs 字段
  2. guokao 选项里的裸 <img> HTML —— 解析成 optionImgs 并清理文本
  3. 题干里的 "[图]" 占位符 —— 已有配图时删除该噪音
  4. 材料错配 —— 题干自带 ____ 的填空/语句题去掉材料
  5. 图形推理挂材料 —— 图形题一律去掉文字材料
  6. 缺失的图片文件 —— 从源仓库下载

用法：
  python scripts/repair_all_defects.py --dry-run
  python scripts/repair_all_defects.py --apply
"""

import sys
import io
import os
import re
import json
import glob
import time
import shutil
import urllib.parse
import urllib.request
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
CACHE = os.path.join(ROOT, "cache")
ASSETS_ZT = os.path.join(ROOT, "site", "assets", "zt")
APPLY = "--apply" in sys.argv

RAW_BASE = "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]

# 选项行：- **A**. 内容
OPTION_LINE = re.compile(r"^-\s*\*\*([A-D])\*\*\.\s*(.*)$", re.M)
IMG_SRC = re.compile(r'<img[^>]*?src="([^"]+)"[^>]*?>', re.I)

KEEP_KW = ("文章", "文中", "这段文字", "给定资料", "根据材料",
           "上述资料", "本文", "上述信息", "以上信息", "上文")


def norm_img_path(src: str) -> str:
    """../90-图片/公式图/x.png → 公式图/x.png"""
    name = src.split("/")[-1]
    if "公式图" in src:
        return "公式图/" + name
    if "题目图" in src:
        return "题目图/" + name
    return name


def scan_cache():
    """返回 {qid: {"optionImgs": {0:rel,1:rel...}, "stemImgs": [...]}}"""
    out = {}
    files = glob.glob(os.path.join(CACHE, "**", "*.md"), recursive=True)
    for f in files:
        try:
            txt = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        # 按题切块
        parts = re.split(r"\n#{1,4}\s*第\s*\d+\s*题", txt)
        for blk in parts:
            m = re.search(r"qid\s*(\d+)", blk)
            if not m:
                continue
            qid = m.group(1)
            # 只取「答案」之前的部分（题干+选项）
            head = blk.split("**答案**")[0]
            rec = out.setdefault(qid, {"optionImgs": {}, "stemImgs": []})

            # 选项图片
            for idx, om in enumerate(OPTION_LINE.finditer(head)):
                letter, content = om.group(1), om.group(2)
                srcs = IMG_SRC.findall(content)
                if srcs:
                    rec["optionImgs"][ord(letter) - ord("A")] = norm_img_path(srcs[0])

            # 题干图片（选项行之外）
            stem_part = OPTION_LINE.sub("", head)
            for src in IMG_SRC.findall(stem_part):
                rel = norm_img_path(src)
                if rel not in rec["stemImgs"]:
                    rec["stemImgs"].append(rel)
    return out


def ensure_image(rel: str) -> bool:
    """确保图片存在于 assets/zt 下，缺失则下载"""
    dst = os.path.join(ASSETS_ZT, rel)
    if os.path.exists(dst) and os.path.getsize(dst) > 50:
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    url = RAW_BASE + urllib.parse.quote("90-图片/" + rel)
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            if len(data) < 50:
                raise ValueError("too small")
            open(dst, "wb").write(data)
            return True
        except Exception:
            time.sleep(1.5 * (i + 1))
    return False


def main():
    print("=" * 72)
    print("  全面修复题库渲染缺陷")
    print("=" * 72)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    cache_map = scan_cache()
    with_opt_img = sum(1 for v in cache_map.values() if v["optionImgs"])
    print(f"  缓存解析：{len(cache_map)} 题，其中 {with_opt_img} 题含选项图片")
    print()

    # 收集所有需要的图片
    needed = set()
    for v in cache_map.values():
        for rel in v["optionImgs"].values():
            needed.add(rel)
        for rel in v["stemImgs"]:
            needed.add(rel)
    missing = [r for r in needed if not os.path.exists(os.path.join(ASSETS_ZT, r))]
    print(f"  需要的图片 {len(needed)} 张，本地缺失 {len(missing)} 张")

    if APPLY and missing:
        print("  开始下载缺失图片…")
        ok = fail = 0
        for i, rel in enumerate(missing):
            if ensure_image(rel):
                ok += 1
            else:
                fail += 1
            if (i + 1) % 50 == 0:
                print(f"    进度 {i+1}/{len(missing)}")
        print(f"  下载成功 {ok}，失败 {fail}")
    print()

    total = defaultdict(int)

    for name in SHARDS:
        path = os.path.join(ZT, name + ".json")
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        changed = 0

        for q in data:
            qid = str(q.get("id", ""))
            tail = qid.split("-")[-1]
            rec = cache_map.get(tail)

            # ── 1. 选项图片：从缓存重建 optionImgs ──
            opts = list(q.get("options") or [])
            srcs = (rec or {}).get("optionImgs") or {}

            # guokao 的选项本身含 <img>，优先从选项里取
            raw_imgs = {}
            for i, o in enumerate(opts):
                m = IMG_SRC.search(str(o))
                if m:
                    raw_imgs[i] = norm_img_path(m.group(1))
            if raw_imgs:
                srcs = raw_imgs

            if srcs:
                arr = [""] * len(opts)
                for i, rel in srcs.items():
                    if 0 <= i < len(arr):
                        p = "assets/zt/" + rel
                        if os.path.exists(os.path.join(ROOT, "site", p)) or not APPLY:
                            arr[i] = p
                if any(arr):
                    q["optionImgs"] = arr
                    changed += 1
                    total["选项图片"] += 1

            # 清理选项里的 <img> HTML（已转成 optionImgs）
            if raw_imgs:
                new_opts = []
                for i, o in enumerate(opts):
                    if i in raw_imgs:
                        new_opts.append("")     # 图片选项，文本留空
                    else:
                        new_opts.append(str(o))
                q["options"] = new_opts

            # ── 2. 题干 "[图]" 噪音清理 ──
            stem = q.get("stem") or ""
            if "[图]" in stem and (q.get("imgs") or q.get("optionImgs")):
                q["stem"] = stem.replace("[图]", "").strip()
                changed += 1
                total["[图]清理"] += 1

            # ── 3. 材料错配清理 ──
            mat = q.get("material") or ""
            sub = q.get("sub") or ""
            stem2 = q.get("stem") or ""
            drop = False
            if mat and not q.get("materialImgs") and mat.strip() not in ("[图]", "[图片]"):
                if sub == "图形推理":
                    drop = True                       # 图形题不需要文字材料
                elif "____" in stem2 and not any(k in stem2 for k in KEEP_KW) \
                        and sub not in ("增长", "比重", "平均数", "倍数", "综合"):
                    drop = True                       # 横线在题干里，材料多余
                elif sub == "类比推理" and not any(k in stem2 for k in KEEP_KW):
                    drop = True                       # 类比推理不依赖长材料
            if drop:
                q["material"] = ""
                q.pop("matNo", None)
                changed += 1
                total["材料清理"] += 1

        if changed:
            print(f"  {name:10s} 修改 {changed} 题")
            if APPLY:
                bak = path + ".repairbak"
                if not os.path.exists(bak):
                    shutil.copy(path, bak)
                json.dump(data, open(path, "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                print(f"      已写入")

    print()
    print("  修复统计：")
    for k, v in total.items():
        print(f"    {k}: {v}")

    if not APPLY:
        print("\n  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

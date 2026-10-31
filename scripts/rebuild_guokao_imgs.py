"""从原始 markdown 重建 guokao 的图片字段

问题：
  fetch_guokao.py 的 clean_rich 把所有 <img> 替换成 "[图]" 文字，
  merge_guokao.py 又硬编码 "imgs": []，
  结果 1040 道国考题全部没有图片。
  其中 80 道图形推理题的选项是 A/B/C/D 文字，
  内容全在图里，没图完全无法作答。

源数据：
  缓存 markdown 里图片是完整的：
    <p><img width="600px" height="268px"
       src="../90-图片/题目图/19ad3b3b7e23ff1.png" /></p>

修复：
  1. 解析缓存 markdown，为每道题提取：
       · 题干图片（题目图）
       · 公式图
       · 选项图片
  2. 复制图片到 site/assets/zt/ 下
  3. 写回 guokao.json 的 imgs / materialImgs 字段

用法：
  python scripts/rebuild_guokao_imgs.py --dry-run
  python scripts/rebuild_guokao_imgs.py --apply
"""

import sys
import io
import os
import re
import json
import glob
import urllib.request
import urllib.parse
import time
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache")
ZT = os.path.join(ROOT, "site", "data", "zt")
ASSETS_ZT = os.path.join(ROOT, "site", "assets", "zt")

APPLY = "--apply" in sys.argv

RAW_BASE = "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"

# 题块分隔
QID_RE = re.compile(r"qid\s*(\d+)")
# 图片引用
IMG_RE = re.compile(r'<img[^>]*?src="([^"]+)"[^>]*?>', re.I)


def scan_markdown():
    """扫描所有缓存 markdown，返回 {qid: [图片相对路径]}"""
    mapping = {}
    files = glob.glob(os.path.join(CACHE, "**", "*.md"), recursive=True)
    print(f"  扫描 markdown: {len(files)} 个")

    for f in files:
        try:
            txt = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue

        # 按「第 N 题」切块
        blocks = re.split(r"\n#{1,4}\s*第\s*\d+\s*题", txt)
        for blk in blocks:
            m = QID_RE.search(blk)
            if not m:
                continue
            qid = m.group(1)
            imgs = IMG_RE.findall(blk[:blk.find("**答案**")] if "**答案**" in blk else blk)
            # 归一化路径：../90-图片/题目图/x.png → 题目图/x.png
            norm = []
            for src in imgs:
                src = src.strip()
                if not src:
                    continue
                name = src.split("/")[-1]
                if "公式图" in src:
                    norm.append("公式图/" + name)
                elif "题目图" in src:
                    norm.append("题目图/" + name)
                elif "材料" in src:
                    norm.append("材料图/" + name)
                else:
                    norm.append(name)
            if norm:
                bucket = mapping.setdefault(qid, [])
                for x in norm:
                    if x not in bucket:
                        bucket.append(x)
    return mapping


def download_image(rel, dest_dir):
    """从源仓库下载图片到本地"""
    name = rel.split("/")[-1]
    sub = rel.split("/")[0]
    out = os.path.join(dest_dir, sub, name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out) and os.path.getsize(out) > 100:
        return out

    # 源仓库路径
    src_path = "90-图片/" + rel
    url = RAW_BASE + urllib.parse.quote(src_path)
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            if len(data) < 100:
                raise ValueError("文件过小")
            open(out, "wb").write(data)
            return out
        except Exception as e:
            if i == 3:
                return None
            time.sleep(2 + i * 2)
    return None


def main():
    print("=" * 66)
    print("  重建 guokao 图片")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    mapping = scan_markdown()
    print(f"  从 markdown 提取到含图的题: {len(mapping)}")
    total_refs = sum(len(v) for v in mapping.values())
    print(f"  图片引用总数: {total_refs}")
    print()

    gk_path = os.path.join(ZT, "guokao.json")
    data = json.load(open(gk_path, encoding="utf-8"))
    byid = {str(q["id"]): q for q in data}

    # qid 匹配：guokao 的 id 是 gk-YYYYxx-<数字>，取尾号匹配
    matched = 0
    would_fill = 0
    for q in data:
        tail = str(q["id"]).split("-")[-1]
        if tail in mapping:
            matched += 1
            if not (q.get("imgs") or []):
                would_fill += 1

    print(f"  guokao 能匹配到图的题: {matched} / {len(data)}")
    print(f"  其中当前无图、待填充: {would_fill}")
    print()

    if not APPLY:
        # 演练：只展示样例
        print("=== 样例（前 5 题）===")
        n = 0
        for q in data:
            tail = str(q["id"]).split("-")[-1]
            if tail in mapping and n < 5:
                print(f"  {q['id']} (sub={q.get('sub')})")
                print(f"    图片: {mapping[tail]}")
                n += 1
        print()
        print("  演练结束。加 --apply 下载图片并写入。")
        return

    # 实际执行：下载图片 + 写入
    print("=== 开始下载图片 ===")
    ok_cnt = 0
    fail_cnt = 0
    done = set()

    for q in data:
        tail = str(q["id"]).split("-")[-1]
        refs = mapping.get(tail, [])
        if not refs:
            continue
        rels = []
        for rel in refs:
            if rel in done:
                rels.append("assets/zt/" + rel)
                continue
            out = download_image(rel, ASSETS_ZT)
            if out:
                ok_cnt += 1
                done.add(rel)
                rels.append("assets/zt/" + rel)
            else:
                fail_cnt += 1
        if rels:
            q["imgs"] = rels

    print(f"  下载成功: {ok_cnt}")
    print(f"  下载失败: {fail_cnt}")

    # 备份并写入
    bak = gk_path + ".imgbak"
    if not os.path.exists(bak):
        shutil.copy(gk_path, bak)
    json.dump(data, open(gk_path, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"  已写入 {gk_path}")

    # 统计写入结果
    with_img = sum(1 for q in data if q.get("imgs"))
    print(f"  最终有图的题: {with_img} / {len(data)}")
    graph_with = sum(1 for q in data if q.get("sub") == "图形推理" and q.get("imgs"))
    graph_all = sum(1 for q in data if q.get("sub") == "图形推理")
    print(f"  图形推理题有图: {graph_with} / {graph_all}")


if __name__ == "__main__":
    main()

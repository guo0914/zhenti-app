"""从原始缓存重建逻辑填空题的横线标记

问题现象：
  逻辑填空题（314 道）里，题干中的横线位置变成了一个普通空格，
  用户看到的是「形成 的整体风格」，不知道要在哪里填词。

根因：
  原始缓存的 markdown 里，横线是连续的 \\xa0（不间断空格），
  常见 8 / 10 / 12 / 20 个，例如：
    "这句古训就是强调\\xa0\\xa0\\xa0\\xa0\\xa0\\xa0\\xa0\\xa0\\xa0\\xa0\\xa0\\xa0的重要性"

  parse_zhenti.py 的 strip_tags 做了：
    t.replace("\\xa0", " ")      → 12 个 \\xa0 变 12 个空格
    re.sub(r"[ \\t]+", " ", t)   → 压缩成 1 个空格

  横线就消失了。

修复：
  1. 已修 parse_zhenti.py（\\xa0{2,} → ____）
  2. 本脚本针对已入库的数据做补救：
     从 cache/ 原始 markdown 重新提取该题题干，
     按 \\xa0 序列还原横线，与当前 stem 比对后替换。

用法：
  python scripts/fix_blank_markers.py --dry-run
  python scripts/fix_blank_markers.py --apply
"""

import sys
import io
import os
import re
import json
import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
CACHE = os.path.join(ROOT, "cache")

APPLY = "--apply" in sys.argv

# 把连续 \xa0 或交替形式还原成横线
BLANK_RE = re.compile(r"(?:\xa0 ?){2,}")


def restore_blanks(text: str) -> str:
    return BLANK_RE.sub("____", text)


def norm(s: str) -> str:
    """用于比对：去掉所有横线/空白差异"""
    s = re.sub(r"_{2,}", "", s)
    s = re.sub(r"[\s\u00a0\u3000]+", "", s)
    return s


def load_raw_stems():
    """从缓存 markdown 里提取所有「题干首句」，建立归一化索引"""
    cache = {}
    dirs = glob.glob(os.path.join(CACHE, "*"))
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.md")):
            try:
                txt = open(f, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            # 按题目块切分（<sub> 题型</sub> 标记题头）
            for m in re.finditer(r"<sub>([^<]*)</sub>\s*(.*?)(?=\n#{1,4}\s|\Z)",
                                 txt, re.S):
                sub = m.group(1).strip()
                body = m.group(2)
                if "逻辑填空" not in sub:
                    continue
                # 取题干（到「填入画横线」或选项开始）
                em = re.search(r"(.*?)(?:填入画横线|\n-\s*\*\*A\*\*|\Z)", body, re.S)
                if not em:
                    continue
                raw_stem = em.group(1).strip()
                if "\xa0" not in raw_stem:
                    continue
                key = norm(restore_blanks(raw_stem))[:60]
                if key:
                    cache[key] = restore_blanks(raw_stem)
    return cache


def main():
    verbal_path = os.path.join(ZT, "verbal.json")
    data = json.load(open(verbal_path, encoding="utf-8"))

    print("=" * 66)
    print("  重建逻辑填空的横线标记")
    print("=" * 66)
    print(f"  模式: {'写入' if APPLY else '演练'}")
    print()

    raw = load_raw_stems()
    print(f"  从缓存提取到含横线的题干: {len(raw)}")
    print()

    fill = [q for q in data if q.get("sub") == "逻辑填空"]
    print(f"  逻辑填空题: {len(fill)}")

    fixed = 0
    samples = []
    for q in fill:
        stem = q.get("stem") or ""
        if "____" in stem:
            continue                       # 已有横线，跳过
        key = norm(stem)[:60]
        if key in raw:
            new_stem = raw[key]
            if norm(new_stem) == norm(stem):
                q["stem"] = new_stem
                fixed += 1
                if len(samples) < 6:
                    samples.append((q.get("id"), stem[:60], new_stem[:60]))

    print(f"  可修复: {fixed} / {len(fill)}")
    print()
    if samples:
        print("=== 样例 ===")
        for qid, before, after in samples:
            print(f"  id={qid}")
            print(f"    修复前: {before}")
            print(f"    修复后: {after}")
        print()

    if APPLY and fixed:
        bak = verbal_path + ".bak"
        if not os.path.exists(bak):
            import shutil
            shutil.copy(verbal_path, bak)
            print(f"  已备份 {os.path.basename(bak)}")
        json.dump(data, open(verbal_path, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"  已写入 {verbal_path}")
    elif not APPLY:
        print("  演练结束。加 --apply 写入。")


if __name__ == "__main__":
    main()

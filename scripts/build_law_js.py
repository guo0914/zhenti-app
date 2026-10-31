#!/usr/bin/env python3
"""把 zt 格式的法律题库 JSON 打包成前端可直接 <script> 加载的 .js

输入：scripts/to_zt_law.py 产出的 law.json（question 数组）
输出：site/data/zt/law.js —— window.__LAW_QUESTIONS__ = [...]

同时可合并多个科目（刑法+民法+…）成一个文件。

用法：
  python scripts/build_law_js.py --in ../law_ocr/law_all.json --out ../site/data/zt/law.js
  python scripts/build_law_js.py --in a.json b.json --out out.js     # 合并多份
"""

import sys, io, os, json, argparse
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description="法律题库打包为 JS")
    ap.add_argument("--in", dest="inputs", nargs="+", required=True, help="一个或多个 law.json")
    ap.add_argument("--out", required=True, help="输出 .js 路径")
    ap.add_argument("--as-index", action="store_true",
                    help="同时生成分类索引 zt-law-index.json")
    args = ap.parse_args()

    all_q = []
    for path in args.inputs:
        if not os.path.exists(path):
            print(f"x 跳过不存在的文件: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("questions", [])
        # 去重
        seen = {q["id"] for q in all_q}
        added = 0
        for q in data:
            if q["id"] not in seen:
                all_q.append(q)
                added += 1
        print(f"  {os.path.basename(path)}: +{added} 题")

    if not all_q:
        print("x 没有题目")
        sys.exit(1)

    # 按科目 → 章节 → 题号 排序
    all_q.sort(key=lambda q: (q.get("region", ""), q.get("chapter", ""), int(q.get("no", 0))))

    # 统计
    subjects = {}
    for q in all_q:
        s = q.get("region", "其他")
        if s not in subjects:
            subjects[s] = {"total": 0, "subs": {}, "withAnswer": 0, "clean": 0}
        subjects[s]["total"] += 1
        sub = q.get("sub", "综合")
        subjects[s]["subs"][sub] = subjects[s]["subs"].get(sub, 0) + 1
        if q.get("answer"):
            subjects[s]["withAnswer"] += 1
        if not q.get("flags"):
            subjects[s]["clean"] += 1

    print("\n" + "=" * 55)
    print(f"法律题库总计: {len(all_q)} 题")
    for s in sorted(subjects, key=lambda x: -subjects[x]["total"]):
        info = subjects[s]
        print(f"  {s}: {info['total']} 题 · {len(info['subs'])} 章节 · " +
              f"答案 {info['withAnswer']}/{info['total']} · 无标记 {info['clean']}")

    # 输出 JS
    updated = datetime.now().strftime("%Y-%m-%d %H:%M")
    js = f"""/* ===== 法律专业科目题库 =====
 * 由 scripts/build_law_js.py 生成 — {updated}
 * 共 {len(all_q)} 题 · {len(subjects)} 科目
 * 格式与 data/zt/*.json 一致，前端可直接复用
 */

window.__LAW_QUESTIONS__ = """
    js += json.dumps(all_q, ensure_ascii=False, separators=(",", ":"))
    js += ";\n"

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(js)

    size = os.path.getsize(args.out) / 1024 / 1024
    print(f"\n[DONE] -> {args.out} ({size:.2f} MB)")

    # 分类索引
    if args.as_index:
        idx_path = os.path.join(os.path.dirname(args.out), "zt-law-index.json")
        index = {
            "meta": {
                "name": "法律专业科目题库",
                "source": "法考真金题系列（8科）",
                "total": len(all_q),
                "built": updated,
            },
            "subjects": [
                {
                    "key": s,
                    "total": subjects[s]["total"],
                    "chapters": subjects[s]["subs"],
                    "withAnswer": subjects[s]["withAnswer"],
                }
                for s in sorted(subjects, key=lambda x: -subjects[x]["total"])
            ],
        }
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=1)
        print(f"[索引] -> {idx_path}")


if __name__ == "__main__":
    main()

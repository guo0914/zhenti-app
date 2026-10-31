"""深度检查题库数据质量：找出可能遗漏的问题"""

import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

SHARDS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data", "guokao"]


def load():
    out = {}
    for c in SHARDS:
        p = os.path.join(ZT, c + ".json")
        if os.path.exists(p):
            out[c] = json.load(open(p, encoding="utf-8"))
    return out


def main():
    shards = load()
    print("=" * 64)
    print("  深度数据质量检查")
    print("=" * 64)

    # ── 1. 选项数量异常 ──
    print("\n[1] 选项数量异常")
    bad = []
    for c, arr in shards.items():
        for q in arr:
            opts = [str(o) for o in (q.get("options") or [])]
            nonempty = [o for o in opts if o.strip()]
            has_img = bool(q.get("imgs"))
            if not nonempty and has_img:
                continue          # 有图题允许空选项
            if len(nonempty) == 1:
                bad.append((c, q.get("id"), "只有1个有效选项"))
            if len(opts) > 5:
                bad.append((c, q.get("id"), f"{len(opts)}个选项"))
    print(f"  异常: {len(bad)}")
    for b in bad[:6]:
        print(f"    {b}")

    # ── 2. 答案格式 ──
    print("\n[2] 答案格式异常")
    bad2 = []
    for c, arr in shards.items():
        for q in arr:
            ans = str(q.get("answer") or "").strip()
            keys = q.get("optionKeys") or ["A", "B", "C", "D"]
            if not ans:
                continue
            for ch in ans:
                if ch not in keys and ch not in "ABCDE":
                    bad2.append((c, q.get("id"), ans))
                    break
    print(f"  异常: {len(bad2)}")
    for b in bad2[:6]:
        print(f"    {b}")

    # ── 3. 选项复述题干 ──
    print("\n[3] 选项长段复述题干（可能解析错位）")
    bad3 = []
    for c, arr in shards.items():
        for q in arr:
            stem = (q.get("stem") or "").strip()
            for o in (q.get("options") or []):
                o = str(o).strip()
                if o and len(o) > 30 and o in stem:
                    bad3.append((c, q.get("id"), o[:35]))
                    break
    print(f"  可疑: {len(bad3)}")
    for b in bad3[:6]:
        print(f"    {b}")

    # ── 4. 选项污染 ──
    print("\n[4] 选项污染（含解析/答案字样）")
    POLLUTE = ["解析", "答案", "故选", "故正确答案", "参考答案", "考点"]
    bad4 = []
    for c, arr in shards.items():
        for q in arr:
            for o in (q.get("options") or []):
                o = str(o)
                if any(p in o for p in POLLUTE):
                    bad4.append((c, q.get("id"), o[:45]))
                    break
    print(f"  污染: {len(bad4)}")
    for b in bad4[:6]:
        print(f"    {b}")

    # ── 5. 题干截断 ──
    print("\n[5] 题干疑似截断（结尾不是标点）")
    bad5 = []
    END_OK = "：:？?。.）)\u201d\u201c；;！!…】]"
    for c, arr in shards.items():
        for q in arr:
            stem = (q.get("stem") or "").strip()
            if not stem or len(stem) < 20:
                continue
            last = stem[-1]
            if last in END_OK:
                continue
            # 结尾是中文/字母时，看最后 30 字像不像话没说完
            tail = stem[-18:]
            if tail and (not tail[-1].isspace()):
                bad5.append((c, q.get("id"), tail))
    print(f"  疑似: {len(bad5)}")
    for b in bad5[:8]:
        print(f"    {b}")

    # ── 6. 重复题（同 stem 完全相同）──
    print("\n[6] 完全重复的题（同分片内）")
    for c, arr in shards.items():
        seen = {}
        dups = 0
        for q in arr:
            key = (q.get("stem") or "").strip()
            if not key:
                continue
            if key in seen:
                dups += 1
            else:
                seen[key] = q.get("id")
        if dups:
            print(f"    {c}: {dups} 处重复")

    # ── 7. 材料题材料为空 ──
    print("\n[7] 需要材料但材料为空")
    bad7 = []
    for c, arr in shards.items():
        for q in arr:
            sub = (q.get("sub") or "")
            stem = (q.get("stem") or "")
            mat = (q.get("material") or "")
            matimgs = q.get("materialImgs") or []
            need = ("综合" in sub or "增长" in sub or "比重" in sub
                    or "平均数" in sub or "倍数" in sub
                    or "画横线" in stem or "文中" in stem or "文章" in stem)
            if need and not mat and not matimgs:
                bad7.append((c, q.get("id"), sub, stem[:30]))
    print(f"  缺失: {len(bad7)}")
    for b in bad7[:6]:
        print(f"    {b}")


if __name__ == "__main__":
    main()

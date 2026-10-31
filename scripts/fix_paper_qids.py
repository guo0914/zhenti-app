"""修复套卷索引里 qids 与题库分片 id 不匹配的问题

问题现象：
  · 打开『真题套卷』，题目题干/选项缺失或错乱
  · 政治理论模块里混进言语等其他模块的题

根因：
  套卷索引 zt-papers.json 里 qids 存的是纯数字（如 '19526414'），
  而题库分片（guokao.json 等）里的 id 是带前缀的完整形式
  （如 'gk-2026xz-19526238'）。两边对不上 → 找不到题目。

  又因为 767 个纯数字在多个卷里重复，不能简单按尾号匹配，
  必须结合年份 + 卷别（副省级 xz / 地市级 ds / 行政执法）精确对应。

修复策略：
  1. 建立「完整 id」集合，按 (年份, 卷短码, 尾号) 索引
  2. 对每套卷，根据 year + subtype 推断正确的卷短码
  3. 用尾号去对应卷里找完整 id，写回 qids
  4. 无法匹配的保留原值并记录，便于人工核对

用法（默认演练，不动文件）：
  python scripts/fix_paper_qids.py --dry-run
实际写入：
  python scripts/fix_paper_qids.py --apply
"""

import sys
import io
import os
import json
import re
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "data")
ZT = os.path.join(DATA, "zt")

APPLY = "--apply" in sys.argv

# 各卷别对应的短码
#   国考：xz=副省级，ds=地市级；行政执法卷与地市级同题源常见
CODE_HINTS = {
    "副省级": ["xz"],
    "地市级": ["ds"],
    "行政执法": ["ds", "zf", "xz"],
}


def load_all_questions():
    """加载所有题目分片，返回 {完整id: question}"""
    allq = {}
    for cat in ["politics", "common", "verbal", "quantity", "judge",
                "graph", "data", "guokao"]:
        p = os.path.join(ZT, cat + ".json")
        if not os.path.exists(p):
            continue
        try:
            arr = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"  读取失败 {cat}.json: {e}")
            continue
        for q in arr:
            qid = str(q.get("id", ""))
            if qid:
                allq[qid] = q
    return allq


def build_lookup(allq):
    """建立 (年份, 卷短码, 尾号) -> 完整id 的索引"""
    idx = defaultdict(dict)
    for qid in allq:
        parts = qid.split("-")
        if len(parts) == 3 and parts[0] == "gk":
            code = parts[1]                 # 2026xz
            m = re.match(r"(\d{4})(\w+)", code)
            if m:
                year, kind = m.group(1), m.group(2)
                idx[(year, kind)][parts[2]] = qid
        else:
            # 普通分片：id 就是尾号本身
            idx[(None, None)][qid] = qid
    return idx


def guess_codes(paper):
    """根据套卷信息推断候选卷短码"""
    sub = (paper.get("subtype") or "") + (paper.get("paper") or "")
    for key, codes in CODE_HINTS.items():
        if key in sub:
            return codes
    # 默认按副省级优先
    return ["xz", "ds"]


def main():
    papers_path = os.path.join(DATA, "zt-papers.json")
    data = json.load(open(papers_path, encoding="utf-8"))
    papers = data["papers"]

    allq = load_all_questions()
    lookup = build_lookup(allq)

    print("=" * 66)
    print("  修复套卷 qids")
    print("=" * 66)
    print(f"  题目分片总数: {len(allq)}")
    print(f"  套卷总数: {len(papers)}")
    print(f"  模式: {'写入文件' if APPLY else '演练（不修改文件）'}")
    print()

    fixed_papers = 0
    fixed_ids = 0
    unresolved_total = 0
    changes = []

    for pi, paper in enumerate(papers):
        qids = [str(x) for x in paper.get("qids", [])]
        if not qids:
            continue

        # 已全部能在分片里找到 → 跳过
        if all(q in allq for q in qids):
            continue

        year = str(paper.get("year") or "")
        codes = guess_codes(paper)
        new_qids = []
        unresolved = []

        for qid in qids:
            if qid in allq:
                new_qids.append(qid)
                continue
            # 尝试按年份+卷短码匹配
            hit = None
            for c in codes:
                m = lookup.get((year, c), {}).get(qid)
                if m:
                    hit = m
                    break
            # 再尝试不限年份
            if not hit:
                for (y, c), mp in lookup.items():
                    if y and mp.get(qid):
                        hit = mp[qid]
                        break
            if hit:
                new_qids.append(hit)
                fixed_ids += 1
            else:
                new_qids.append(qid)
                unresolved.append(qid)

        if new_qids != qids:
            fixed_papers += 1
            changes.append({
                "idx": pi,
                "paper": paper.get("paper", ""),
                "before_sample": qids[:3],
                "after_sample": new_qids[:3],
                "replaced": sum(1 for a, b in zip(qids, new_qids) if a != b),
                "unresolved": len(unresolved),
            })
            paper["qids"] = new_qids
        unresolved_total += len(unresolved)

    print(f"  处理套卷: {fixed_papers}")
    print(f"  替换 id 数: {fixed_ids}")
    print(f"  仍无法匹配: {unresolved_total}")
    print()

    if changes:
        print("=== 变更明细（前 12 条）===")
        for c in changes[:12]:
            print(f"  [{c['idx']}] {c['paper'][:40]}")
            print(f"      替换 {c['replaced']} 个，无法匹配 {c['unresolved']} 个")
            print(f"      例: {c['before_sample'][0]} → {c['after_sample'][0]}")
        if len(changes) > 12:
            print(f"  …… 还有 {len(changes) - 12} 套")
        print()

    # 更新 meta 里的统计
    data["meta"]["qidFixApplied"] = "2026-10-31"
    data["meta"]["qidFixReplaced"] = fixed_ids

    if APPLY:
        # 备份
        bak = papers_path + ".bak"
        if not os.path.exists(bak):
            import shutil
            shutil.copy(papers_path, bak)
            print(f"  已备份: zt-papers.json.bak")

        json.dump(data, open(papers_path, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        print(f"  已写入 {papers_path}")

        # 同时更新 .js 版本（前端优先读 js）
        js_path = os.path.join(DATA, "zt-papers.js")
        if os.path.exists(js_path):
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            open(js_path, "w", encoding="utf-8").write(
                "window.__ZT_PAPERS__ = " + body + ";\n")
            print(f"  已同步 {js_path}")
    else:
        print("  演练结束。确认无误后加 --apply 写入。")


if __name__ == "__main__":
    main()

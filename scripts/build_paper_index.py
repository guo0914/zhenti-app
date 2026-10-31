"""生成真题套卷索引 site/data/zt-papers.json

从 site/data/zt/*.json 聚合出「卷」这一维度的元信息：
  卷名、年份、地区、模块配比、题数、题号连续性、题目 id 列表

供前端「真题套卷」模块按卷浏览/组卷使用。
"""
import json
import os
import sys
import io
import re
from collections import defaultdict, Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")
OUT = os.path.join(ROOT, "site", "data", "zt-papers.json")

# 分类 → 标准模块名（行测七大模块）
CAT_NAME = {
    "politics": "政治理论",
    "common": "常识判断",
    "verbal": "言语理解与表达",
    "quantity": "数量关系",
    "judge": "判断推理",
    "graph": "图形推理",
    "data": "资料分析",
    "law": "法律专业",
}

# 标准行测模块顺序（用于卷面排序）
MODULE_ORDER = ["政治理论", "常识判断", "言语理解与表达", "数量关系",
                "判断推理", "图形推理", "资料分析", "法律专业"]


def guess_region(paper: str) -> str:
    """从卷名推断地区。"""
    if "国家公务员" in paper or "国考" in paper:
        return "国考"
    provs = ["北京", "上海", "天津", "重庆", "江苏", "浙江", "山东", "四川", "广东",
             "福建", "河南", "河北", "湖南", "湖北", "安徽", "江西", "陕西", "山西",
             "辽宁", "吉林", "黑龙江", "云南", "贵州", "广西", "海南", "甘肃", "青海",
             "宁夏", "新疆", "内蒙古", "西藏"]
    for p in provs:
        if p in paper:
            return p + "省考" if p not in ("北京", "上海", "天津", "重庆") else p + "市考"
    if "联考" in paper:
        return "多省联考"
    if "选调" in paper:
        return "选调生"
    return "其他"


def guess_subtype(paper: str) -> str:
    """从卷名推断卷别（副省级/地市级/行政执法等）。"""
    for k in ("副省级", "地市级", "行政执法", "乡镇卷", "县级卷",
              "A类", "B类", "C类", "公安"):
        if k in paper:
            return k
    return ""


def scan_shenlun():
    """扫描申论数据文件，聚合出申论套卷。"""
    pairs = [
        (os.path.join(ROOT, "site", "data", "shenlun.js"), "shenlun"),
        (os.path.join(ROOT, "site", "data", "shenlun-2025-2026.js"), "shenlun"),
    ]
    papers = defaultdict(lambda: {"n": 0, "qids": []})
    for path, _ in pairs:
        if not os.path.exists(path):
            continue
        txt = open(path, encoding="utf-8").read()
        # 逐题对象提取（宽松）：找 paper + id
        # 用正则在整份文件里扫每道题
        for m in re.finditer(
                r'\{[^{}]*?["\']?id["\']?\s*:\s*["\']([^"\']+)["\'][^{}]*?\}', txt):
            obj = m.group(0)
            pm = re.search(r'["\']?[Pp]aper["\']?\s*:\s*["\']([^"\']+)["\']', obj)
            if not pm:
                continue
            paper = pm.group(1)
            papers[paper]["n"] += 1
            papers[paper]["qids"].append(m.group(1))

    out = []
    for paper, e in papers.items():
        my = re.search(r"(20\d{2})", paper)
        year = my.group(1) if my else ""
        # 申论是主观题，每卷 4-5 道大题，评级看题数
        grade = "A" if e["n"] >= 4 else "B"
        out.append({
            "paper": paper,
            "year": year,
            "region": guess_region(paper),
            "subtype": guess_subtype(paper),
            "total": e["n"],
            "modules": [{"cat": "shenlun", "name": "申论", "count": e["n"]}],
            "moduleCount": 1,
            "noSpan": e["n"],
            "noGaps": 0,
            "coverage": 1.0,
            "qids": e["qids"],
            "grade": grade,
            "kind": "shenlun",
        })
    return out


def main():
    papers = defaultdict(lambda: {
        "n": 0, "cats": Counter(), "qids": [], "nos": [],
    })

    # 遍历所有 zt 分片
    for f in sorted(os.listdir(ZT)):
        if not f.endswith(".json"):
            continue
        cat = f[:-5]
        if cat in ("zt-law-index", "zt-papers"):
            continue
        path = os.path.join(ZT, f)
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        qs = d if isinstance(d, list) else d.get("questions", [])
        for q in qs:
            paper = str(q.get("paper") or "").strip()
            if not paper:
                continue
            e = papers[paper]
            e["n"] += 1
            e["cats"][cat] += 1
            e["qids"].append(str(q.get("id")))
            try:
                e["nos"].append(int(q.get("no")))
            except (ValueError, TypeError):
                pass

    out = []
    for paper, e in papers.items():
        nos = sorted(set(e["nos"]))
        total_span = (nos[-1] - nos[0] + 1) if len(nos) > 1 else len(nos)
        gaps = total_span - len(nos)
        coverage = len(nos) / total_span if total_span else 0

        # 模块配比（按标准顺序）
        mods = []
        for cat, cnt in e["cats"].items():
            mods.append({
                "cat": cat,
                "name": CAT_NAME.get(cat, cat),
                "count": cnt,
            })
        mods.sort(key=lambda m: (MODULE_ORDER.index(m["name"])
                                 if m["name"] in MODULE_ORDER else 99,
                                 -m["count"]))

        # 年份
        m_year = re.search(r"(20\d{2})", paper)
        year = m_year.group(1) if m_year else ""

        out.append({
            "paper": paper,
            "year": year,
            "region": guess_region(paper),
            "subtype": guess_subtype(paper),
            "total": e["n"],
            "modules": mods,
            "moduleCount": len(mods),
            "noSpan": total_span,
            "noGaps": gaps,
            "coverage": round(coverage, 3),
            "qids": e["qids"],
            # 完整度评级：>=80题 且 >=4模块 且 覆盖率>=0.95
            "grade": ("A" if e["n"] >= 80 and len(mods) >= 4 and coverage >= 0.95
                      else "B" if e["n"] >= 60 and len(mods) >= 4
                      else "C"),
        })

    # 排序：年份降序 → 完整度降序 → 题数降序
    out.sort(key=lambda x: (-int(x["year"] or 0),
                            {"A": 0, "B": 1, "C": 2}[x["grade"]],
                            -x["total"]))

    # 并入申论套卷
    sl = scan_shenlun()
    for x in sl:
        x.setdefault("kind", "shenlun")
    # 行测卷标 kind
    for x in out:
        x.setdefault("kind", "xingce")
    out.extend(sl)
    out.sort(key=lambda x: (-int(x["year"] or 0),
                            {"A": 0, "B": 1, "C": 2}[x["grade"]],
                            0 if x.get("kind") == "xingce" else 1,
                            -x["total"]))

    # 汇总统计
    by_year = Counter(x["year"] for x in out)
    by_grade = Counter(x["grade"] for x in out)

    payload = {
        "meta": {
            "name": "行测真题套卷索引",
            "total": len(out),
            "totalQuestions": sum(x["total"] for x in out),
            "years": sorted(by_year.keys(), reverse=True),
            "gradeCount": dict(by_grade),
            "generated": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "papers": out,
    }

    json.dump(payload, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    size = os.path.getsize(OUT) / 1024
    print("=" * 66)
    print("套卷索引生成完成")
    print("=" * 66)
    print(f"卷数: {len(out)}")
    print(f"题目: {sum(x['total'] for x in out)}")
    print(f"年份: {', '.join(sorted(by_year, reverse=True))}")
    print(f"评级: {dict(by_grade)}")
    print(f"\n输出: {OUT} ({size:.0f} KB)")
    print("\n分级说明：A=完整可模拟（>=80题/>=4模块/覆盖率>=95%）")
    print("          B=中等（>=60题/>=4模块）  C=片段卷")

    print("\n各年 A 级套卷：")
    for x in out:
        if x["grade"] == "A":
            print(f"  {x['year']} {x['region']:<8} {x['total']:>3}题 "
                  f"{x['moduleCount']}模块  {x['paper'][:44]}")


if __name__ == "__main__":
    main()

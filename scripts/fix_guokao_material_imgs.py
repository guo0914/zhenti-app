"""修复 guokao 分片缺失的材料图片（[图] 占位符）与两处模块错分类

问题 1（严重，影响作答）：
  fetch_guokao.py / merge_guokao.py 建 guokao 分片时，把材料里的图表
  压成了字面 "[图]"，且 materialImgs 一律为空。而 papers-v5.js 渲染
  材料时只认 materialImgs，不解析 "[图]" 文本 —— 于是国考套卷里
  资料分析题只显示 "[图] [图]"，图表完全不可见，题目无法作答。
  实测：guokao 分片 121 题材料含 "[图]"，全部能从分类分片补到图片。

问题 2（模块错分类）：
  5445878 / 5893530（及 guokao 副本 gk-2023ds-5445878、
  gk-2024ds-5893530、gk-2024xz-5893530）是数量关系（数学运算）题，
  却被塞进 data 分片，并继承了同一份资料分析材料 —— 表现为
  「数量关系题上面顶着一段资料分析材料 / 资料分析图表」。

修法：
  1. 对 guokao 每条材料含 "[图]" 的题，按 srcQid 反查分类分片：
     · 材料正文（去 [图] 与空白后）与分类分片一致 → 直接用分类分片的
       material + materialImgs（格式更干净）
     · 不一致 → 保留 guokao 自己的正文（信息更全），只剔除 "[图]" 残字，
       并补上分类分片的 materialImgs
     · 缺 matNo 时用分类分片的 matNo 补齐（只影响「材料 N」标题）
  2. 那 5 条错分类题：从 data 分片移到 quantity 分片，cat → quantity，
     sub → 数学运算，清空 material / matNo / materialImgs，
     no 接到该卷 quantity 末尾。

用法：
  python scripts/fix_guokao_material_imgs.py            # 演练
  python scripts/fix_guokao_material_imgs.py --apply    # 写入
"""

import io
import json
import os
import re
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(ROOT, "site", "data", "zt")

BASE_CATS = ["politics", "common", "verbal", "quantity", "judge", "graph", "data"]
PLACEHOLDER = "[图]"

# 被错误塞进 data 分片的数量关系题（分类分片 id）
MISCLASSIFIED = ["5445878", "5893530"]

APPLY = "--apply" in sys.argv


def load(cat):
    path = os.path.join(ZT, cat + ".json")
    d = json.load(open(path, encoding="utf-8"))
    return d["questions"] if isinstance(d, dict) and "questions" in d else d


def save(cat, qs):
    path = os.path.join(ZT, cat + ".json")
    bak = path + ".matimgbak"
    if not os.path.exists(bak):
        shutil.copy(path, bak)
    json.dump(qs, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))


def norm(s):
    """去掉 [图] 与所有空白后用于比较。"""
    return re.sub(r"\s+", "", (s or "").replace(PLACEHOLDER, ""))


def strip_placeholder(s):
    """剔除 [图] 残字，并压掉因此产生的空行。"""
    s = (s or "").replace(PLACEHOLDER, "")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def base_index():
    idx = {}
    for cat in BASE_CATS:
        for q in load(cat):
            idx[str(q["id"])] = q
    return idx


def main():
    print("=" * 66)
    print("  修复 guokao 材料图片 / 模块错分类")
    print("=" * 66)
    print("  模式:", "写入" if APPLY else "演练")
    print()

    base = base_index()
    gk = load("guokao")
    data_qs = load("data")
    quantity_qs = load("quantity")

    print("=== 1) 材料 [图] 占位符 ===")
    hit = [q for q in gk if PLACEHOLDER in (q.get("material") or "")]
    print("  guokao 材料含 [图]:", len(hit))

    filled_img = filled_mat = filled_no = 0
    fail = []
    for q in hit:
        key = str(q.get("srcQid") or str(q["id"]).split("-", 2)[-1])
        src = base.get(key)
        if not src or not (src.get("materialImgs") or []):
            fail.append(q["id"])
            continue

        src_text = src.get("material") or ""
        if norm(q["material"]) == norm(src_text):
            q["material"] = src_text      # 分类分片的排版更干净
            filled_mat += 1
        else:
            q["material"] = strip_placeholder(q["material"])

        q["materialImgs"] = list(src["materialImgs"])
        filled_img += 1

        if not q.get("matNo") and src.get("matNo"):
            q["matNo"] = src["matNo"]
            filled_no += 1

    print("  补上 materialImgs:", filled_img)
    print("  材料正文采用分类分片版本:", filled_mat)
    print("  补齐 matNo:", filled_no)
    print("  补不到图片:", len(fail), fail[:5])

    print()
    print("=== 2) 模块错分类 ===")
    moved_ids = []

    # 2a) 分类分片：data → quantity
    for qid in MISCLASSIFIED:
        dq = next((x for x in data_qs if str(x["id"]) == qid), None)
        if not dq:
            print("  data 分片找不到", qid)
            continue
        paper = str(dq.get("paper") or "")
        same = [x for x in quantity_qs if (x.get("paper") or "") == paper]
        nums = [int(x["no"]) for x in same if str(x.get("no", "")).isdigit()]
        new_no = (max(nums) + 1) if nums else 1
        print("  data → quantity: %-10s no: %-3s → %-3s  sub=%-5s matLen=%d matImgs=%d" % (
            qid, dq.get("no"), new_no, dq.get("sub"),
            len(dq.get("material") or ""), len(dq.get("materialImgs") or [])))
        dq["cat"] = "quantity"
        dq["sub"] = "数学运算"
        dq["no"] = new_no
        for k in ("material", "materialImgs", "matNo"):
            dq.pop(k, None)
        data_qs.remove(dq)
        quantity_qs.append(dq)
        moved_ids.append(qid)

    # 2b) guokao 副本（同在 guokao.json 内，改 cat/sub/no 即可）
    for qid in MISCLASSIFIED:
        copies = [g for g in gk if str(g.get("srcQid") or "") == qid]
        for g in copies:
            paper = g.get("paper") or ""
            same = [x for x in gk
                    if (x.get("paper") or "") == paper and x.get("cat") == "quantity"]
            nums = [int(x["no"]) for x in same if str(x.get("no", "")).isdigit()]
            new_no = (max(nums) + 1) if nums else 1
            print("  guokao: %-22s no: %-3s → %-3s  sub=%s" % (
                g["id"], g.get("no"), new_no, g.get("sub")))
            g["cat"] = "quantity"
            g["sub"] = "数学运算"
            g["no"] = new_no
            for k in ("material", "materialImgs", "matNo"):
                g.pop(k, None)

    if not APPLY:
        print()
        print("  演练结束，加 --apply 写入。")
        return

    save("guokao", gk)
    save("data", data_qs)
    save("quantity", quantity_qs)
    print()
    print("  已写入 guokao.json / data.json / quantity.json")

    left = [q for q in gk if PLACEHOLDER in (q.get("material") or "")]
    noimg = [q for q in gk
             if not (q.get("material") or "") and not (q.get("materialImgs") or [])
             and q.get("sub") in ("增长", "比重", "平均数", "倍数", "综合")]
    print("  复核 guokao 残留 [图]:", len(left))
    print("  复核 guokao 资料题彻底无材料:", len(noimg))
    print("  复核分片题数: data=%d quantity=%d guokao=%d" % (
        len(data_qs), len(quantity_qs), len(gk)))


if __name__ == "__main__":
    main()

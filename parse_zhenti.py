"""
把 cache/ 下的真题 markdown 解析成结构化题目 JSON。

格式（每篇 markdown 的结构）：
    ---
    类型: "真题"
    试卷: "..."
    地区: "..."
    年份: "..."
    模块: "..."
    题数: "..."
    ---

    # 标题
    > 模块 · N 题 · 地区 年份

    ## 第 1 题　<sub>qid 123456 · 图形推理</sub>

    题干正文（可能含 <p> 与 <img src="../90-图片/题目图/xxx.png">）

    - **A**. 选项内容　✅      ← ✅ 表示正确答案
    - **B**. 选项内容
    ...

    **答案**：A

    **官方解析**

    解析正文

    ---

输出：
    data/zhenti.json   { meta, categories[], questions[] }
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "cache")
OUT_DIR = os.path.join(ROOT, "site", "data")
OUT_JSON = os.path.join(OUT_DIR, "zhenti.json")

# 六大类目录 → 展示分类
CATEGORY_DIRS = {
    "01-政治理论": "politics",
    "02-常识判断": "common",
    "03-言语理解与表达": "verbal",
    "04-数量关系": "quantity",
    "05-判断推理": "judge",
    "06-资料分析": "data",
}

# 判断推理需要把「图形推理」拆出来单列
GRAPH_SUB = "图形推理"
GRAPH_KEY = "graph"
JUDGE_KEY = "judge"

CATEGORY_META = {
    "politics": {"name": "政治理论", "short": "政治", "order": 1},
    "common":   {"name": "常识判断", "short": "常识", "order": 2},
    "verbal":   {"name": "言语理解与表达", "short": "言语", "order": 3},
    "quantity": {"name": "数量关系", "short": "数量", "order": 4},
    "graph":    {"name": "图形推理", "short": "图推", "order": 5},
    "judge":    {"name": "判断推理", "short": "判断", "order": 6},
    "data":     {"name": "资料分析", "short": "资料", "order": 7},
}

FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
META_LINE = re.compile(r'^([\u4e00-\u9fa5A-Za-z]+)\s*:\s*"?([^"\n]*)"?\s*$')
QUESTION_RE = re.compile(r"^##\s*第\s*(\d+)\s*题\s*[　\s]*<sub>qid\s*(\d+)\s*·\s*([^<]*)</sub>", re.M)
# 资料分析采用「## 材料 N」+「### 第 N 题」结构
MATERIAL_RE = re.compile(r"^##\s*材料\s*(\d+)\s*$", re.M)
SUBQ_RE = re.compile(r"^###\s*第\s*(\d+)\s*题\s*[　\s]*<sub>qid\s*(\d+)\s*·\s*([^<]*)</sub>", re.M)
# 实际格式：- **A**. 选项内容　✅   （加粗只包住字母，点号在加粗外）
OPTION_RE = re.compile(r"^-\s*\*\*([A-D])\*\*\.\s*(.*?)(?:\s*　✅)?\s*$", re.M)
ANSWER_RE = re.compile(r"^\*\*答案\*\*[：:]\s*(.+?)\s*$", re.M)
IMG_RE = re.compile(r'<img[^>]*src="([^"]+)"[^>]*>', re.I)
TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    """把 markdown 里内嵌的 HTML 标签去掉，保留文字，压缩空白。"""
    t = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    t = re.sub(r"</p>\s*<p[^>]*>", "\n", t, flags=re.I)
    t = TAG_RE.sub("", t)
    t = html.unescape(t)
    t = t.replace("\u200b", "")
    # 逻辑填空题的「横线」在原始数据里是连续的 \xa0（不间断空格），
    # 常见 8/10/12/20 个。直接转成普通空格会被下面的空白压缩清掉，
    # 导致题干里「形成 的整体风格」这种缺横线的情况。这里先还原成 ____。
    t = re.sub(r"\xa0{2,}", "____", t)
    # 交替形式：\xa0 \xa0 \xa0
    t = re.sub(r"(?:\xa0 ?){2,}", "____", t)
    t = t.replace("\xa0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# 解析中的图片（公式图 + 题目图）都要保留，转成 markdown 图片语法交给前端渲染。
# 早期只匹配「公式图」，解析段里的「题目图」被 strip_tags 一起剥掉，
# 表现为「右边数位从大到小依次为」这类断句里凭空少了图（定义判断、
# 图形推理、数量关系都受影响）。题目图必须一并保留。
EXPL_IMG = re.compile(r'<img[^>]*src="([^"]*(?:公式图|题目图)/[^"]+)"[^>]*>', re.I)


def explain_with_formulas(html_text: str) -> str:
    """保留解析里的公式图与题目图，其余标签剥掉。"""
    tokens: list[str] = []

    def repl(m):
        src = m.group(1)
        name = os.path.basename(src)
        if "公式图" in src:
            tokens.append(("公式", "assets/zt/formula/" + name))
        else:
            tokens.append(("图", "assets/zt/timu/" + name))
        return "\u0000%d\u0000" % (len(tokens) - 1)

    tmp = EXPL_IMG.sub(repl, html_text)
    tmp = strip_tags(tmp)
    for i, (alt, src) in enumerate(tokens):
        tmp = tmp.replace("\u0000%d\u0000" % i, "\n![%s](%s)\n" % (alt, src))
    return re.sub(r"\n{3,}", "\n\n", tmp).strip()


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = FRONT_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        mm = META_LINE.match(line.strip())
        if mm:
            meta[mm.group(1)] = mm.group(2).strip()
    return meta, text[m.end():]


def rewrite_img(src: str) -> str:
    """把仓库里的 ../90-图片/题目图/x.png 改成本地路径 assets/zt/timu/x.png。

    本地目录名是 ASCII（timu / formula），远程源仓库仍是中文目录，
    所以判据看远程路径里的「题目图」「公式图」，输出写 ASCII 目录。
    """
    name = os.path.basename(src)
    if "题目图" in src:
        return "assets/zt/timu/" + name
    if "公式图" in src:
        return "assets/zt/formula/" + name
    return src


def classify(cat_dir: str, sub: str) -> str:
    key = CATEGORY_DIRS[cat_dir]
    if key == JUDGE_KEY and GRAPH_SUB in (sub or ""):
        return GRAPH_KEY
    return key


def parse_file(path: str, cat_dir: str) -> list[dict]:
    raw = open(path, encoding="utf-8").read()
    meta, body = parse_front_matter(raw)
    paper = meta.get("试卷") or os.path.basename(path).replace(".md", "")
    year = meta.get("年份") or ""
    region = meta.get("地区") or ""

    # 资料分析是「## 材料 N」+「### 第 N 题」；其余模块是「## 第 N 题」
    sub_marks = list(SUBQ_RE.finditer(body))
    out: list[dict] = []

    if sub_marks:
        mats = list(MATERIAL_RE.finditer(body))
        for mi, mm in enumerate(mats):
            m_start = mm.end()
            m_end = mats[mi + 1].start() if mi + 1 < len(mats) else len(body)
            mat_no = int(mm.group(1))
            mat_block = body[m_start:m_end]
            mat_qs = [q for q in sub_marks if m_start <= q.start() < m_end]
            # 材料正文 = 第一个小题之前的全部内容
            first_q = mat_qs[0].start() if mat_qs else m_end
            mat_imgs = IMG_RE.findall(mat_block[:max(0, first_q - m_start)])
            mat_text = strip_tags(IMG_RE.sub("", mat_block[:max(0, first_q - m_start)]))
            mat_text = re.sub(r"^\s*-{3,}\s*$", "", mat_text, flags=re.M).strip()

            for i, m in enumerate(mat_qs):
                start = m.end()
                end = mat_qs[i + 1].start() if i + 1 < len(mat_qs) else m_end
                q = parse_block(body[start:end], m.group(1), m.group(2), m.group(3),
                                cat_dir, paper, year, region)
                if not q:
                    continue
                q["material"] = mat_text
                q["materialImgs"] = [rewrite_img(x) for x in mat_imgs]
                q["matNo"] = mat_no
                out.append(q)
        return out

    marks = list(QUESTION_RE.finditer(body))
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        q = parse_block(body[start:end], m.group(1), m.group(2), m.group(3),
                        cat_dir, paper, year, region)
        if q:
            out.append(q)
    return out


def parse_block(block: str, no_raw: str, qid: str, sub_raw: str,
                cat_dir: str, paper: str, year: str, region: str) -> dict | None:
    no = int(no_raw)
    sub = (sub_raw or "").strip()

    # 答案
    ans_m = ANSWER_RE.search(block)
    answer_raw = ans_m.group(1).strip() if ans_m else ""
    answer = answer_raw[:1].upper() if answer_raw[:1].upper() in "ABCD" else ""

    # 解析
    expl = ""
    em = re.search(r"\*\*官方解析\*\*\s*\n(.*)$", block, re.S)
    if em:
        expl = explain_with_formulas(em.group(1))
        expl = re.sub(r"^-{3,}\s*$", "", expl, flags=re.M).strip()

    # 截掉答案与解析，剩下题干 + 选项
    head = block
    if ans_m:
        head = block[:ans_m.start()]
    if em:
        cut = block.find("**官方解析**")
        if cut > 0 and len(head) > cut:
            head = head[:cut]

    # 判断题
    is_tf = bool(re.search(r"^-\s*（选项）\s*\[\s*\]\s*$", head, re.M))

    options = []
    for om in OPTION_RE.finditer(head):
        letter = om.group(1)
        content = strip_tags(om.group(2)).strip()
        options.append({"k": letter, "t": content})
    # 去重保序，最多 4 个
    seen, opts = set(), []
    for o in options:
        if o["k"] in seen:
            continue
        seen.add(o["k"])
        opts.append(o)
    opts.sort(key=lambda x: x["k"])
    opts = opts[:4]

    # 判断题补上固定的两个选项，保证前端能正常渲染
    if is_tf and len(opts) < 2:
        opts = [{"k": "A", "t": "正确"}, {"k": "B", "t": "错误"}]

    # 题干 = 去掉选项行后的文本
    stem_part = OPTION_RE.sub("", head)
    stem_part = re.sub(r"^-\s*（选项）\s*\[\s*\]\s*$", "", stem_part, flags=re.M)
    imgs = IMG_RE.findall(stem_part)
    stem = strip_tags(stem_part)
    stem = re.sub(r"^\s*-{3,}\s*$", "", stem, flags=re.M).strip()
    # 只去掉首尾空白，不能 strip("-")：数列题的题干可能以负号开头
    # （如「-3，-1，2，7，14，（ ）」），strip("- \n") 会把负号一起删掉，
    # 使题目变成另一个数列，答案也随之错误。
    stem = stem.strip()

    # 选项内容里也偶尔带图
    opt_imgs = []
    for om in OPTION_RE.finditer(head):
        opt_imgs.extend(IMG_RE.findall(om.group(2)))

        cat = classify(cat_dir, sub)
        return {
            "id": qid,
            "cat": cat,
            "sub": sub,
            "paper": paper,
            "year": year,
            "region": region,
            "no": no,
            "stem": stem,
            "options": [o["t"] for o in opts],
            "optionKeys": [o["k"] for o in opts],
            "answer": answer,
            "answerRaw": answer_raw,
            "explain": expl,
            "imgs": [rewrite_img(x) for x in (imgs + opt_imgs)],
            "tf": is_tf,
        }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    all_q: list[dict] = []
    papers = set()
    per_cat = Counter()
    stat = Counter()
    seen_ids = set()   # 全局 qid 去重

    for cat_dir in CATEGORY_DIRS:
        d = os.path.join(CACHE, cat_dir)
        if not os.path.isdir(d):
            continue
        files = sorted(f for f in os.listdir(d) if f.endswith(".md"))
        for fn in files:
            try:
                qs = parse_file(os.path.join(d, fn), cat_dir)
            except Exception as exc:
                print(f"  解析失败 {cat_dir}/{fn}: {exc}")
                stat["file_fail"] += 1
                continue
            papers.add(fn)
            stat["files"] += 1
            for q in qs:
                if not q["stem"] or len(q["options"]) < 2:
                    stat["bad"] += 1
                    continue
                # 去重：同一 qid 可能因多个「## 第 N 题」块被重复解析
                qid = str(q.get("id") or "")
                if qid:
                    if qid in seen_ids:
                        stat["dup"] = stat.get("dup", 0) + 1
                        continue
                    seen_ids.add(qid)
                if not q["answer"]:
                    stat["no_answer"] += 1
                all_q.append(q)
                per_cat[q["cat"]] += 1

    # 分类统计
    categories = []
    for key, meta in sorted(CATEGORY_META.items(), key=lambda kv: kv[1]["order"]):
        n = per_cat.get(key, 0)
        years = Counter(q["year"] for q in all_q if q["cat"] == key)
        papers_n = len({q["paper"] for q in all_q if q["cat"] == key})
        categories.append({
            "key": key,
            "name": meta["name"],
            "short": meta["short"],
            "count": n,
            "papers": papers_n,
            "years": dict(sorted(years.items())),
        })

    out = {
        "meta": {
            "name": "行测真题分类题库",
            "source": "ERRRC/xingcezhenti（2023–2026 国考+省考）",
            "papers": len(papers),
            "questions": len(all_q),
            "built": "2026-10-22",
        },
        "categories": categories,
        "questions": all_q,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))

    # 按分类切分，前端按需加载（避免首屏拉 12MB）
    split_dir = os.path.join(OUT_DIR, "zt")
    os.makedirs(split_dir, exist_ok=True)
    for cat in CATEGORY_META:
        qs = [q for q in all_q if q["cat"] == cat]
        fp = os.path.join(split_dir, f"{cat}.json")
        with open(fp, "w", encoding="utf-8") as fh:
            json.dump(qs, fh, ensure_ascii=False, separators=(",", ":"))
        print(f"  分片 {cat}.json: {len(qs)} 题 {os.path.getsize(fp)/1024:.0f} KB")

    # 轻量索引（分类 + 统计，不含题目）
    index = {
        "meta": out["meta"],
        "categories": [
            {k: v for k, v in c.items() if k != "questions"}
            for c in categories
        ],
    }
    with open(os.path.join(OUT_DIR, "zt-index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))

    # 轻量入口 js（只含分类索引，题目按分类分片按需加载）
    js = "window.__ZHENTI__ = " + json.dumps(
        {"meta": out["meta"], "categories": categories, "questions": []},
        ensure_ascii=False, separators=(",", ":")) + ";"
    with open(os.path.join(OUT_DIR, "zhenti.js"), "w", encoding="utf-8") as fh:
        fh.write(js)

    print(f"卷子 {len(papers)} 份，题目 {len(all_q)} 道")
    for c in categories:
        print(f"  {c['name']:12s} {c['count']:5d} 题 / {c['papers']:3d} 卷")
    print(f"  跳过(结构不完整) {stat['bad']}，无答案 {stat['no_answer']}")
    print(f"输出 {OUT_JSON} ({os.path.getsize(OUT_JSON)/1024:.0f} KB)")


if __name__ == "__main__":
    main()

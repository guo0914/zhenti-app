#!/usr/bin/env python3
"""从 ERRRC/xingcezhenti 采集国考指定卷，解析 Markdown 为结构化数据

源仓库文件格式（关键：带原卷题号）：
    ### 第 1 题　<sub>qid 19526404 · 语句表达</sub>
    题干文字...

    - **A**. 选项A
    - **B**. 选项B　✅        ← ✅ 标正确答案
    - **C**. ...
    - **D**. ...

    **答案**：D

    **官方解析**
    解析正文...

输出：law_ocr/guokao/<paper-slug>/<module>.json 及合并后的 papers JSON

用法：
  python scripts/fetch_guokao.py --paper "2023年国家公务员录用考试《行测》题（行政执法卷网友回忆版）"
  python scripts/fetch_guokao.py --all-targets
"""

import sys
import io
import os
import re
import json
import time
import argparse
import urllib.parse
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "..", "law_ocr", "guokao")

RAW_BASE = "https://raw.githubusercontent.com/ERRRC/xingcezhenti/main/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 模块 → 分类代码（与现有 zt 分片一致）
MODULES = [
    ("01-政治理论", "politics"),
    ("02-常识判断", "common"),
    ("03-言语理解与表达", "verbal"),
    ("04-数量关系", "quantity"),
    ("05-判断推理", "judge"),
    ("06-资料分析", "data"),
]

# 国考目标卷（地市级 + 行政执法卷，2023-2026）
TARGETS = []
for _y in (2023, 2024, 2025, 2026):
    for _sub in ("地市级", "行政执法卷"):
        TARGETS.append(f"{_y}年国家公务员录用考试《行测》题（{_sub}网友回忆版）")


def log(msg):
    import time as _t
    print(f"[{_t.strftime('%H:%M:%S')}] {msg}", flush=True)


CACHE_DIR = os.path.join(ROOT, "..", "law_ocr", "guokao_cache")


def fetch(url, retries=6):
    """带重试 + 本地缓存的下载。

    - 已缓存直接读本地（避免重复下载大文件）
    - 流式分块读取，避免大响应中途断开
    """
    # 缓存文件名用 URL 的 hash
    import hashlib
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.md5(url.encode()).hexdigest()[:16]
    cache_path = os.path.join(CACHE_DIR, key + ".md")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        try:
            txt = open(cache_path, encoding="utf-8").read()
            if txt:
                return txt
        except Exception:
            pass

    for i in range(retries):
        try:
            resp = urlopen(Request(url, headers=HEADERS), timeout=90)
            chunks = []
            while True:
                try:
                    buf = resp.read(64 * 1024)
                except Exception:
                    buf = b""
                if not buf:
                    break
                chunks.append(buf)
            data = b"".join(chunks)
            if data:
                txt = data.decode("utf-8", "replace")
                try:
                    open(cache_path, "w", encoding="utf-8").write(txt)
                except Exception:
                    pass
                return txt
        except Exception:
            pass
        time.sleep(2 + i * 2)
    return None


def clean_rich(text):
    """清理富文本：保留图片引用为占位标记，去掉 HTML 标签。

    源仓库用 <img flag="tex" src="../90-图片/公式图/xxx.png" /> 表示公式/图形，
    选项或题干可能整段都是图片。转成 [图] 占位，避免变成空白。
    """
    if not text:
        return ""
    # 图片 → 占位标记
    text = re.sub(r"<img[^>]*?src=\"([^\"]+)\"[^>]*?/?>", r"[图]", text)
    text = re.sub(r"<img[^>]*?/>", "[图]", text)
    # 段落标签 → 换行
    text = re.sub(r"</p>\s*<p[^>]*>", "\n", text)
    text = re.sub(r"</?p>", "\n", text)
    # 其它标签
    text = re.sub(r"<[^>]+>", "", text)
    # 清理多余空白
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def parse_md(text, cat, paper):
    """解析一个模块的 Markdown 为一个题目数组。

    返回 [{qid, no(原卷题号), cat, paper, stem, options[], optionKeys[],
           answer, explain, sub(题型), material}]
    """
    # 先按「第 N 题 + qid」切块
    # 注意标题层级不固定：可能是 "## 第 1 题" 或 "### 第 1 题"
    blocks = []
    pat = re.compile(
        r"^#{1,4}\s*第\s*(\d+)\s*题[\s\u3000]*<sub>\s*qid\s*(\d+)(?:\s*·\s*([^<]*))?</sub>",
        re.M)
    marks = list(pat.finditer(text))
    if not marks:
        # 兜底：标题行里只要有 第N题 和 qid
        pat2 = re.compile(r"^#{1,4}\s*第\s*(\d+)\s*题[^\n]*?qid\s*(\d+)", re.M)
        marks = list(pat2.finditer(text))
        if not marks:
            return []

    # 材料切分（## 材料 N / ### 材料 N）
    mat_marks = list(re.finditer(r"^#{1,4}\s*材料\s*(\d+)\s*$", text, re.M))

    def material_for(pos):
        """找到 pos 之前最近的材料，返回其正文。"""
        best = None
        for mm in mat_marks:
            if mm.start() < pos:
                best = mm
            else:
                break
        if not best:
            return ""
        start = best.end()
        # 材料正文到下一个标题（任意级别）为止
        nxt = re.search(r"^#{1,4}\s", text[start:], re.M)
        end = start + nxt.start() if nxt else len(text)
        raw = text[start:end].strip()
        return clean_rich(raw)

    for i, m in enumerate(marks):
        no = int(m.group(1))
        qid = m.group(2)
        sub = (m.group(3) or "").strip()
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()

        q = parse_one(body, cat, paper, qid, no, sub)
        if q:
            mat = material_for(m.start())
            if mat:
                q["material"] = mat
            blocks.append(q)

    return blocks


def parse_one(body, cat, paper, qid, no, sub):
    """解析单个题目正文。"""
    # 去掉结尾的分隔线
    body = re.sub(r"\n---+\s*$", "", body).strip()

    # 答案
    ans = ""
    m_ans = re.search(r"\*\*答案\*\*\s*[：:]\s*([A-D]{1,4})", body)
    if m_ans:
        ans = m_ans.group(1)
    else:
        # 兜底：从选项里找 ✅ 标记
        checks = re.findall(r"\*\*([A-D])\*\*\..*?✅", body)
        if checks:
            ans = "".join(sorted(set(checks)))

    # 官方解析
    explain = ""
    m_exp = re.search(r"\*\*官方解析\*\*\s*\n+([\s\S]*?)(?:\n---|\Z)", body)
    if m_exp:
        explain = m_exp.group(1).strip()
    else:
        m_exp2 = re.search(r"\*\*解析\*\*\s*\n+([\s\S]*?)(?:\n---|\Z)", body)
        if m_exp2:
            explain = m_exp2.group(1).strip()

    # 分割「题干」与「选项」
    # 选项行格式：- **A**. xxx
    opt_pat = re.compile(r"^-\s*\*\*([A-D])\*\*\.\s*(.*)$", re.M)
    opts = list(opt_pat.finditer(body))
    if opts:
        stem_raw = body[:opts[0].start()].strip()
    else:
        stem_raw = body
        # 没有选项 → 可能是判断/填空，保留题干
        if m_exp:
            stem_raw = body[:m_exp.start()].strip()

    # 清理题干：去掉答案/解析部分
    stem_raw = re.split(r"\*\*答案\*\*|\*\*官方解析\*\*|\*\*解析\*\*", stem_raw)[0].strip()
    stem_raw = clean_rich(stem_raw)

    # 提取选项
    #   关键：正则用了 re.M，`.*$` 只匹配到行尾，om.end() 在行末，
    #   所以不能用 om.end() 取内容，必须用 group(2) 拿本行文本，
    #   再把后续非选项行（续行）并进来。
    options = []
    keys = []
    if opts:
        for j, om in enumerate(opts):
            key = om.group(1)
            parts = [om.group(2).strip()]

            # 续行：本选项行之后到下一个选项行之前
            tail_start = om.end()
            tail_end = opts[j + 1].start() if j + 1 < len(opts) else len(body)
            tail = body[tail_start:tail_end]

            # 只保留续行里「不属于答案/解析」的部分
            cut = len(tail)
            for marker in ("**答案**", "**官方解析**", "**解析**", "\n---"):
                pos = tail.find(marker)
                if pos >= 0:
                    cut = min(cut, pos)
            tail = tail[:cut]

            # 续行里可能有 <p> 包裹的补充文字，转成纯文本
            tail_clean = clean_rich(tail).strip()
            if tail_clean:
                parts.append(re.sub(r"\s+", " ", tail_clean))

            vtxt = " ".join(p for p in parts if p)
            vtxt = re.sub(r"✅\s*$", "", vtxt).strip()
            vtxt = re.sub(r"\s+", " ", vtxt).strip()

            keys.append(key)
            options.append(vtxt)

    stem = re.sub(r"\s+", " ", stem_raw).strip()
    if not stem:
        return None

    return {
        "qid": qid,
        "no": no,
        "cat": cat,
        "paper": paper,
        "sub": sub,
        "stem": stem,
        "options": options,
        "optionKeys": keys,
        "answer": ans,
        "explain": re.sub(r"\s+", " ", clean_rich(explain)).strip(),
    }


def slug(paper):
    """卷名转文件安全名。"""
    s = re.sub(r"[（）()《》\s]", "_", paper)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:80]


def fetch_paper(paper):
    """采集一卷的所有模块（网络失败自动重试，缺失的模块记录在案）。"""
    results = []
    mods_hit = []
    mods_miss = []
    for mod_name, cat in MODULES:
        url = RAW_BASE + urllib.parse.quote(mod_name + "/" + paper + ".md")
        text = fetch(url)
        if text is None:
            mods_miss.append(cat)
            continue
        qs = parse_md(text, cat, paper)
        if qs:
            results.extend(qs)
            mods_hit.append(f"{cat}:{len(qs)}")
        else:
            mods_miss.append(cat)
    return results, mods_hit, mods_miss


def main():
    ap = argparse.ArgumentParser(description="采集国考行测卷")
    ap.add_argument("--paper", default=None, help="指定单卷")
    ap.add_argument("--all-targets", action="store_true", help="采集全部目标卷")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    papers = TARGETS if args.all_targets else ([args.paper] if args.paper else [])
    if not papers:
        print("请指定 --paper 或 --all-targets")
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    log(f"目标 {len(papers)} 卷")

    summary = []
    for paper in papers:
        log(f"采集: {paper}")
        try:
            qs, mods, miss = fetch_paper(paper)
        except Exception as e:
            log(f"  失败: {str(e)[:60]}")
            continue
        if not qs:
            log("  无数据")
            continue

        # 按原卷题号排序
        qs.sort(key=lambda q: (q["no"], q["cat"]))

        path = os.path.join(args.out, slug(paper) + ".json")
        json.dump({
            "paper": paper,
            "total": len(qs),
            "modules": mods,
            "modulesMissing": miss,
            "questions": qs,
        }, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        nodup = len({q["qid"] for q in qs})
        log(f"  {len(qs)} 题（唯一 qid {nodup}）模块 {', '.join(mods)}"
            + (f" | 缺失 {','.join(miss)}" if miss else ""))
        summary.append({"paper": paper, "total": len(qs), "unique": nodup,
                        "modules": mods, "missing": miss, "file": path})

    log("=" * 60)
    log("采集完成")
    for s in summary:
        print(f"  {s['total']:>4} 题  {s['paper'][:50]}", flush=True)

    json.dump(summary, open(os.path.join(args.out, "_summary.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()

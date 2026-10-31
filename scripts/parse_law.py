#!/usr/bin/env python3
"""法考真金题 OCR 文本 → 结构化题库 JSON

输入：ocr_law.py 输出的 JSONL（每页一条，含左右栏的行级文本）
输出：{科目}.json，题目数组

处理的排版特征（真金题系列）：
  题号：18. 或 18、
  出处：（2023金题-1-2-1，多）  单=单选 多=多选
  选项：A. 或 A、
  考点：[考点］内容
  解析：[解析］内容，末尾常有「本题答案为BD」
  答案：从解析末尾提取「本题答案为X」「答案：X」

用法：
  python scripts/parse_law.py --in ../law_ocr/xingfa.jsonl --out ../law_ocr/xingfa.json --subject 刑法 --author 柏浪涛
"""

import sys, io, os, re, json, argparse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── 正则 ──
RE_QNO = re.compile(r"^\s*(\d{1,3})[.、]\s*(.+)$")
RE_OPTION = re.compile(r"^([A-D])[.、]\s*(.*)$")
# 出处：兼容「2023金题-1-2-1，多」「2015-2-51，多」「2016-2-89，任」
# 注意 OCR 噪声：「金题-」常被识别成「金题一」，括号可能未闭合
RE_SOURCE = re.compile(
    r"[（(]\s*(\d{4})\s*(?:金题)?\s*[-\s—–一]\s*([\d\-—–一]+?)\s*[，,]?\s*([单多任])\s*[)）]?"
)
# 考点标记：兼容两种书
#   刑法系：[考点］xxx    民法系：考点11：xxx
RE_KAODIAN = re.compile(
    r"(?:[\[［【]\s*考点\s*[\]］】])"          # [考点]
    r"|(?:考点\s*\d+\s*[：:])"                 # 考点11：
)
# 解析标记：兼容三种书
#   刑法系：[解析］xxx
#   民法系：[解题思路】xxx / 【解题思路】
#   民诉系：[分析与思路］xxx / [分析]xxx
RE_JIEXI = re.compile(
    r"(?:[\[［【]\s*解析\s*[\]］】])"                # [解析]
    r"|(?:[\[［【]\s*解题思路\s*[\]］】])"           # [解题思路】【解题思路】
    r"|(?:[\[［【]\s*解题思路)"                     # [解题思路（未闭合）
    r"|(?:解题思路\s*[\]］】])"                      # 解题思路】
    r"|(?:[\[［【]\s*分析与思路\s*[\]］】]?)"        # [分析与思路]
    r"|(?:[\[［【]\s*分析\s*[\]］】])"               # [分析]
)
# 答案标记：兼容两种书
#   刑法系：本题答案为X    民法系：本题的正确答案为X / 正确答案为X
RE_ANSWER = re.compile(
    r"(?:本题的?正确答案|正确答案|本题答案|答案)\s*(?:为|是)?\s*[：:]?\s*([A-D]{1,4})"
)
RE_PAGE_NO = re.compile(r"^\d{1,4}$")
# 章节：兼容「第X讲/章/编」（刑法）与「专题X」（民法）
RE_CHAPTER = re.compile(
    r"(?:第([一二三四五六七八九十百零\d]+)(讲|章|编))"
    r"|(?:专题([一二三四五六七八九十百零\d]+))"
)
# 章节名（用于从题干里剔除）
RE_CHAPTER_LEAD = re.compile(
    r"^(?:第[一二三四五六七八九十百零\d]+[讲章编]|专题[一二三四五六七八九十百零\d]+)"
    r"[^。？?]{0,30}"
)

# OCR 常见错字修正
OCR_FIXES = [
    ("［", "["), ("］", "]"), ("【", "["), ("】", "]"),
    ("自已", "自己"),
]

# 水印/噪点（扫描版 PDF 的网站水印、页码、投影标记）
WATERMARK_PATTERNS = [
    r"网盘好\S{0,2}",      # 「网盘好」水印残留
    r"风盘好友[:：]?",     # 「风盘好友」水印残留
    r"金盾招警圆梦藏蓝",
    r"金盾招警",
    r"PROJECT\d+",         # 章节投影标记
    r"^\d{2,3}$",          # 孤立页码
    # 版式残留
    r"[①②③④⑤⑥⑦⑧⑨⑩]\s*见本书第\d+题[。，,]?",  # 脚注引用
    r"[①②③④⑤⑥⑦⑧⑨⑩]\s*参见[^，。]{0,20}[。，,]?",  # 脚注参见
    r"续表",               # 表格续标记
    r"接下页",             # 分页标记
    r"转下页",
    r"（?见本书第\d+题）?[。，,]?",   # 无编号的引用
]

# 脚注/版式痕迹：选项里出现这些，直接截断到该位置之前
LAYOUT_ARTIFACT = re.compile(
    r"(?:[①②③④⑤⑥⑦⑧⑨⑩]\s*(?:见|参见|详见)本书第\d+题|"
    r"续表|接下页|转下页|"
    r"[①②③④⑤⑥⑦⑧⑨⑩]\s*见[^，。]{0,15}[。，,])"
)


def clean_watermark(s):
    """清除 OCR 结果里混入的水印与噪点。"""
    if not s:
        return s
    for pat in WATERMARK_PATTERNS:
        s = re.sub(pat, "", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def fix_ocr(s):
    for a, b in OCR_FIXES:
        s = s.replace(a, b)
    return s


def load_pages(path):
    """读 JSONL，返回按页序的列表。"""
    pages = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                pages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    pages.sort(key=lambda p: p["page"])
    return pages


def page_lines(page):
    """把一页的左右栏还原成连贯的行序列。

    返回 [(text, score, col), ...]，col 为 'L'/'R'。
    双栏时左栏全部 → 右栏全部。
    """
    out = []
    for col, key in (("L", "left"), ("R", "right")):
        for item in page.get(key, []):
            out.append((item["t"], item.get("s", 1.0), col))
    return out


def split_page_boundary(lines):
    """处理跨页拼接的问题。

    真金题排版：一道题的解析可能跨到下一页。
    这里不做分割，让上层按题号自然切分即可。
    """
    return lines


def parse_chapter(header_texts, page_texts=None):
    """从页眉或页面正文提取章节名。

    两种书的两套体系：
      刑法系：第一讲 刑法论 / 第四讲 行为
      民法系：专题三 民事法律行为 / 专题七 所有权
    清理 OCR 噪声符号（○、⊙、● 等）并统一格式。
    """
    def norm(s):
        s = re.sub(r"[○⊙●◎◇◆□■△▲※☆★\s]+", " ", s)
        m = RE_CHAPTER.search(s)
        if not m:
            return ""
        if m.group(1):   # 第X讲/章/编
            title = s[m.end():]
            title = re.sub(r"[^\u4e00-\u9fff（）()、，,．.\w]", "", title).strip()
            title = re.sub(r"^(?:第[一二三四五六七八九十]+节|第\d+节)", "", title).strip()
            return f"第{m.group(1)}{m.group(2)} {title}".strip()
        # 专题X
        num = m.group(3)
        title = s[m.end():]
        title = re.sub(r"[^\u4e00-\u9fff（）()、，,．.\w]", "", title).strip()
        # 去掉紧跟的「第一节」「考点11：」等
        title = re.sub(r"^第[一二三四五六七八九十\d]+节", "", title).strip()
        title = re.sub(r"^考点\d+[：:]?", "", title).strip()
        title = title[:20]
        return f"专题{num} {title}".strip()

    for h in header_texts or []:
        r = norm(h)
        if r:
            return r
    for t in (page_texts or [])[:3]:
        r = norm(t)
        if r:
            return r
    return ""


def page_offset(pages):
    """计算 PDF 物理页码与书印页码的偏移量。

    扫描版 PDF 前面通常有封面、版权、目录等未编号页，
    导致物理页码（1-based）比书印页码大一个固定值。
    做法：统计每页页脚的数字，取众数差值。
    """
    from collections import Counter
    diffs = Counter()
    for p in pages:
        foot = p.get("footer") or []
        num = None
        for f in foot:
            m = re.fullmatch(r"\s*(\d{1,4})\s*", str(f))
            if m:
                num = int(m.group(1))
                break
        if num and 0 < num < p["page_no"]:
            diffs[p["page_no"] - num] += 1
    if not diffs:
        return 0
    # 取出现次数最多的差值，且要求至少 3 次、占比 > 50%
    best, cnt = diffs.most_common(1)[0]
    total = sum(diffs.values())
    if cnt < 3 or cnt / total < 0.5:
        return 0
    return best


def parse_questions(pages, subject, author):
    """核心：把行序列切分成题目。"""
    offset = page_offset(pages)
    if offset:
        print(f"  页码偏移: PDF 页码 - {offset} = 书印页码")
    # 1. 先合并成一个大行流，带页码溯源
    stream = []   # [(text, score, page_no, chapter)]
    last_chapter = ""
    for page in pages:
        page_lines_text = [i["t"] for i in page.get("left", []) + page.get("right", [])]
        chapter = parse_chapter(page.get("header", []), page_lines_text)
        if chapter:
            last_chapter = chapter
        for text, score, col in page_lines(page):
            text = fix_ocr(text.strip())
            if not text or RE_PAGE_NO.fullmatch(text):
                continue
            stream.append({
                "text": text,
                "score": score,
                "page": page.get("page_no"),
                "chapter": last_chapter,
            })

    # 2. 按「题号」切分为题目块
    blocks = []
    cur = None
    for item in stream:
        t = item["text"]
        m = RE_QNO.match(t)
        # 题号特征：1-3 位数字 + 顿号/点 + 后面是题干（长度 > 8）
        if m and len(m.group(2)) > 8:
            if cur:
                blocks.append(cur)
            cur = {
                "no": int(m.group(1)),
                "items": [dict(item, text=m.group(2))],
                "page": item["page"],
                "chapter": item["chapter"],
            }
        elif cur is not None:
            cur["items"].append(item)
    if cur:
        blocks.append(cur)

    # 3. 每个块内解析出题干/选项/考点/解析/答案
    questions = []
    for b in blocks:
        q = parse_block(b, subject, author)
        if q:
            # 页码转换：PDF 物理页 → 书印页码
            if offset and q.get("page"):
                q["pdfPage"] = q["page"]
                q["page"] = q["page"] - offset
            questions.append(q)

    # 3.5 答案回填：跨栏/跨页导致某题的答案落在下一题块首
    #     若上一题无答案、且本题块首带 orphan 答案 → 补给上一题
    for i in range(1, len(questions)):
        cur, prev = questions[i], questions[i - 1]
        orphan = cur.pop("_orphanAnswer", "")
        if orphan and not prev.get("answer"):
            # 仅当两题相邻（题号差 1）且上一题确实缺答案时回填
            try:
                adjacent = int(cur["no"]) - int(prev["no"]) == 1
            except (ValueError, TypeError):
                adjacent = False
            if adjacent:
                prev["answer"] = orphan
                # 缺答案标记也一并清除
                if "缺答案" in (prev.get("flags") or []):
                    prev["flags"] = [f for f in prev["flags"] if f != "缺答案"]

    # 4. 题号去重排序（跨页重复的题号保留信息更全的一条）
    by_no = {}
    for q in questions:
        n = q["no"]
        if n not in by_no or len(q["stem"]) > len(by_no[n]["stem"]):
            by_no[n] = q
    return sorted(by_no.values(), key=lambda x: x["no"]), len(blocks)


def sanitize_option(text, stem=""):
    """选项正文的最后一道保底清洗。

    无论前面切分多准，都会残留少量污染（OCR 丢失标记等）。
    这里直接按「污染特征」截断，宁可让选项短一点也不留垃圾。

    stem 用于检测「跨栏错位」：选项里出现与题干无关的解析片段。
    """
    if not text:
        return text
    t = str(text).strip()

    # 0. 版式残留（脚注引用、续表标记）—— 直接截断
    m_art = LAYOUT_ARTIFACT.search(t)
    if m_art and m_art.start() > 3:
        t = t[:m_art.start()].strip()

    # 污染起点特征（出现即截断）
    POLLUTE_START = [
        r"综上",
        r"本题的?正确答案",
        r"本题答案为",
        r"[\[［【]?\s*民事法律关系示意图",
        r"[\[［【]?\s*刑事法律关系示意图",
        r"[\[［【]?\s*法律关系示意图",
        r"[\[［【]?\s*示意图",
        r"[\[［【]?\s*有体系",
        r"[\[［【]?\s*知识体系",
        r"[\[［【]?\s*解题思路",
        r"[\[［【]?\s*分析与思路",
        r"[\[［【]?\s*题支逐项",
        r"[\[［【]?\s*题干信息",
        r"[\[［【]?\s*命题陷阱",
        r"[\[［【]?\s*命题思路",
        r"[\[［【]?\s*角度拓展",
        r"[\[［【]?\s*总结与归纳",
        r"[\[［【]?\s*应试技巧",
        r"[\[［【]?\s*解析[\]］】]",
        r"考点\s*\d+\s*[：:]",
        r"PROJECT\s*\d+",
        r"专题[一二三四五六七八九十百零\d]+",
    ]
    cut = len(t)
    for pat in POLLUTE_START:
        m = re.search(pat, t)
        # 只在其后还有内容时才截断；且不能把整个选项都切掉
        if m and 3 < m.start() < cut:
            cut = m.start()

    # 「故X项说法正确/错误」「X项说法正确」属于逐项分析，从该句句首切
    m = re.search(r"(?:故)?[A-D]项(?:说法)?(?:正确|错误)", t)
    if m and m.start() > 8:
        # 往前找最近句号，从那一句开头切
        prev_dot = t.rfind("。", 0, m.start())
        cut_at = prev_dot + 1 if prev_dot > 5 else m.start()
        cut = min(cut, cut_at)

    t = t[:cut].strip()
    # 附加规则：选项正文里出现「术语解释」特征（如「X是指」「所谓X」）
    # 且选项已经较长（>100字），说明解析混入，在「。X是指」处截断
    if len(t) > 100:
        m_def = re.search(r"[。]\s*(?=(?:所谓|.{2,10}(?:是指|是谓|即指)))[^。]{10,}", t)
        if m_def and m_def.start() > 15:
            t2 = t[:m_def.start() + 1].strip()
            if len(t2) >= 10:
                t = t2

    # 长度兜底：法考选项极少超过 220 字，超出部分必是解析混入
    # 取前 220 字，并在最后一个句号处收尾
    if len(t) > 220:
        head = t[:220]
        last_dot = head.rfind("。")
        t = (head[:last_dot + 1] if last_dot > 60 else head).strip()

    # 关键兜底：按「解析性语句」特征找边界
    #   仅在选项已经偏长（>55字）时启用，避免误伤正常短选项
    if len(t) > 55:
        ANALYSIS_START = re.compile(
            r"[。]\s*(?="
            r"(?:[A-D]项(?:考查|说法|表述)|"
            r"关键词为|"
            r"本题考查|本题综合考查|本专题|"
            r"所谓|首先[，,]|其次[，,]|最后[，,]|"
            r"\(1\)|（1）|"
            r"根据《|按照《|依据《|"
            r"故[A-D]项|因此[，,])"
            r")"
        )
        m_cut = ANALYSIS_START.search(t)
        if m_cut and m_cut.start() > 20:
            t2 = t[:m_cut.start()].strip()
            if len(t2) >= 6:
                t = t2

    # 跨栏错位检测：选项混入「不属于本题」的解析片段
    #   特征1：出现「X项考查」「关键词为」「故X项正确」等解析句式
    #   特征2：出现「系有权处分」「依法应…承担违约责任」这类解析结论
    if len(t) > 25:
        m_cross = re.search(
            r"(?:[A-D]项(?:考查|说法)|关键词为|故[A-D]项(?:说法)?(?:正确|错误)|"
            r"系有权处分|系无权处分|依法应[向]?\S{0,8}承担|"
            r"本题中[，,]|不当选|当选[，,。])",
            t)
        if m_cross and m_cross.start() > 8:
            head = t[:m_cross.start()]
            last_dot = head.rfind("。")
            t = (head[:last_dot + 1] if last_dot > 5 else head).strip()

    # 跨栏错位检测2：选项里出现「题干中完全没有的专有名词 + 解析动词」
    #   （例如题干讲"债权转让"，选项里出现"包销合同"）
    if stem and len(t) > 25:
        # 提取题干里的双字词作为「本题话题」
        stem_words = set(re.findall(r"[\u4e00-\u9fff]{2,4}", stem))
        # 找选项里的「XX合同/XX权/XX罪」等专有名词
        for m_noun in re.finditer(r"[\u4e00-\u9fff]{2,6}(?:合同|协议|权利|行为|罪名|罪)", t):
            noun = m_noun.group(0)
            core = noun[:-2] if len(noun) > 2 else noun
            # 该名词（或其核心）在题干里完全没出现 → 是外来话题
            if core and core not in stem and noun not in stem:
                pos = m_noun.start()
                if pos > 6:
                    head = t[:pos]
                    last_dot = head.rfind("。")
                    t = (head[:last_dot + 1] if last_dot > 5 else head).strip()
                    break

    # 去掉尾部的残缺标点
    t = re.sub(r"[，,、；;：:]+$", "", t).strip()
    return t


def parse_block(block, subject, author):
    """解析单个题目块。

    核心策略：不用「逐行状态机」（对 OCR 的乱序很脆弱），
    改用「全文一次切分」——先把所有行拼成一整段文本，
    再用正则按标记位置切分。这样能正确处理：
      - 选项 A 与题干挤在同一行（如「...单)A.虽然大火...」）
      - 选项字母被 OCR 漏掉（C 内容接在 B 后面）
      - [解析] 标记出现在行中间
    """
    items = block["items"]
    if not items:
        return None

    # 1. 拼成整段，行间用空格（避免把两行文字粘连）
    full = " ".join(i["text"].strip() for i in items)
    full = re.sub(r"\s{2,}", " ", full).strip()
    if not full:
        return None

    # 1.5 预清理：切掉「跨页带进来的下一题开头」
    #     题号切分保证 full 以本题题号开头，但末尾可能带下一题的内容。
    #     民法常见形态：本题解析结束后紧跟「30.某旅游地...」下一题，
    #     但那种已被题号切分处理。此处只处理「解析区尾部混入下一题选项」。
    #     做法：找到本题答案标记后，截断其后的所有内容。
    m_ans_early = RE_ANSWER.search(full)
    if m_ans_early:
        # 只截断「答案标记之后」明显属于下一题的内容（有下一题号）
        after_ans = full[m_ans_early.end():]
        m_next_no = re.search(r"\s\d{1,3}[.、][\u4e00-\u9fff]", after_ans)
        if m_next_no:
            full = full[:m_ans_early.end() + m_next_no.start()].strip()

    # 2.2 跨栏归位：切除块首「属于上一题的」答案残留
    #     双栏排版下，上一题的解析可能延续到本块前部，
    #     表现为块首（第一个选项之前）出现「本题的正确答案为X」。
    #     这类内容属于上一题，由 parse_questions 的答案回填逻辑处理。
    m_first_opt = re.search(r"(?:^|[^A-Za-z0-9])(A)[.、．]\s*", full)
    orphan_answer = ""
    if m_first_opt:
        # 注意：要从字母 A 的位置开始切，不能从匹配起点（可能含标点）
        head_zone = full[:m_first_opt.start(1)]
        m_ans = RE_ANSWER.search(head_zone)
        if m_ans:
            orphan_answer = m_ans.group(1)
            full = full[m_first_opt.start(1):]
    else:
        m_ans = RE_ANSWER.search(full[:800])
        if m_ans:
            orphan_answer = m_ans.group(1)

    # 2. 出处
    source = ""
    src_tag = ""
    m_src = RE_SOURCE.search(full)
    if m_src:
        num_part = re.sub(r"[—–一]", "-", m_src.group(2))
        source = f"{m_src.group(1)}金题-{num_part}"
        src_tag = m_src.group(3)

    # 3. 切出【解析】之后的部分（含「解析」标记可能带各种括号）
    jiexi = ""
    _need_jiexi_from_options = False
    m_jx = RE_JIEXI.search(full)
    if m_jx:
        jiexi = full[m_jx.end():].strip()
        head = full[:m_jx.start()].strip()
    else:
        # 没有解析标记的书（如商经知）：解析就是「选项之后的正文」
        # 解法：先切出选项区，选项结束后的内容即为解析。
        # 在 head 阶段无法确定，这里先保留全文，
        # 由后面第 5 步切完选项后用剩余部分当解析。
        head = full
        _need_jiexi_from_options = True

    # 4. 从 head 里切出【考点】
    #    关键：考点是「一行短语」，解析是长段落。
    #    OCR 常丢失 [解析] 标记，导致考点吞掉整段解析。
    #    策略：
    #      1. 若 kd_zone 里有 [解析] 标记 → 考点 = 标记前，解析 = 标记后
    #      2. 否则在「第一个句号」或「（一）项/（1）」处截断考点，
    #         并把截断后的余下部分【保留为解析】（不能丢）
    kaodian = ""
    m_kd = RE_KAODIAN.search(head)
    if m_kd:
        kd_start, kd_end = m_kd.start(), m_kd.end()
        head_before = head[:kd_start].strip()
        kd_zone = head[kd_end:]

        # 优先：kd_zone 内有 [解析] 标记
        m_jx2 = RE_JIEXI.search(kd_zone)
        if m_jx2:
            kaodian = kd_zone[:m_jx2.start()].strip()
            extra_jiexi = kd_zone[m_jx2.end():].strip()
        else:
            # 找考点终止点
            cut = len(kd_zone)
            # 句号
            m_dot = re.search(r"[。！？]", kd_zone)
            if m_dot:
                cut = min(cut, m_dot.end())
            # （一）项 / （1）这类解析条目
            m_num = re.search(r"[（(]\s*[一二三四五六七八九十\d]+\s*[)）]\s*项?", kd_zone)
            if m_num and m_num.start() > 2:
                cut = min(cut, m_num.start())
            # 硬上限 80 字
            cut = min(cut, 80)

            kaodian = kd_zone[:cut].strip()
            # 关键：余下部分作为解析，不能丢
            extra_jiexi = kd_zone[cut:].strip()

        # 考点再清理
        m_num2 = re.search(r"[（(]\s*[一二三四五六七八九十\d]+\s*[)）]\s*项?", kaodian)
        if m_num2 and m_num2.start() > 2:
            extra_jiexi = kaodian[m_num2.start():].strip() + " " + extra_jiexi
            kaodian = kaodian[:m_num2.start()].strip()
        # 考点是「术语短语」，特征是：短、常以「、」分隔、不含逗号引导的叙述句
        # 出现逗号 + 叙述性词语，即视为混入正文
        m_rule = re.search(
            r"[，,]\s*(?:法?定|应当|可以|如果|若|因此|经过|包括|所谓|是指|坦白|"
            r"骗|胁|制造|获取|检举|例如|比如|第一|第二|第三)", kaodian)
        if m_rule and m_rule.start() > 2:
            extra_jiexi = kaodian[m_rule.start():].strip() + " " + extra_jiexi
            kaodian = kaodian[:m_rule.start()].strip()
        # 额外：逗号后是「2字及以上 + 动词/名词短语」，且整串已超 20 字 → 截断
        if len(kaodian) > 20:
            m_comma = re.search(r"[，,]\s*\S{2,}", kaodian)
            if m_comma and m_comma.start() > 4:
                head_part = kaodian[:m_comma.start()].strip()
                # 前半部分是纯术语（含顿号或短）才截断
                if len(head_part) >= 4:
                    extra_jiexi = kaodian[m_comma.start():].strip() + " " + extra_jiexi
                    kaodian = head_part

        # 纯长度兜底：考点通常 <= 30 字（多个术语用顿号连接）
        if len(kaodian) > 30:
            # 优先在顿号处截断
            cut = kaodian.rfind("、", 0, 30)
            if cut > 4:
                extra_jiexi = kaodian[cut + 1:].strip() + " " + extra_jiexi
                kaodian = kaodian[:cut].strip()
            else:
                cut = kaodian.rfind("，", 0, 30)
                if cut > 4:
                    extra_jiexi = kaodian[cut + 1:].strip() + " " + extra_jiexi
                    kaodian = kaodian[:cut].strip()
                else:
                    extra_jiexi = kaodian[30:].strip() + " " + extra_jiexi
                    kaodian = kaodian[:30].strip()

        # 去掉不配对的括号残片
        if kaodian.count("（") != kaodian.count("）"):
            kaodian = re.sub(r"[（(][^（）()]*$", "", kaodian).strip()
        kaodian = re.sub(r"^[）)，,、]+", "", kaodian).strip()
        kaodian = re.sub(r"[）)，,、]+$", "", kaodian).strip()

        # 把考点之后的内容并入解析
        if extra_jiexi:
            jiexi = (extra_jiexi + " " + jiexi).strip() if jiexi else extra_jiexi

        head = head_before

    # 5. 从 head 里切出选项
    #    找到第一个选项标记（A. / A、/ A．），其后全是选项
    #    注意：选项之间可能跨行，B.xxx C.xxx 在同一行
    opts = {}
    opt_zone_start = -1
    # 找出所有选项标记位置
    # 选项标记：「A.」「A、」「A．」三种
    #  危险：正文常出现「A、B两市」这类并列词，会被误当选项标记
    #  规避：优先用「A.」「A．」（点号），只有找不到点号形式时才退化用「A、」
    OPT_MARK_DOT = re.compile(r"(?:^|[^A-Za-z0-9])([A-D])[.．]\s*")
    OPT_MARK_DUN = re.compile(r"(?:^|[^A-Za-z0-9])([A-D])[、]\s*(?=[\u4e00-\u9fff])")

    opt_marks = [(m.start(1), m.group(1), m.end())
                 for m in OPT_MARK_DOT.finditer(head)]
    # 点号标记少于 3 个时，补充顿号标记（部分书用「A、」）
    if len(opt_marks) < 3:
        seen = {x[1] for x in opt_marks}
        for m in OPT_MARK_DUN.finditer(head):
            if m.group(1) not in seen:
                opt_marks.append((m.start(1), m.group(1), m.end()))
                seen.add(m.group(1))
        opt_marks.sort()

    if opt_marks:
        a_marks = [x for x in opt_marks if x[1] == "A"]
        start_pos = a_marks[0][0] if a_marks else opt_marks[0][0]
        # 记录「选项区在 head 中的起始位置」，用于答案提取定位
        opt_zone_start = len(head) - len(head[start_pos:]) if start_pos else 0

        stem_raw = head[:start_pos].strip()
        opt_zone = head[start_pos:]

        marks_in_zone = [(m.start(1), m.group(1), m.end())
                         for m in OPT_MARK_DOT.finditer(opt_zone)]
        if len(marks_in_zone) < 3:
            seen = {x[1] for x in marks_in_zone}
            for m in OPT_MARK_DUN.finditer(opt_zone):
                if m.group(1) not in seen:
                    marks_in_zone.append((m.start(1), m.group(1), m.end()))
                    seen.add(m.group(1))
            marks_in_zone.sort()

        # ── 关键：选项正文必须在「板块标记」处截断 ──
        # 各书在选项之后紧跟解析/图示/补充板块，若只切到下个选项标记，
        # 这些内容会被并进最后一个选项（实测民法污染率 27%）。
        # 因此：先找「第一个板块标记」的位置，选项区只保留其之前的部分。
        BLOCK_MARK = re.compile(
            r"(?:[\[［【]\s*)?"
            r"(?:题干信息解读|命题陷阱|命题思路|题支逐项解析|题支逐项|题支解析|"
            r"选项分析|角度拓展|角度\s*\d|总结与归纳|应试技巧|应试提示|"
            r"民事法律关系示意图|刑事法律关系示意图|法律关系示意图|示意图|"
            r"有体系|知识体系|体系图|思维导图|"
            r"解题思路|分析与思路|本题解析|解析|考点|注意|提示|说明|归纳|拓展|"
            r"命题规律|命题角度|考点拓展|真题链接|相关规定|法条链接)"
            r"(?:\s*[\]］】])?"
        )
        m_block_any = BLOCK_MARK.search(opt_zone)
        # 板块标记必须不在选项区最开头（否则可能是选项正文的一部分）
        block_tail = ""      # 被截掉的板块区（含解析），用于解析提取
        if m_block_any and m_block_any.start() > 10:
            opt_zone_clean = opt_zone[:m_block_any.start()].strip()
            block_tail = opt_zone[m_block_any.start():].strip()
        else:
            opt_zone_clean = opt_zone

        # 用清理后的选项区重新切分
        marks_clean = [(m.start(1), m.group(1), m.end())
                       for m in OPT_MARK_DOT.finditer(opt_zone_clean)]
        if len(marks_clean) < 3:
            seen = {x[1] for x in marks_clean}
            for m in OPT_MARK_DUN.finditer(opt_zone_clean):
                if m.group(1) not in seen:
                    marks_clean.append((m.start(1), m.group(1), m.end()))
                    seen.add(m.group(1))
            marks_clean.sort()
        if marks_clean:
            marks_in_zone = marks_clean
            opt_zone = opt_zone_clean

        for idx, (ms, letter, me) in enumerate(marks_in_zone):
            next_ms = marks_in_zone[idx + 1][0] if idx + 1 < len(marks_in_zone) else len(opt_zone)
            body = opt_zone[me:next_ms].strip()
            if letter not in opts:
                opts[letter] = body
            elif not opts[letter]:
                opts[letter] = body
            # 同字母重复出现不追加（避免解析混入）

        # 无解析标记的书（如商经知）：结构是「选项 + 各类解读板块 + 综上，本题答案为X」
        # 真正的解析往往只有「综上」前那一小段，中间的 [题干信息解读]/[命题陷阱]
        # 等属于补充材料，不是每题解析。
        # 策略：D 选项取到「第一个板块标记」为止；解析取「综上...本题答案为X」附近
        if _need_jiexi_from_options and marks_in_zone:
            last_letter_idx = None
            for idx, (ms, letter, me) in enumerate(marks_in_zone):
                if letter == "D":
                    last_letter_idx = idx
            if last_letter_idx is not None:
                # 优先用被截掉的板块区（内含解析），其次用 D 之后的内容
                if block_tail:
                    tail_zone = block_tail
                else:
                    d_start = marks_in_zone[last_letter_idx][2]
                    tail_zone = opt_zone[d_start:]

                # 解析：优先取「综上...本题答案为X」这句话（含前一句结论）
                if tail_zone:
                    m_sum = re.search(r"综上[^。]{0,60}本题答案为\s*[A-D]+[^。]{0,10}[。]?", tail_zone)
                    if m_sum:
                        before = tail_zone[:m_sum.start()]
                        m_prev = re.search(r"[。]\s*([^。]{20,120})[。]\s*$", before + "。")
                        jiexi = (m_prev.group(1) + "。" if m_prev else "") + m_sum.group(0)
                        jiexi = jiexi.strip()
                    # 若没有「综上」句，说明该书解析极简，留空比塞错内容好
    else:
        stem_raw = head

    # 6. 补漏：若选项不是 A 开头，或中间跳过字母，尝试用「内容切分」修复
    #    典型场景：OCR 漏了 C.，导致 B 的内容里混入了 C 的题干
    #    这里做保守修复：按字母顺序补齐，识别明显的多选项拼接
    opts = repair_options(opts)

    # 6.5 选项长度均衡化：同题选项长度应大致相当
    #     若某选项远超其他选项，说明混入了解析（双栏错位的典型症状）
    if len(opts) >= 3:
        sent_opts = {k: sanitize_option(v, stem_raw) for k, v in opts.items()}
        lens = sorted(len(v) for v in sent_opts.values() if v)
        if len(lens) >= 3:
            median = lens[len(lens) // 2]
            for k in list(sent_opts.keys()):
                v = sent_opts[k]
                if not v:
                    continue
                # 判据：该选项超过中位数的 2.5 倍，且比第二长的选项长 40 字以上
                others = sorted((len(x) for kk, x in sent_opts.items()
                                 if kk != k and x), reverse=True)
                second = others[0] if others else 0
                if median > 0 and len(v) > median * 2.5 and len(v) - second >= 30:
                    cut_at = max(median * 2, second + 20, 40)
                    head = v[:cut_at]
                    last_dot = head.rfind("。")
                    sent_opts[k] = (head[:last_dot + 1] if last_dot > 15 else head).strip()
        opts = sent_opts

    # 7. 清理题干
    stem = stem_raw
    # 去水印/噪点
    stem = clean_watermark(stem)

    # 7.1 题干过短时的补救：选项 A 的内容里常混有题干尾部
    #     形态：题干被切在中间，剩余部分跑到 A 选项开头
    if len(stem) < 25 and opts.get("A"):
        a_val = opts["A"]
        # 在 A 内容里找「？（」或「？(」—— 题干通常以问号+出处结尾
        m_q = re.search(r"[？?]\s*[（(]", a_val)
        if m_q and m_q.start() > 10:
            stem = (stem + a_val[:m_q.end()]).strip()
            opts["A"] = a_val[m_q.end():].strip()
        else:
            # 找第一个句号，前半当题干补充
            m_dot = re.search(r"[。]", a_val)
            if m_dot and m_dot.start() > 10:
                stem = (stem + a_val[:m_dot.end()]).strip()
                opts["A"] = a_val[m_dot.end():].strip()
    # 去掉开头章节名
    stem = RE_CHAPTER_LEAD.sub("", stem).strip()
    # 去掉残留标记
    stem = re.sub(r"^[\[\]［］【】\s]*(?:考点|解析)[\[\]［］【】\s]*", "", stem).strip()
    # 题干混入解析：截断
    for kw in ("本题答案为", "综上所述", "故本题", "因此，本题"):
        idx = stem.find(kw)
        if idx > 20:
            stem = stem[:idx].strip()
            stem = re.sub(r"[，,。；;]$", "", stem).strip()
            if not stem.endswith(("？", "?", "。")):
                stem += "。"
            break
    # 题干末尾残留「X项，」
    m_tail = re.search(r"[。？?]\s*([A-D]项[，,])", stem)
    if m_tail and m_tail.start() > 20:
        stem = stem[:m_tail.start() + 1].strip()
    # 去掉题干末尾未闭合的出处括号残片
    stem = re.sub(r"[（(]\s*\d{4}[^）)]*$", "", stem).strip()

    if not stem or len(stem) < 8:
        return None

    # 8.5 丢弃「不是题目」的块
    #   特征：没有任何选项 + 题干里没有疑问句/「下列」
    #   这类块通常是上一题解析的跨页续文，被题号误切
    opt_keys = sorted(opts.keys())
    looks_like_question = bool(re.search(r"[？?]|下列|哪一|哪些|正确的是|错误的是|说法", stem))
    if not opt_keys and not looks_like_question:
        return None
    # 只有一个选项且题干无问句，也视为垃圾
    if len(opt_keys) == 1 and not looks_like_question:
        return None

    # 9. 答案提取（关键：必须锁定「本题」的解析范围）
    #   错误做法：解析区找不到就搜 full —— full 里混有上一题的
    #            「本题答案为X」，会张冠李戴（实测 100+ 题答案错误）
    #   正确做法：
    #     1) 只在本题解析区 jiexi 里找答案
    #     2) 取【最后一个】—— 本题答案为X 一定在本题解析的最末尾，
    #        若出现多个，说明前面混入了上一题残留，最后一个才属于本题
    #     3) 找到后用该位置截断解析，丢弃其后的串栏残留
    answer = ""
    ans_hits = [(mm.start(), mm.end(), mm.group(1)) for mm in RE_ANSWER.finditer(jiexi)]
    if ans_hits:
        # 取最后一个（本题答案在本题解析末尾）
        pos_s, pos_e, ans_val = ans_hits[-1]
        answer = ans_val
        # 解析保留到该答案为止（后面的内容属于下一题或其他残留）
        jiexi = jiexi[:pos_e].strip()
    else:
        # 退路：解析区无答案时，在选项区之后找（仍限定本题范围）
        if opt_zone_start >= 0:
            tail = full[opt_zone_start:]
            hits = [(m.start(), m.group(1)) for m in RE_ANSWER.finditer(tail)]
            if hits:
                answer = hits[-1][1]

    # 9.5 选项补齐：仅在切分点可靠时才执行
    #     判定标准：切分点必须是「句号 + 新主语」且前后长度均衡
    #     否则宁可保持原样（由 flags 标记），绝不造出错误选项
    if answer:
        opts = fill_missing_by_answer(opts, answer)
        keys = sorted(opts.keys())

    # 9. 题型：答案字母数反推（最可靠）
    qtype = ""
    if answer:
        n = len(answer)
        if n == 1:
            qtype = "单选"
            if src_tag in ("多", "任"):
                qtype = "多选" if src_tag == "多" else "不定项"
        else:
            qtype = "不定项" if src_tag == "任" else "多选"
    if not qtype:
        if src_tag == "多":
            qtype = "多选"
        elif src_tag == "任":
            qtype = "不定项"
        else:
            qtype = "单选"
        if re.search(r"哪些|多选|错误的有|正确的有|说法错误的是", stem):
            qtype = "多选"

    # 10. 质量标记
    scores = [i["score"] for i in items]
    min_score = min(scores) if scores else 0

    flags = []
    if min_score < 0.85:
        flags.append("低置信度")
    keys = sorted(opts.keys())
    if not (keys and keys[0] == "A" and "D" in keys and len(keys) == 4):
        flags.append("选项不完整")
    if not answer:
        flags.append("缺答案")
    if not jiexi:
        flags.append("缺解析")
    if len(stem) > 500:
        flags.append("题干过长")

    return {
        "id": f"{subject}-{block['no']}",
        "no": block["no"],
        "subject": subject,
        "author": author,
        "chapter": block.get("chapter", ""),
        "stem": stem,
        "options": [{"k": k, "v": clean_watermark(sanitize_option(opts[k], stem))}
                    for k in keys],
        "answer": answer,
        "qtype": qtype,
        "source": source,
        "kaodian": kaodian,
        "explain": clean_watermark(jiexi),
        "page": block.get("page"),
        "ocr_score": round(min_score, 2),
        "flags": flags,
        # 块首混入的「上一题答案」，供 parse_questions 回填上一题
        "_orphanAnswer": orphan_answer,
    }


def repair_options(opts, stem=""):
    """修复选项异常。

    场景 1：选项内容过长 → 可能混入了下一个选项，按句号切分
    场景 2：选项字母不全（OCR 漏掉 C. 之类）→ 尝试用内容边界切分补齐
    """
    if not opts:
        return opts

    fixed = dict(opts)

    # 场景 1：过长选项按句号边界切分（保守，只切一次）
    for k in list(fixed.keys()):
        v = fixed[k].strip()
        if len(v) <= 130:
            continue
        m = re.search(r"[。]\s*(?=(?:甲|乙|丙|丁|戊|某|该|根据|按照|依据|如果|若)[^。]{10,})", v)
        if m and m.start() > 40:
            fixed[k] = v[:m.start() + 1].strip()

    # 场景 2：字母缺失时暂不强行补齐（无法可靠判断归属），
    #        由 flags 标记出来，前端提示用户对照原书
    return fixed



def fill_missing_by_answer(opts, answer):
    """当答案引用了缺失的选项字母时，尝试从已有选项里切出来。

    严格条件（缺一不可，否则放弃——宁可保留问题也不造错误数据）：
      1. 缺失字母在答案中
      2. 前一个选项内容足够长（>=100 字）
      3. 切分点必须是「。+ 空白 + 新主语」
      4. 切开后前段 >=50 字，后段 >=40 字
      5. 后段长度不超过前段的 1.2 倍
    """
    if not opts or not answer:
        return opts

    keys = set(opts.keys())
    missing = [c for c in "ABCD" if c not in keys and c in answer]
    if not missing:
        return opts

    fixed = dict(opts)

    for miss in missing:
        prev = None
        for c in "ABCD":
            if c == miss:
                break
            if c in fixed:
                prev = c
        if not prev:
            continue

        v = fixed[prev].strip()
        if len(v) < 100:
            continue

        # 只在「句号 + 新主语开头」处切
        best = None
        for m in re.finditer(r"[。]\s*(?=(?:甲|乙|丙|丁|戊|某|该|根据|按照|依据|如果|若|二人|三人))", v):
            pos = m.end()
            head_len, tail_len = pos, len(v) - pos
            if head_len >= 50 and tail_len >= 40 and tail_len <= head_len * 1.2:
                best = pos
        if best is None:
            continue

        fixed[prev] = v[:best].strip()
        fixed[miss] = v[best:].strip()

    return fixed



def main():
    ap = argparse.ArgumentParser(description="法考真金题 结构化解析")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--author", default="")
    ap.add_argument("--min-answer-rate", type=float, default=0,
                    help="答案覆盖率低于此值则报警")
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print(f"x 输入不存在: {args.inp}")
        sys.exit(1)

    print("=" * 58)
    print(f"解析: {args.inp}")
    print(f"科目: {args.subject}")
    print("=" * 58)

    pages = load_pages(args.inp)
    print(f"读入 {len(pages)} 页")

    questions, n_blocks = parse_questions(pages, args.subject, args.author)
    print(f"切分出 {n_blocks} 个题目块 → 去重后 {len(questions)} 题")

    # 统计
    with_answer = sum(1 for q in questions if q["answer"])
    with_explain = sum(1 for q in questions if q["explain"])
    complete_opts = sum(1 for q in questions if len(q["options"]) == 4)
    multi = sum(1 for q in questions if q["qtype"] == "多选")

    print(f"\n答案完整: {with_answer}/{len(questions)} ({with_answer/max(len(questions),1)*100:.0f}%)")
    print(f"解析完整: {with_explain}/{len(questions)} ({with_explain/max(len(questions),1)*100:.0f}%)")
    print(f"四选项齐全: {complete_opts}/{len(questions)}")
    print(f"多选题: {multi}")

    # 答案覆盖率报警
    rate = with_answer / max(len(questions), 1)
    if args.min_answer_rate and rate < args.min_answer_rate:
        print(f"\n[警告] 答案覆盖率 {rate*100:.0f}% 低于阈值 {args.min_answer_rate*100:.0f}%")

    # 章节分布
    chapters = {}
    for q in questions:
        ch = q["chapter"] or "(未识别)"
        chapters[ch] = chapters.get(ch, 0) + 1
    print("\n章节分布:")
    for ch, n in sorted(chapters.items()):
        print(f"  {ch}: {n} 题")

    # 写文件
    payload = {
        "subject": args.subject,
        "author": args.author,
        "total": len(questions),
        "stats": {
            "withAnswer": with_answer,
            "withExplain": with_explain,
            "completeOptions": complete_opts,
            "multiChoice": multi,
        },
        "questions": questions,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    size = os.path.getsize(args.out) / 1024
    print(f"\n[DONE] -> {args.out} ({size:.0f} KB)")

    # 样例
    print("\n" + "=" * 58)
    print("前 2 题样例:")
    for q in questions[:2]:
        print(f"\n--- {q['id']} [{q['qtype']}] 第{q['page']}页 ---")
        print(f"  题干: {q['stem'][:80]}")
        print(f"  选项: " + " | ".join(f"{o['k']}.{o['v'][:20]}" for o in q["options"]))
        print(f"  答案: {q['answer']}")
        print(f"  考点: {q['kaodian'][:50]}")
        print(f"  出处: {q['source']}")
        print(f"  标记: {q['flags']}")


if __name__ == "__main__":
    main()

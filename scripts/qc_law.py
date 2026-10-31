#!/usr/bin/env python3
"""法律题库自动化质检器 —— 多级检查，任一硬性检查失败即报错

设计目标：把之前踩过的坑全部固化成自动检查，
避免同样的错误再次发生，也避免引入新错误。

三级检查：
  L1 硬性阻断（fail-fast）：数据不可用，必须修复才能入库
  L2 质量警告：数据可用但有瑕疵，需统计比例
  L3 一致性检查：跨字段一致性

用法：
  python scripts/qc_law.py --data ../law_ocr/law_xingfa.json --subject 刑法
  python scripts/qc_law.py --data a.json b.json --subject 刑法 --strict
"""

import sys, io, os, re, json, argparse
from collections import Counter, defaultdict

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


class QC:
    def __init__(self, name):
        self.name = name
        self.fatal = []      # L1 硬性错误
        self.warn = []       # L2 质量问题
        self.info = []       # L3 信息

    def fail(self, qid, msg):
        self.fatal.append((qid, msg))

    def warning(self, qid, msg):
        self.warn.append((qid, msg))

    def note(self, msg):
        self.info.append(msg)

    def report(self):
        print("=" * 66)
        print(f"质检：{self.name}")
        print("=" * 66)

        ok = True
        if self.fatal:
            ok = False
            print(f"\n[L1 硬性错误] {len(self.fatal)} 处 —— 必须修复")
            grouped = defaultdict(list)
            for qid, msg in self.fatal:
                grouped[msg].append(qid)
            for msg, ids in sorted(grouped.items(), key=lambda x: -len(x[1])):
                print(f"  {len(ids):>4}  {msg}")
                print(f"        例: {', '.join(ids[:3])}")
        else:
            print("\n[L1 硬性错误] 0 ✓")

        if self.warn:
            print(f"\n[L2 质量警告] {len(self.warn)} 处")
            grouped = defaultdict(list)
            for qid, msg in self.warn:
                grouped[msg].append(qid)
            for msg, ids in sorted(grouped.items(), key=lambda x: -len(x[1])):
                print(f"  {len(ids):>4}  {msg}")
        else:
            print("\n[L2 质量警告] 0 ✓")

        if self.info:
            print("\n[L3 统计]")
            for m in self.info:
                print(f"  {m}")

        return ok


def load(data_paths):
    all_q = []
    for p in data_paths:
        if not os.path.exists(p):
            print(f"x 文件不存在: {p}")
            continue
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d = d.get("questions", [])
        all_q.extend(d)
    return all_q


def check(qs, subject, pdf_pages=None):
    qc = QC(f"{subject}（{len(qs)} 题）")

    if not qs:
        qc.fail("ALL", "题库为空")
        return qc

    # ══════════════ L1 硬性检查 ══════════════

    # 0. 页码单调性：题号与页码应同步递增（防止串题）
    prev_no = prev_page = None
    disorder = 0
    for q in sorted(qs, key=lambda x: (x.get("page") or 0, int(x.get("no") or 0))):
        no, pg = int(q.get("no") or 0), q.get("page")
        if prev_no is not None and pg == prev_page and no < prev_no:
            disorder += 1
        prev_no, prev_page = no, pg
    if disorder > len(qs) * 0.02:
        qc.fail("ALL", f"题号顺序异常 {disorder} 处（可能串题）")

    stems = {}
    for q in qs:
        qid = q.get("id") or q.get("no") or "?"

        # 1. 必填字段
        for field in ("id", "stem", "options", "answer"):
            if not q.get(field):
                qc.fail(qid, f"缺字段 {field}")

        stem = (q.get("stem") or "").strip()
        opts = q.get("options") or []
        keys = q.get("optionKeys") or []
        ans = (q.get("answer") or "").strip()

        # 2. 选项必须是 4 个（且 A-D 齐全）
        if len(opts) != 4:
            qc.fail(qid, f"选项数≠4（实际 {len(opts)}）")
        if keys and sorted(keys) != ["A", "B", "C", "D"]:
            qc.fail(qid, f"选项字母异常 {keys}")
        if any(not v or len(str(v).strip()) < 5 for v in opts):
            qc.fail(qid, "选项内容为空或过短")

        # 3. 答案有效性
        if not ans:
            qc.fail(qid, "缺答案")
        else:
            if not re.fullmatch(r"[A-D]{1,4}", ans):
                qc.fail(qid, f"答案格式异常 {ans}")
            elif sorted(ans) != list(dict.fromkeys(sorted(ans))):
                qc.fail(qid, f"答案有重复字母 {ans}")
            elif keys and any(c not in keys for c in ans):
                qc.fail(qid, f"答案字母不在选项中 {ans}")
            if len(set(ans)) != len(ans):
                qc.fail(qid, f"答案字母重复 {ans}")

        # 4. 题干不得含标记/解析
        if re.search(r"\[解析|\[考点|本题答案为|综上所述", stem):
            qc.fail(qid, "题干含解析标记")
        if re.search(r"^第[一二三四五六七八九十\d]+[讲章编]", stem):
            qc.fail(qid, "题干开头是章节名")
        if len(stem) < 15:
            qc.fail(qid, f"题干过短（{len(stem)}字）")

        # 5. 题干不得与选项内容「完全等同」（说明切分错位）
        #    注意：法考常见的「选项复述题干片段」是正常出题手法
        #    （如题干说「夏某持有0.8%股权」，A选项说「夏某持有0.8%股权，无权查阅」），
        #    只有「选项 == 题干」或「题干是选项的子串」才判错。
        if len(stem) > 20 and len(stem) < 200:
            for v in opts:
                vs = str(v).strip()
                if len(vs) > 20 and (vs == stem or stem in vs):
                    qc.fail(qid, "题干是某选项的子串（切分错位）")
                    break

        # 6. 重复题干 → 若选项也相同才是切分错误；否则是「一案多问」，合法
        key = re.sub(r"\s+", "", stem)[:40]
        opt_sig = "|".join(re.sub(r"\s+", "", str(v))[:20] for v in opts)
        if key in stems:
            prev_id, prev_sig = stems[key]
            if prev_sig == opt_sig:
                qc.fail(qid, f"题干与选项均与 {prev_id} 相同（重复题）")
            else:
                qc.warning(qid, f"题干与 {prev_id} 相同但选项不同（一案多问）")
        else:
            stems[key] = (qid, opt_sig)

        # 7. 选项不得重复（但 OCR 截断导致的前缀相同不算）
        vals = [re.sub(r"\s+", "", str(v)) for v in opts]
        if len(set(vals)) < len(vals):
            dup = [v for v, c in Counter(vals).items() if c > 1]
            # 只当重复项内容「完整且较长」时才判错；
            # 若都以不完整片段结尾（如「向H」），说明是 OCR 截断，属于 L2 警告
            full_dup = [v for v in dup if len(v) > 20 and v[-1] in "。！？；）"]
            if full_dup:
                qc.fail(qid, "存在完全相同的选项")
            else:
                qc.warning(qid, "选项内容相似（可能 OCR 截断）")

        # 7.5 选项污染（解析/图示混入选项）—— 硬性错误
        #     这是实际发生过的最严重问题，必须挡住
        POLLUTE = [
            (r"综上", "含「综上」"),
            (r"本题的?正确答案|本题答案为", "含答案标记"),
            (r"[\[［【]?\s*(?:民事|刑事)?法律关系示意图", "含示意图"),
            (r"[\[［【]?\s*(?:有体系|知识体系|思维导图)", "含体系图"),
            (r"[\[［【]?\s*(?:解题思路|分析与思路|题支逐项|题干信息|命题陷阱)", "含解析标记"),
            (r"考点\s*\d+\s*[：:]", "含考点标记"),
            (r"PROJECT\s*\d+", "含 PROJECT 水印"),
            (r"专题[一二三四五六七八九十百零\d]+", "含章节名"),
        ]
        polluted = False
        for v in opts:
            vs = str(v)
            for pat, label in POLLUTE:
                if re.search(pat, vs):
                    qc.fail(qid, f"选项污染（{label}）")
                    polluted = True
                    break
            if polluted:
                break
            # 逐项分析特征
            if len(vs) > 120 and re.search(r"(?:故)?[A-D]项(?:说法)?(?:正确|错误)", vs):
                qc.fail(qid, "选项污染（含逐项分析）")
                polluted = True
                break

        # 7.6 选项长度异常
        if not polluted:
            for v in opts:
                vs = str(v)
                if len(vs) > 260:
                    qc.fail(qid, f"选项过长（{len(vs)}字，疑似解析混入）")
                    break
                if 0 < len(vs.strip()) < 4:
                    qc.fail(qid, "选项过短")
                    break

        # ══════════════ L2 质量警告 ══════════════

        # 8. 水印/噪点（注意：「微信」「公众号」可能是案情内容，需看上下文）
        joined = stem + "".join(str(v) for v in opts)
        # 明确的扫描水印
        for pat in ("网盘", "金盾招警", "PROJECT", "加微信领", "扫码关注", "仅供学习"):
            if pat in joined:
                qc.warning(qid, f"含水印「{pat}」")
                break
        # 「微信」只在不像案情时才算水印（如"微信号""微信搜索"）
        if re.search(r"微信号|微信搜索|微信关注|微信扫码", joined):
            qc.warning(qid, "含水印「微信」")

        # 9. 题干过长（>300字，多半吞了材料）
        if len(stem) > 300:
            qc.warning(qid, f"题干过长（{len(stem)}字）")

        # 10. 题干无问句
        if not re.search(r"[？?]|下列|哪一|哪些|正确|错误|说法", stem):
            qc.warning(qid, "题干无问句特征")

        # 11. 缺解析
        #     注意：商经知等书的解析本身就极简（只有「综上，本题答案为X」），
        #     这属于原书体例，不算缺陷。区分「完全没有」与「极简」。
        exp = (q.get("explain") or "").strip()
        if len(exp) == 0:
            qc.warning(qid, "缺解析")
        elif len(exp) < 15 and "本题答案为" not in exp:
            qc.warning(qid, "解析过短")

        # 12. 考点异常
        kd = (q.get("kaodian") or "").strip()
        if len(kd) > 40:
            qc.warning(qid, f"考点过长（{len(kd)}字）")

        # 13. 章节缺失
        if not (q.get("chapter") or "").strip():
            qc.warning(qid, "无章节")

        # 14. 页码合理性
        page = q.get("page")
        if page is not None:
            if not isinstance(page, int) or page < 1:
                qc.warning(qid, f"页码异常 {page}")
            elif pdf_pages and page > pdf_pages:
                qc.warning(qid, f"页码超出范围 {page}>{pdf_pages}")

        # 15. 题型与答案一致性
        qt = q.get("qtype") or ""
        if qt == "单选" and len(ans) > 1:
            qc.warning(qid, f"单选但答案 {ans}")

    # ══════════════ L3 统计信息 ══════════════

    # 图片覆盖检查：有 flags 的题必须有对应原书图片
    img_code = {"刑法": "xf", "民法": "mf", "民诉法": "msf", "刑诉法": "xsf",
                "行政法": "xzf", "商经知": "sxz", "三国法": "sgf", "理论法": "lilun"}
    code = img_code.get(subject)
    if code:
        imgdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "site", "data", "zt", "law_img")
        flagged = [q for q in qs if q.get("flags")]
        missing = []
        for q in flagged:
            page = q.get("page")
            if not page:
                continue
            base = os.path.join(imgdir, f"{code}-{page:04d}")
            # 支持 webp 与 jpg 两种格式
            if not (os.path.exists(base + ".webp") or os.path.exists(base + ".jpg")):
                missing.append(q.get("id") or "?")
        if missing:
            # 图片缺失是 L2 警告（不影响答题，但影响对照功能）
            for qid in missing[:50]:
                qc.warning(qid, "原书图片缺失")
            qc.note(f"⚠ 有 {len(missing)} 题的原书图片未生成")
        else:
            qc.note(f"原书图片: {len(flagged)} 题有疑点，全部有图片 ✓")

    qc.note(f"题型分布: {dict(Counter(q.get('qtype','?') for q in qs))}")
    qc.note(f"答案长度分布: {dict(Counter(len(q.get('answer') or '') for q in qs))}")
    qc.note(f"选项数分布: {dict(Counter(len(q.get('options') or []) for q in qs))}")
    # 解析体例统计（区分「极简解析」与「完整解析」）
    exp_lens = [len((q.get("explain") or "").strip()) for q in qs]
    brief = sum(1 for x in exp_lens if 0 < x < 30)
    empty = sum(1 for x in exp_lens if x == 0)
    rich = sum(1 for x in exp_lens if x >= 30)
    qc.note(f"解析体例: 完整 {rich} 题 / 极简 {brief} 题 / 空缺 {empty} 题")
    chapters = Counter((q.get("chapter") or "(无)") for q in qs)
    qc.note(f"章节数: {len(chapters)}，最大章节: {chapters.most_common(3)}")
    years = Counter(str(q.get("year") or "?") for q in qs)
    qc.note(f"年份数: {len(years)}，范围: {min(years)}-{max(years)}")
    lens = sorted(len((q.get("stem") or "")) for q in qs)
    qc.note(f"题干长度: 最短 {lens[0]}，中位 {lens[len(lens)//2]}，最长 {lens[-1]}")
    kds = sorted(len((q.get("kaodian") or "")) for q in qs)
    qc.note(f"考点长度: 最短 {kds[0]}，中位 {kds[len(kds)//2]}，最长 {kds[-1]}")
    pages = [q.get("page") for q in qs if isinstance(q.get("page"), int)]
    if pages:
        qc.note(f"页码范围: {min(pages)} - {max(pages)}")

    return qc


def main():
    ap = argparse.ArgumentParser(description="法律题库自动化质检")
    ap.add_argument("--data", nargs="+", required=True, help="题库 JSON 文件")
    ap.add_argument("--subject", default="法律", help="科目名")
    ap.add_argument("--pdf-pages", type=int, default=None, help="PDF 总页数（校验页码上限）")
    ap.add_argument("--strict", action="store_true", help="有 L2 警告也视为失败")
    ap.add_argument("--max-warn-ratio", type=float, default=0.10,
                    help="L2 警告占比上限（默认 10%%）")
    args = ap.parse_args()

    qs = load(args.data)
    qc = check(qs, args.subject, args.pdf_pages)
    ok = qc.report()

    n_warn = len(qc.warn)
    ratio = n_warn / max(len(qs), 1)

    print("\n" + "=" * 66)
    if args.strict and n_warn > 0:
        ok = False
    elif ratio > args.max_warn_ratio:
        ok = False

    if ok:
        print(f"✅ 通过（{len(qs)} 题，警告 {n_warn} 处，占比 {ratio*100:.1f}%）")
    else:
        print(f"❌ 未通过（{len(qs)} 题，硬性错误 {len(qc.fatal)} 处，警告 {n_warn} 处）")
    print("=" * 66)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

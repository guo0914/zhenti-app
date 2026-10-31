#!/usr/bin/env python3
"""从题库挖掘国省考常考成语与实词，生成 site/data/cidian.js

数据来源：site/data/zt/verbal.json（807 道言语理解真题）

挖掘内容：
  1. 逻辑填空题的 options 中的四字成语、两字/三字实词
  2. 每道题关联：题干原文、正确答案、官方解析（含逐项辨析）
  3. 从解析中反查该词的释义与辨析

用法：
  python scripts/extract_cidian.py
  python scripts/extract_cidian.py --min-freq 1
"""

import json, os, re, sys, io
from collections import Counter, defaultdict
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERBAL = os.path.join(BASE, "site", "data", "zt", "verbal.json")
OUTPUT = os.path.join(BASE, "site", "data", "cidian-mined.js")

# ── 常见虚词/非词条黑名单 ──
STOP = {
    "重要意义", "实践路径", "重要作用", "主要因素", "基本情况", "发展趋势",
    "重要内容", "关键因素", "核心内容", "基本要求", "实现路径", "具体措施",
    "有效措施", "重要举措", "突出表现", "显著特征", "主要特点", "根本原因",
}

# 词的难度分层（按考频常用度粗分，用于展示）
LEVEL1 = set("""一鸣惊人 一蹴而就 一鼓作气 一丝不苟 一如既往 一视同仁 一举两得
一劳永逸 一蹴而就 不言而喻 不谋而合 不期而遇 不遗余力 不可或缺 不胫而走
不攻自破 不负众望 不落窠臼 别具一格 耳目一新 焕然一新 万象更新 翻天覆地
潜移默化 耳濡目染 日新月异 突飞猛进 一日千里 与日俱增 层出不穷 比比皆是
屡见不鲜 司空见惯 习以为常 淡然处之 处心积虑 千方百计 想方设法 无所不用其极""".split())

LEVEL2 = set("""相形见绌 黯然失色 自惭形秽 望尘莫及 屈指可数 寥寥无几 凤毛麟角
九牛一毛 微不足道 无足轻重 举足轻重 首屈一指 独占鳌头 一枝独秀 独树一帜
标新立异 别出心裁 匠心独运 巧夺天工 鬼斧神工 卓尔不群 出类拔萃 鹤立鸡群
卓有成效 行之有效 立竿见影 潜移默化 水滴石穿 持之以恒 锲而不舍 孜孜不倦""".split())

LEVEL3 = set("""缘木求鱼 南辕北辙 抱薪救火 火上浇油 饮鸩止渴 急功近利 揠苗助长
掩耳盗铃 削足适履 刻舟求剑 胶柱鼓瑟 生搬硬套 照猫画虎 依样画葫芦 邯郸学步
东施效颦 囫囵吞枣 生吞活剥 断章取义 望文生义 穿凿附会 牵强附会 生造硬凑""".split())

# ── 非成语的四字短语后缀黑名单 ──
# "使用现状""政治困境" 这类是名词性短语，不是成语
PHRASE_SUFFIX = (
    "现状", "困境", "优势", "方式", "习性", "环境", "特征", "前景",
    "价值", "危害", "原理", "时间", "作用", "意义", "路径", "措施",
    "因素", "内容", "要求", "特点", "原因", "问题", "现象", "趋势",
    "功能", "结构", "体系", "机制", "模式", "过程", "关系", "影响",
    "水平", "能力", "程度", "范围", "规模", "速度", "效率", "质量",
    "成本", "收益", "风险", "需求", "供给", "市场", "政策", "制度",
)

# 非词专名黑名单（人名/器物/发髻等）
PROPER_NOUN_HINT = ("髻", "楼", "阁", "亭", "桥", "山", "河", "湖", "江")

# 明确排除的非成语条目（人工校准）
EXTRA_BLACKLIST = {
    "传承途径", "天气预报", "视觉美感", "造字依据", "换而言之",
    "点茶", "熁盏", "碎茶", "罗茶", "垂挂髻", "十字髻", "堕马髻", "飞仙髻",
    "播音员", "非遗传承人", "美发师", "幼儿保育员",
    "预警机", "试金石", "缓冲器", "安全阀",
}


def detect_level(word):
    if word in LEVEL1:
        return 1
    if word in LEVEL2:
        return 2
    if word in LEVEL3:
        return 3
    return 0


def is_idiom(w):
    """四字成语判定：纯汉字四字、非停用词、非名词性短语"""
    if not re.fullmatch(r"[\u4e00-\u9fff]{4}", w):
        return False
    if w in STOP or w in EXTRA_BLACKLIST:
        return False
    if w.endswith(PHRASE_SUFFIX):
        return False
    return True


def is_word(w):
    """实词判定：2-3 字纯汉字，排除专名与名词性短语"""
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,3}", w):
        return False
    if w in STOP or w in EXTRA_BLACKLIST:
        return False
    if w.endswith(PHRASE_SUFFIX):
        return False
    if any(w.endswith(h) for h in PROPER_NOUN_HINT) and len(w) >= 3:
        return False
    if len(w) == 3 and w[-1] in "员师家器阀":
        return False
    return True


def extract_def(explain, word):
    """从解析中提取该词的释义片段。

    解析里常见格式：B项"相形见绌"意为和同类的事物相比较显得不足，符合文意
    或：A项"黯然失色"比喻相比之下有很大差距
    """
    if not explain:
        return "", ""

    pat = r'[项\"]' + re.escape(word) + r'[\"”]?\s*(?:一词|的意思|意为|意思是|比喻|形容|指|表示)?\s*([^，。；]{2,60})'
    m = re.search(pat, explain)
    if m:
        return m.group(1).strip(" ，。；"), explain

    # 尝试 "word" 后紧跟动词
    idx = explain.find(word)
    if idx >= 0:
        tail = explain[idx + len(word):idx + len(word) + 80]
        tail = re.sub(r'^[\"”]?(?:一词|的意思|意为|意思是|比喻|形容|指|表示)[，:]?', '', tail)
        tail = tail.split("，")[0].split("。")[0].strip()
        if 2 <= len(tail) <= 60:
            return tail, explain
    return "", explain


def detect_judgment(explain, word):
    """判断感情色彩/用法倾向：正确项 vs 干扰项"""
    if not explain:
        return ""
    # 在解析中定位该词附近是否有"符合文意""当选"
    idx = explain.find(word)
    if idx < 0:
        return ""
    seg = explain[max(0, idx - 60): idx + 120]
    if "符合文意" in seg or "当选" in seg:
        return "correct"
    if "排除" in seg or "不符" in seg or "不当" in seg:
        return "wrong"
    return ""


def main():
    import argparse
    ap = argparse.ArgumentParser(description="挖掘真题中的成语与实词")
    ap.add_argument("--min-freq", type=int, default=1, help="最低出现次数")
    args = ap.parse_args()

    if not os.path.exists(VERBAL):
        print(f"x 找不到 {VERBAL}")
        sys.exit(1)

    qs = json.load(open(VERBAL, encoding="utf-8"))
    print(f"读入 {len(qs)} 道言语题")

    idioms = {}      # word -> entry
    words = {}       # word -> entry
    ctx_count = 0

    for q in qs:
        sub = q.get("sub", "")
        opts = q.get("options") or []
        keys = q.get("optionKeys") or [chr(65 + i) for i in range(len(opts))]
        ans = (q.get("answer") or "").strip()
        explain = q.get("explain") or ""
        stem = q.get("stem") or ""

        # 只处理含成语/实词选项的填空类题
        cand = []
        for i, o in enumerate(opts):
            o = str(o).strip()
            if is_idiom(o):
                cand.append((o, keys[i] if i < len(keys) else "", "idiom"))
            elif is_word(o):
                cand.append((o, keys[i] if i < len(keys) else "", "word"))

        if not cand:
            continue

        ctx_count += 1
        for word, key, kind in cand:
            store = idioms if kind == "idiom" else words
            e = store.setdefault(word, {
                "word": word,
                "kind": kind,
                "level": detect_level(word),
                "def": "",
                "contexts": [],
                "count": 0,
                "isAnswer": 0,
            })
            e["count"] += 1
            if key and key == ans:
                e["isAnswer"] += 1

            # 提取释义
            if not e["def"]:
                d, _ = extract_def(explain, word)
                if d:
                    e["def"] = d

            # 记录真题语境（每题每题最多保留 2 条，避免文件过大）
            if len(e["contexts"]) < 3:
                e["contexts"].append({
                    "stem": re.sub(r"\s+", " ", stem).strip()[:400],
                    "options": [str(x) for x in opts],
                    "answer": ans,
                    "isAnswer": (key == ans),
                    "explain": re.sub(r"\s+", " ", explain).strip()[:500],
                    "paper": q.get("paper", "")[:60],
                    "year": q.get("year", ""),
                    "region": q.get("region", ""),
                })

    # 按考频排序
    def sort_key(e):
        return (-e["isAnswer"], -e["count"], e["word"])

    idiom_list = sorted([e for e in idioms.values() if e["count"] >= args.min_freq], key=sort_key)
    word_list = sorted([e for e in words.values() if e["count"] >= args.min_freq], key=sort_key)

    print(f"挖掘到成语 {len(idiom_list)} 个、实词 {len(word_list)} 组")
    print(f"有真题语境 {ctx_count} 题")

    # 统计有释义的比例
    with_def_i = sum(1 for e in idiom_list if e["def"])
    with_def_w = sum(1 for e in word_list if e["def"])
    print(f"  含释义：成语 {with_def_i}/{len(idiom_list)}，实词 {with_def_w}/{len(word_list)}")

    payload = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "行测真题言语理解（807 题）",
        "idioms": idiom_list,
        "words": word_list,
        "stats": {
            "idioms": len(idiom_list),
            "words": len(word_list),
            "contexts": ctx_count,
            "withDef": with_def_i + with_def_w,
        },
    }

    js = f"""/* ===== 真题词库（自动挖掘）=====
 * 由 scripts/extract_cidian.py 生成 — {payload['updated']}
 * 来源：{payload['source']}
 * 成语 {len(idiom_list)} 个 · 实词 {len(word_list)} 组 · 真题语境 {ctx_count} 题
 */

window.__CIDIAN_MINED__ = """
    js += json.dumps(payload, ensure_ascii=False, indent=1, separators=(",", ":"))
    js += ";\n"

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(js)

    size = os.path.getsize(OUTPUT) / 1024
    print(f"\n[DONE] -> {OUTPUT} ({size:.1f} KB)")


if __name__ == "__main__":
    main()

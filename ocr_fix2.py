"""
用 PaddleOCR 修复题库识别错误（精确裁剪方案）。

核心洞察（实测验证）：
  - PaddleOCR 直接识别干净的小区域，准确率接近 100%
    （例：A.1个 / B.2个 / C.3个 / D.4个 全部正确，置信度 0.84~0.94）
  - 整页检测切分是瓶颈：行合并、边界偏移会导致识别崩坏
  - 所以：不依赖自动检测，改用题目已有的 (pg, y, y2) 坐标 + 选项行等距规律精确裁剪

关键前提：
  - 模型必须放纯 ASCII 路径（C:\\paddle_models），Paddle C++ 层不认中文路径
  - 用 Paddle Inference API 直接加载（paddleocr 3.x 封装有兼容问题）

用法：
    python ocr_fix2.py --sample 5      # 抽样 5 道做质量验证
    python ocr_fix2.py                 # 全量处理
    python ocr_fix2.py --dry-run       # 不写回
"""

from __future__ import annotations

import json
import os
import re
import sys
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("GLOG_minloglevel", "3")

import numpy as np
from PIL import Image

APP = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.path.join(APP, "..", ".pdfwork"))
PAGES = os.path.join(WORK, "pages")
BANK = os.path.join(APP, "site", "data", "bank.json")

MODELS = r"C:\paddle_models"
DET = os.path.join(MODELS, "ch_PP-OCRv4_det_infer")
REC = os.path.join(MODELS, "ch_PP-OCRv4_rec_infer")
DICT = os.path.join(MODELS, "ppocr_keys_v1.txt")


# ---------------------------------------------------------------- 预测器

def make_rec():
    from paddle.inference import Config, create_predictor
    cfg = Config(os.path.join(REC, "inference.pdmodel"),
                 os.path.join(REC, "inference.pdiparams"))
    cfg.disable_gpu()
    cfg.disable_mkldnn()
    cfg.set_cpu_math_library_num_threads(4)
    return create_predictor(cfg)


def load_charset() -> list[str]:
    chars = ["blank"]
    with open(DICT, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                chars.append(line)
    chars.append(" ")
    return chars


def rec(predictor, img: np.ndarray, charset: list[str]) -> tuple[str, float]:
    """识别单行图像。"""
    h, w = img.shape[:2]
    if h < 4 or w < 4:
        return "", 0.0
    ch = 48
    cw = max(1, min(640, int(round(w * ch / h))))
    pil = Image.fromarray(img).convert("RGB").resize((cw, ch), Image.LANCZOS)
    x = np.array(pil).astype(np.float32) / 255.0
    x = (x - 0.5) / 0.5
    x = np.array([x.transpose(2, 0, 1)], dtype=np.float32)

    inp = predictor.get_input_handle(predictor.get_input_names()[0])
    inp.copy_from_cpu(x)
    predictor.run()
    out = np.array(
        predictor.get_output_handle(predictor.get_output_names()[0]).copy_to_cpu()
    )[0]

    idx = out.argmax(axis=-1)
    score = out.max(axis=-1)
    text, confs = [], []
    prev = -1
    for i, k in enumerate(idx):
        if k != prev and k != 0 and k < len(charset):
            text.append(charset[k])
            confs.append(float(score[i]))
        prev = k
    return "".join(text), (sum(confs) / len(confs) if confs else 0.0)


# ---------------------------------------------------------------- 版面分析

def crop_line(img: np.ndarray, y0: int, y1: int, x0: int = 0, x1: int | None = None):
    h, w = img.shape[:2]
    x1 = w if x1 is None else x1
    y0 = max(0, min(y0, h - 1))
    y1 = max(y0 + 1, min(y1, h))
    x0 = max(0, min(x0, w - 1))
    x1 = max(x0 + 1, min(x1, w))
    return img[y0:y1, x0:x1]


def tight_crop(a: np.ndarray, pad: int = 4) -> np.ndarray:
    """紧贴文字裁剪：去掉四周空白。实测能把识别置信度从 0.6 提升到 1.0。"""
    if a.size == 0:
        return a
    g = np.array(Image.fromarray(a).convert("L"))
    m = g < 170
    if not m.any():
        return a
    ys, xs = np.where(m)
    y0 = max(0, ys.min() - pad)
    y1 = min(a.shape[0], ys.max() + pad + 1)
    x0 = max(0, xs.min() - pad)
    x1 = min(a.shape[1], xs.max() + pad + 1)
    return a[y0:y1, x0:x1]


def find_text_rows(img: np.ndarray, y_from: int, y_to: int,
                   x_from: int = 240, x_to: int = 1900,
                   min_h: int = 25) -> list[tuple[int, int]]:
    """在指定区域内按水平投影找出文本行带。"""
    y_to = min(y_to, img.shape[0])
    y_from = max(0, y_from)
    if y_to <= y_from:
        return []
    band = img[y_from:y_to, x_from:min(x_to, img.shape[1])]
    gray = np.array(Image.fromarray(band).convert("L"))
    # 二值化：文字是深色
    mask = gray < 165
    row_has = mask.sum(axis=1) > 2

    rows = []
    start = None
    for i, v in enumerate(row_has):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_h:
                rows.append((y_from + start, y_from + i))
            start = None
    if start is not None and len(row_has) - start >= min_h:
        rows.append((y_from + start, y_from + len(row_has)))
    return rows


def split_option_rows(rows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """从行带里挑出选项行：高度相近、间距均匀的 4 行。"""
    if len(rows) < 4:
        return []
    # 从后往前找连续 4 行且高度接近的
    for i in range(len(rows) - 4, -1, -1):
        grp = rows[i:i + 4]
        hs = [b - a for a, b in grp]
        if max(hs) - min(hs) <= max(12, min(hs) * 0.5):
            gaps = [grp[j + 1][0] - grp[j][0] for j in range(3)]
            if max(gaps) - min(gaps) <= max(20, min(gaps) * 0.35):
                return grp
    return rows[-4:] if len(rows) >= 4 else []


# ---------------------------------------------------------------- 主流程

def process(bank: dict, predictor, charset, sample: int | None, dry: bool) -> None:
    qs = bank["questions"]
    targets = [q for q in qs
               if q.get("risky") or not all(o.strip() for o in q["options"])]
    # 优先处理选项为空的
    targets.sort(key=lambda q: (all(o.strip() for o in q["options"]), q.get("pg") or 0))
    if sample:
        targets = targets[:sample]

    print(f"处理 {len(targets)} 道题\n")
    cache: dict[int, np.ndarray] = {}
    fixed_opt = 0
    fixed_stem = 0

    for n, q in enumerate(targets, 1):
        pg, y, y2 = q.get("pg"), q.get("y"), q.get("y2")
        if not pg or not y:
            continue
        fp = os.path.join(PAGES, f"p{pg:03d}.png")
        if not os.path.exists(fp):
            continue
        if pg not in cache:
            cache[pg] = np.array(Image.open(fp).convert("RGB"))
        img = cache[pg]

        stem_txt = q["stem"]
        new_opts = list(q["options"])

        # 1) 版面事实：本书排版是「题干在前、选项紧随其后」，
        #    而 bank 里的 y 指向题干行。所以选项在 (y, y2) 区间内。
        #    y2 不可靠时，取下一个题干位置作为上界。
        y_end = y2 if y2 and y2 > y + 120 else y + 420
        rows = find_text_rows(img, y + 40, y_end - 5)
        opt_rows = split_option_rows(rows)

        print(f"[{n}/{len(targets)}] {q['id']} pg={pg} 行带={len(rows)} 选项行={len(opt_rows)}")

        # 2) 识别选项行：先按位置猜 4 行，再用 A/B/C/D 前缀校验修正
        def rec_line(a: int, b: int) -> tuple[str, float]:
            line = tight_crop(crop_line(img, a - 4, b + 4, 240, 1900))
            return rec(predictor, line, charset)

        got = []
        for (a, b) in opt_rows:
            got.append(rec_line(a, b))

        letters = [t[:1].upper() for t, _ in got]
        if letters != ["A", "B", "C", "D"]:
            # 位置猜错：在整题范围内找以 A/B/C/D 开头的 4 行
            all_rows = find_text_rows(img, y + 55, y_end - 5)
            cand = []
            for (a, b) in all_rows:
                t, s = rec_line(a, b)
                cand.append((t.strip(), s, (a, b)))
            picked = []
            used = set()
            for want in ("A", "B", "C", "D"):
                for idx, (t, s, box) in enumerate(cand):
                    if t[:1].upper() == want and idx not in used:
                        picked.append((t, s))
                        used.add(idx)
                        break
            if len(picked) == 4:
                got = picked

        if len(got) == 4:
            parsed = [clean_option(t) for t, s in got]
            avg = sum(s for _, s in got) / 4
            letters_ok = [t[:1].upper() for t, _ in got] == ["A", "B", "C", "D"]
            # 内容合理性：非空、长度适中、4 项不重复、不像题干整句
            nonempty = all(parsed)
            lens_ok = all(1 <= len(p) <= 90 for p in parsed)
            distinct = len(set(parsed)) == 4
            # 排除误把题干/下一题抓进来的情况
            not_stem = not any(re.match(r"^\d{1,2}[.、．]", p) for p in parsed)
            ok = nonempty and lens_ok and distinct and not_stem and avg >= 0.80
            if ok:
                print(f"      旧 {new_opts}")
                print(f"      新 {parsed}  (conf {avg:.2f})")
                if not dry:
                    new_opts = parsed
                fixed_opt += 1
            else:
                why = []
                if not nonempty: why.append("有空项")
                if not lens_ok: why.append("长度异常")
                if not distinct: why.append("重复")
                if not not_stem: why.append("像题干")
                if avg < 0.80: why.append(f"conf {avg:.2f}")
                print(f"      跳过 ({','.join(why)})")

        # 3) 题干：取选项区之上的所有行
        if opt_rows:
            stem_rows = [r for r in rows if r[1] < opt_rows[0][0]]
        else:
            stem_rows = rows
        if stem_rows:
            parts = []
            for (a, b) in stem_rows:
                line = tight_crop(crop_line(img, a - 4, b + 4, 240, 1900))
                t, s = rec(predictor, line, charset)
                if t.strip() and s > 0.55:
                    parts.append(t.strip())
            if parts:
                new_stem = "".join(parts)
                if len(new_stem) > len(stem_txt) * 0.8:
                    if not dry:
                        q["stem"] = new_stem
                    fixed_stem += 1
                    print(f"      题干: {new_stem[:70]}")

        if not dry:
            q["options"] = new_opts
            q["risky"] = (sum(1 for o in new_opts if o.strip()) < 4)

    print(f"\n选项修复 {fixed_opt} 道，题干修复 {fixed_stem} 道")
    if not dry:
        json.dump(bank, open(BANK, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        js = ("window.__BANK__ = "
              + json.dumps(bank, ensure_ascii=False, separators=(",", ":")) + ";")
        open(os.path.join(APP, "site", "data", "bank.js"), "w",
             encoding="utf-8").write(js)
        print("已写入 bank.json / bank.js")
    else:
        print("[dry-run] 未写入")


A_OPT = re.compile(r"^[A-Da-d]\s*[.、．]\s*")


def clean_option(t: str) -> str:
    """去掉选项前的 A. / B、 等字母前缀，保留内容。"""
    s = A_OPT.sub("", t.strip())
    s = s.strip(" ：:;；")
    return s


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv
    sample = None
    for i, a in enumerate(sys.argv):
        if a == "--sample" and i + 1 < len(sys.argv):
            sample = int(sys.argv[i + 1])

    if not os.path.exists(REC):
        print(f"缺少模型: {REC}")
        sys.exit(1)

    bank = json.load(open(BANK, encoding="utf-8"))
    pred = make_rec()
    charset = load_charset()
    process(bank, pred, charset, sample, dry)


if __name__ == "__main__":
    main()

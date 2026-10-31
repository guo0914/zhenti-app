"""
用 PaddleOCR（Paddle Inference 直接加载）重新识别 PDF 页面，修复题库识别错误。

关键点：
  - 模型必须放在纯 ASCII 路径（C:\\paddle_models），Paddle C++ 层不认中文路径
  - 直接使用 paddle.inference API，绕开 paddleocr 3.x 的封装兼容问题
  - 输入页面图片用 pypdfium2 从 PDF 渲染，scale 对齐原 OCR 坐标空间（2000x2800）

用法：
    python ocr_fix.py                 # 处理所有需要修的题
    python ocr_fix.py --pages 8,10    # 只处理指定页
    python ocr_fix.py --dry-run       # 不写回，只打印
"""

from __future__ import annotations

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("GLOG_minloglevel", "3")

import numpy as np
from PIL import Image

APP = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.path.join(APP, "..", ".pdfwork"))
PAGES = os.path.join(WORK, "pages")
MODELS = r"C:\paddle_models"
BANK = os.path.join(APP, "site", "data", "bank.json")

DET_DIR = os.path.join(MODELS, "ch_PP-OCRv4_det_infer")
REC_DIR = os.path.join(MODELS, "ch_PP-OCRv4_rec_infer")
DICT = os.path.join(MODELS, "ppocr_keys_v1.txt")


# ---------------------------------------------------------------- 预测器

def make_predictors():
    from paddle.inference import Config, create_predictor

    def build(d):
        cfg = Config(os.path.join(d, "inference.pdmodel"),
                     os.path.join(d, "inference.pdiparams"))
        cfg.disable_gpu()
        # 不使用 mkldnn：与 PP-OCRv4 的融合算子不兼容
        cfg.disable_mkldnn()
        cfg.set_cpu_math_library_num_threads(4)
        return create_predictor(cfg)

    return build(DET_DIR), build(REC_DIR)


def load_dict(path: str) -> list[str]:
    chars = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                chars.append(line)
    # CTC：blank + 字典
    return ["blank"] + chars + [" "]


# ---------------------------------------------------------------- 检测

def detect(det, img: np.ndarray) -> list[tuple]:
    """文本检测。返回 [([x0,y0,x1,y1], score), ...]（原图坐标）。"""
    h, w = img.shape[:2]

    # PaddleOCR 官方策略：限制最长边到 960（det_limit_side_len），
    # 并对齐到 32 的倍数。缩太小会让正文糊掉。
    limit = 960
    ratio = limit / max(h, w) if max(h, w) > limit else 1.0
    nh = max(32, int(round(h * ratio / 32) * 32))
    nw = max(32, int(round(w * ratio / 32) * 32))
    small = np.array(Image.fromarray(img).resize((nw, nh), Image.LANCZOS))

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1) * 255
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1) * 255
    x = small.astype(np.float32).transpose(2, 0, 1)
    x = (x - mean) / std
    x = np.array([x], dtype=np.float32)

    inp = det.get_input_handle(det.get_input_names()[0])
    inp.copy_from_cpu(x)
    det.run()
    pred = np.array(det.get_output_handle(det.get_output_names()[0]).copy_to_cpu())
    while pred.ndim > 2:
        pred = pred[0]

    boxes = pred_to_boxes(pred, 1.0)
    # 缩放回原图
    sx, sy = w / nw, h / nh
    out = []
    for (x0, y0, x1, y1), sc in boxes:
        out.append(([int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)], sc))
    out.sort(key=lambda t: (t[0][1], t[0][0]))
    return out


def pred_to_boxes(pred: np.ndarray, scale: float, thr: float = 0.3, box_thr: float = 0.5):
    """从 DB 概率图提取文本行框。

    做法：二值化 → 按行投影切出行带 → 行内按列投影切出词块，
    再把间距过小的词块合并成整行。贴近 PaddleOCR 的 DB 后处理思路。
    """
    h, w = pred.shape[-2:]
    mask = pred > thr
    if not mask.any():
        return []

    # 1) 行切分：水平投影
    row_has = mask.any(axis=1)
    rows = []
    start = None
    for y in range(h):
        if row_has[y] and start is None:
            start = y
        elif not row_has[y] and start is not None:
            if y - start >= 4:
                rows.append((start, y))
            start = None
    if start is not None and h - start >= 4:
        rows.append((start, h))

    out = []
    for y0, y1 in rows:
        band = mask[y0:y1]
        # 2) 列切分：带内投影
        col_has = band.any(axis=0)
        cols = []
        cs = None
        for x in range(w):
            if col_has[x] and cs is None:
                cs = x
            elif not col_has[x] and cs is not None:
                cols.append((cs, x))
                cs = None
        if cs is not None:
            cols.append((cs, w))
        if not cols:
            continue

        # 3) 合并间距小的列块（同一行被切碎的情况）
        merged = []
        cur = list(cols[0])
        for c in cols[1:]:
            if c[0] - cur[1] <= max(6, (y1 - y0) * 0.9):
                cur[1] = c[1]
            else:
                merged.append(tuple(cur))
                cur = list(c)
        merged.append(tuple(cur))

        for x0, x1 in merged:
            if x1 - x0 < 6:
                continue
            sub = pred[y0:y1, x0:x1]
            score = float(sub[sub > thr].mean()) if (sub > thr).any() else 0.0
            if score < box_thr:
                continue
            out.append(((x0, y0, x1, y1), score))

    out.sort(key=lambda t: (t[0][1], t[0][0]))
    return out


# ---------------------------------------------------------------- 识别

def recognize(rec, img: np.ndarray, box: tuple, charset: list[str]) -> tuple[str, float]:
    x0, y0, x1, y1 = box
    h, w = img.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return "", 0.0
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return "", 0.0

    # 统一高度 48，宽度按比例，限制最大 480
    ch = 48
    cw = max(1, int(crop.shape[1] * ch / crop.shape[0]))
    cw = min(cw, 480)
    c = Image.fromarray(crop).convert("RGB").resize((cw, ch), Image.LANCZOS)
    x = np.array(c).astype(np.float32) / 255.0
    x = (x - 0.5) / 0.5
    x = x.transpose(2, 0, 1)
    x = np.array([x], dtype=np.float32)

    inp = rec.get_input_handle(rec.get_input_names()[0])
    inp.copy_from_cpu(x)
    rec.run()
    pred = rec.get_output_handle(rec.get_output_names()[0]).copy_to_cpu()[0]

    idx = pred.argmax(axis=-1)
    score = pred.max(axis=-1)
    text, confs = [], []
    prev = -1
    for i, k in enumerate(idx):
        if k != prev and k != 0 and k < len(charset):
            text.append(charset[k])
            confs.append(float(score[i]))
        prev = k
    return "".join(text), (sum(confs) / len(confs) if confs else 0.0)


# ---------------------------------------------------------------- 主流程

def ocr_page(det, rec, charset, page_path: str) -> list[dict]:
    img = np.array(Image.open(page_path).convert("RGB"))
    boxes = detect(det, img)
    results = []
    for box, dscore in boxes:
        text, rscore = recognize(rec, img, box, charset)
        if text.strip():
            results.append({
                "text": text,
                "score": round(rscore, 4),
                "box": box,
                "y": box[1],
                "x": box[0],
            })
    return results


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv

    only_pages = None
    for i, a in enumerate(sys.argv):
        if a == "--pages" and i + 1 < len(sys.argv):
            only_pages = [int(x) for x in sys.argv[i + 1].split(",") if x.strip()]

    bank = json.load(open(BANK, encoding="utf-8"))
    qs = bank["questions"]
    targets = [q for q in qs if q.get("risky") or not all(o.strip() for o in q["options"])]
    pages = sorted(set(q["pg"] for q in targets if q.get("pg")))
    if only_pages:
        pages = [p for p in pages if p in only_pages]

    print(f"待处理题: {len(targets)}  页: {len(pages)}")
    det, rec = make_predictors()
    charset = load_dict(DICT)

    out_path = os.path.join(WORK, "reocr.json")
    all_res = {}
    if os.path.exists(out_path):
        try:
            all_res = json.load(open(out_path, encoding="utf-8"))
        except Exception:
            all_res = {}

    for n, pno in enumerate(pages, 1):
        fp = os.path.join(PAGES, f"p{pno:03d}.png")
        if not os.path.exists(fp):
            print(f"[{n}/{len(pages)}] 页 {pno}: 缺图片，跳过")
            continue
        try:
            res = ocr_page(det, rec, charset, fp)
            all_res[str(pno)] = res
            print(f"[{n}/{len(pages)}] 页 {pno}: {len(res)} 行", flush=True)
        except Exception as e:
            print(f"[{n}/{len(pages)}] 页 {pno}: FAIL {type(e).__name__} {str(e)[:120]}")

    if not dry:
        json.dump(all_res, open(out_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\n结果已写入 {out_path}")
    else:
        print("\n[dry-run] 未写入")


if __name__ == "__main__":
    main()

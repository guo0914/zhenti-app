# -*- coding: utf-8 -*-
"""
修复「题干配图 imgs」里混入选项图 optionImgs 的缺陷。

根因：parse_zhenti.py 按整个题目块（含选项）提取 <img>，选项里的图片也进了 imgs，
      前端渲染时题干下方就多出一张本属于选项 A 的图（如数量题公式选项、
      常识题的邮票图）。实测 653 道有题干图的题里 138 道存在这种重复。

规则：
  1. 从 imgs 中删掉所有同时出现在 optionImgs 的路径（选项图已在选项里渲染）；
  2. 对 imgs 自身去重（部分题因多份缓存 md 合并出现同一路径两次）。

安全边界：只删「与选项图完全相同路径」的图。题干里内联的公式符号图
（如电路题的 S1/S2 开关图）不在 optionImgs 中，不会被误删。

用法：
  python scripts/fix_img_option_dup.py --dry-run
  python scripts/fix_img_option_dup.py --apply
"""
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZT = os.path.join(BASE, 'site', 'data', 'zt')
SHARDS = ['politics', 'common', 'verbal', 'quantity', 'judge', 'graph', 'data', 'guokao']


def clean(imgs, optimgs):
    """返回 (新 imgs, 删掉的路径数, 去重数)"""
    oset = set(x for x in (optimgs or []) if x)
    seen = set()
    out = []
    dropped = 0
    dedup = 0
    for x in (imgs or []):
        if not x:
            continue
        if x in oset:
            dropped += 1
            continue
        if x in seen:
            dedup += 1
            continue
        seen.add(x)
        out.append(x)
    return out, dropped, dedup


def main():
    apply = '--apply' in sys.argv
    dry = '--dry-run' in sys.argv or not apply
    total_drop = 0
    total_dedup = 0
    touched = 0
    per_shard = {}

    for cat in SHARDS:
        p = os.path.join(ZT, cat + '.json')
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
        changed = False
        for q in data:
            imgs = q.get('imgs') or []
            oi = q.get('optionImgs') or []
            new, dropped, dedup = clean(imgs, oi)
            if dropped or dedup:
                if dropped:
                    total_drop += dropped
                if dedup:
                    total_dedup += dedup
                touched += 1
                per_shard[cat] = per_shard.get(cat, 0) + 1
                if apply:
                    q['imgs'] = new
                    changed = True
        if apply and changed:
            bak = p + '.imgoverlapbak'
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    print('模式:', 'APPLY（已写入）' if apply else 'DRY-RUN（只统计）')
    print('受影响题数:', touched)
    print('删除与选项图重复的引用:', total_drop)
    print('imgs 内部去重:', total_dedup)
    print('分片:', per_shard)
    if dry:
        print('\n加 --apply 才会真正写入。')


if __name__ == '__main__':
    main()

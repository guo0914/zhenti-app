#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Payload/ 目录打成 iOS 可安装的 .ipa。

用法：
    python3 mobile/scripts/make-ipa.py <Payload 目录> <输出 .ipa>

为什么不用 `zip -r`：
macOS 自带的 zip 在部分版本里会把 UTF-8 文件名原样写进 zip，但**不设置**
0x800（UTF-8）标志位。iOS 安装时按 cp437 解释这些名字，含中文的目录
（例如 assets/zt/题目图/）就变成乱码目录，App 运行时按原路径请求图片
全部 404 —— 表现就是「一张图都看不到」。这里用 zipfile 显式置位。

同时保留 unix 权限位（可执行位对 .app 里的二进制是必需的）。
"""
import os
import stat
import sys
import zipfile

UTF8_FLAG = 0x800


def add_path(zf, fs_path, arc_name):
    st = os.stat(fs_path)
    is_dir = stat.S_ISDIR(st.st_mode)
    if is_dir and not arc_name.endswith("/"):
        arc_name += "/"
    zi = zipfile.ZipInfo(arc_name)
    zi.flag_bits |= UTF8_FLAG      # 明确声明文件名是 UTF-8
    zi.create_system = 3           # unix，让 iOS 认权限位
    zi.external_attr = (st.st_mode & 0xFFFF) << 16
    if is_dir:
        zi.external_attr |= 0x10   # MS-DOS 目录标记
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, b"")
        return
    zi.compress_type = zipfile.ZIP_DEFLATED
    with open(fs_path, "rb") as f:
        zf.writestr(zi, f.read())


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    payload, out = sys.argv[1], sys.argv[2]
    if not os.path.isdir(payload):
        print("错误：找不到 Payload 目录 %s" % payload)
        return 1
    if os.path.exists(out):
        os.remove(out)

    base = os.path.basename(os.path.normpath(payload))
    n_file = n_dir = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        add_path(zf, payload, base)
        n_dir += 1
        for root, dirs, files in os.walk(payload):
            dirs.sort()
            files.sort()
            rel = os.path.relpath(root, payload)
            arc_root = base if rel == "." else base + "/" + rel.replace(os.sep, "/")
            for d in dirs:
                add_path(zf, os.path.join(root, d), arc_root + "/" + d)
                n_dir += 1
            for f in files:
                add_path(zf, os.path.join(root, f), arc_root + "/" + f)
                n_file += 1

    # 自校验：所有非 ASCII 名字必须带 UTF-8 标志位
    bad = 0
    with zipfile.ZipFile(out) as zf:
        for info in zf.infolist():
            try:
                info.filename.encode("ascii")
            except UnicodeEncodeError:
                if not (info.flag_bits & UTF8_FLAG):
                    bad += 1
    size = os.path.getsize(out)
    print("IPA 生成：%s" % out)
    print("  条目 %d 个（目录 %d / 文件 %d）" % (n_file + n_dir, n_dir, n_file))
    print("  体积 %.2f MB" % (size / 1048576.0))
    print("  非 ASCII 名字缺 UTF-8 标志位：%d" % bad)
    if bad:
        print("错误：仍有条目缺 UTF-8 标志位")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

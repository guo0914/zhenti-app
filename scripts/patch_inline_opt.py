"""给 law.js / papers.js 的选项字母块加内联样式

目的：不依赖外部 CSS，保证字母块在任何环境下都可见。
"""
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LETTER_STYLE = (
    'style="display:inline-flex;align-items:center;justify-content:center;'
    'flex:0 0 24px;width:24px;min-width:24px;height:24px;border-radius:7px;'
    'background:#d8dfec;color:#46506a;font-size:12.5px;font-weight:700;'
    'line-height:1;margin-top:1px;box-sizing:border-box;"'
)

OPT_STYLE = (
    'style="display:flex;gap:11px;align-items:flex-start;text-align:left;'
    'width:100%;max-width:100%;box-sizing:border-box;min-width:0;'
    'border:1.5px solid #c5cddd;background:#fff;border-radius:11px;'
    'padding:10px 13px;font:inherit;font-size:14.5px;line-height:1.7;'
    'color:inherit;cursor:pointer;"'
)


def patch(path):
    s = open(path, encoding="utf-8").read()
    orig = s
    n_letter = 0
    n_btn = 0

    # 1) letter span：'<span class="letter">' + key + '</span>'
    #    这类拼接里 key 是变量，用正则匹配整段
    pat_letter = re.compile(
        r'<span class="letter">\'?\s*\+\s*key\s*\+\s*\'</span>')
    def repl_letter(m):
        nonlocal n_letter
        n_letter += 1
        return ("'<span class=\"letter\" " + LETTER_STYLE + ">' + key + '</span>")
    s2, c = pat_letter.subn(
        lambda m: '\'<span class="letter" ' + LETTER_STYLE + '>\' + key + \'</span>',
        s)
    if c:
        s = s2
        n_letter = c

    # 2) option button 开头：
    #    '<button class="' + cls + '" data-k="' + key + '">'
    pat_btn = re.compile(
        r"\'<button\s+class=\"\'\s*\+\s*cls\s*\+\s*\'\"\s+data-k=\"\'\s*\+\s*key\s*\+\s*\'\">\'")
    s2, c2 = pat_btn.subn(
        lambda m: ("'<button class=\"' + cls + '\" data-k=\"' + key + '\" "
                   + OPT_STYLE + ">'"),
        s)
    if c2:
        s = s2
        n_btn = c2

    if s != orig:
        open(path, "w", encoding="utf-8").write(s)
    print(f"{path}: letter {n_letter} 处, button {n_btn} 处")


for p in ["site/assets/law.js", "site/assets/papers.js"]:
    patch(p)

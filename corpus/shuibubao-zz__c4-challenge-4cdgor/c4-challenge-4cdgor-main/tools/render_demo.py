#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_demo.py — 把 challenge-submit-guard 的真实终端输出渲染成 demo 截图。

注意：图片里的文字**全部来自真实运行输出**（evidence/*.txt），本脚本只做排版，
不改写、不编造任何一个字符。原始输出留档在同目录 evidence/ 下，可逐字复核。

用法：
    python tools/render_demo.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE = os.path.join(ROOT, "evidence")
OUT_DIR = os.path.join(ROOT, "demo")

FONT_MONO = "C:/Windows/Fonts/consola.ttf"
FONT_CJK = "C:/Windows/Fonts/msyh.ttc"
FONT_EMOJI = "C:/Windows/Fonts/seguiemj.ttf"

FONT_SIZE = 15
LINE_H = 24
PAD_X = 26
PAD_Y = 20
TITLE_H = 46
FOOTER_H = 40
MAX_CELLS = 128
MIN_CELLS = 76

BG = (255, 255, 255)
TITLE_BG = (246, 247, 249)
BORDER = (208, 215, 222)
TITLE_FG = (87, 96, 106)
TEXT = (31, 35, 40)
DIM = (110, 119, 129)
GREEN = (26, 127, 55)
RED = (207, 34, 46)
AMBER = (154, 103, 0)
BLUE = (9, 105, 218)


def load_fonts(size):
    mono = ImageFont.truetype(FONT_MONO, size)
    cjk = ImageFont.truetype(FONT_CJK, size)
    try:
        emoji = ImageFont.truetype(FONT_EMOJI, size)
    except Exception:
        emoji = cjk
    return mono, cjk, emoji


def is_wide(ch):
    """东亚宽字符 / 全角符号按 2 个字符宽度排版（终端行为）。"""
    o = ord(ch)
    return (
        0x1100 <= o <= 0x115F
        or 0x2E80 <= o <= 0xA4CF
        or 0xAC00 <= o <= 0xD7A3
        or 0xF900 <= o <= 0xFAFF
        or 0xFE30 <= o <= 0xFE6F
        or 0xFF00 <= o <= 0xFF60
        or 0xFFE0 <= o <= 0xFFE6
        or 0x1F000 <= o <= 0x1FAFF
        or 0x2600 <= o <= 0x27BF
    )


def is_emoji(ch):
    o = ord(ch)
    return 0x1F000 <= o <= 0x1FAFF or o in (0x2705, 0x274C, 0x26A0, 0xFE0F, 0x26A1)


def cell_width(line):
    return sum(2 if is_wide(c) else 1 for c in line)


def wrap(line):
    """按字符宽度换行（终端软换行）。"""
    if cell_width(line) <= MAX_CELLS:
        return [line]
    out, cur, w = [], [], 0
    for ch in line:
        cw = 2 if is_wide(ch) else 1
        if w + cw > MAX_CELLS:
            out.append("".join(cur))
            cur, w = [], 0
        cur.append(ch)
        w += cw
    if cur:
        out.append("".join(cur))
    return out


def line_color(line):
    s = line.strip()
    if s.startswith("✅"):
        return GREEN
    if s.startswith("❌") or s.startswith("🚩"):
        return RED
    if s.startswith("⚠️") or s.startswith("⚠"):
        return AMBER
    if s.startswith("#"):
        return BLUE
    if s.startswith(">") or s.startswith("_") or s.startswith("---"):
        return DIM
    if s.startswith("**粗估总分"):
        return BLUE
    return TEXT


def render(mono, cjk, emoji, char_w, title, lines, footer, out_path):
    wrapped = []
    for ln in lines:
        wrapped.extend(wrap(ln.rstrip("\n").replace("\t", "    ")))

    cells = max([cell_width(l) for l in wrapped] + [cell_width(title), MIN_CELLS])
    cells = min(cells + 2, MAX_CELLS + 2)

    width = int(PAD_X * 2 + cells * char_w)
    height = TITLE_H + PAD_Y * 2 + len(wrapped) * LINE_H + FOOTER_H

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # 窗口标题栏
    d.rectangle([0, 0, width, TITLE_H], fill=TITLE_BG)
    d.line([0, TITLE_H, width, TITLE_H], fill=BORDER, width=1)
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 18 + i * 20
        d.ellipse([cx - 5, TITLE_H // 2 - 5, cx + 5, TITLE_H // 2 + 5], fill=col)
    d.text((110, TITLE_H // 2), title, font=cjk, fill=TITLE_FG, anchor="lm")

    # 正文
    y = TITLE_H + PAD_Y
    for line in wrapped:
        x = PAD_X
        color = line_color(line)
        for ch in line:
            if is_emoji(ch):
                fnt = emoji
            elif is_wide(ch) and not is_emoji(ch):
                fnt = cjk
            else:
                fnt = mono
            d.text((x, y + LINE_H / 2), ch, font=fnt, fill=color, anchor="lm")
            x += char_w * (2 if is_wide(ch) else 1)
        y += LINE_H

    # 页脚
    d.line([0, height - FOOTER_H, width, height - FOOTER_H], fill=BORDER, width=1)
    d.text(
        (PAD_X, height - FOOTER_H / 2),
        footer,
        font=cjk,
        fill=DIM,
        anchor="lm",
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    print("  → %s (%dx%d)" % (os.path.basename(out_path), width, height))


def read_ev(name):
    with open(os.path.join(EVIDENCE, name), encoding="utf-8") as fh:
        return fh.read().splitlines()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    mono, cjk, emoji = load_fonts(FONT_SIZE)
    char_w = mono.getlength("M")
    print("字号 %d / 字符宽 %.2f px" % (FONT_SIZE, char_w))

    base = "$ python challenge_submit_guard.py"

    # 01 自检
    render(
        mono, cjk, emoji, char_w,
        "Terminal — challenge-submit-guard --self-test",
        ["%s --self-test" % base, ""]
        + read_ev("selftest_output.txt"),
        "图1  内置自检：任意机器 3 秒可验证（5 个合成夹具断言，全部来自真实运行输出）",
        os.path.join(ROOT, "卢怡然_C4_demo_01.png"),
    )

    # 02 真实 C3 体检报告
    c3 = read_ev("run_C3_real.txt")
    render(
        mono, cjk, emoji, char_w,
        "Terminal — 对我自己的 C3 交付包做真实体检",
        ['%s "C:/Users/卢怡然/Desktop/C3" -c C3' % base, ""]
        + c3[:40],
        "图2  真实案例：交付物 3/3、无红线、粗估 90/100（平台实评 77 —— 差距原因见报告第 7 节）",
        os.path.join(ROOT, "卢怡然_C4_demo_02.png"),
    )

    # 03 报告下半部分（第 5-7 节）
    render(
        mono, cjk, emoji, char_w,
        "Terminal — 提分杠杆 / TODO / 机器查不到的事",
        c3[40:],
        "图3  第 5-7 节：先解红线再补内容；第 7 节是我被 C3 的 -13 分打脸后补上的",
        os.path.join(ROOT, "卢怡然_C4_demo_03.png"),
    )

    # 04 注册表覆盖 20 个挑战
    render(
        mono, cjk, emoji, char_w,
        "Terminal — 注册表覆盖 20 个挑战",
        ["%s --list" % base, ""]
        + read_ev("list_output.txt"),
        "图4  --list：20 个挑战的必交交付物清单，注册表由平台 rubric.json 自动生成，非手打",
        os.path.join(ROOT, "卢怡然_C4_demo_04.png"),
    )


if __name__ == "__main__":
    main()

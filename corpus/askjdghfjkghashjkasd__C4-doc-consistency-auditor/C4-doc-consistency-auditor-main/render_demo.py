#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the doc-consistency-auditor demo screenshot with Pillow + system STHeiti font."""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = "/Users/bingtanghulu./.cogseed/userWorkSpace/我的挑战/C4-技能分享与传播"
OUT = os.path.join(BASE, "2025105400130_C4_demo.png")
FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"

# ---- palette (GitHub dark) ----
BG      = "#0d1117"
PANEL   = "#161b22"
BORDER  = "#30363d"
BAR     = "#21262d"
TXT     = "#c9d1d9"
MUTED   = "#8b949e"
CMD     = "#79c0ff"
PROMPT  = "#7ee787"
OK      = "#7ee787"
WARN    = "#ffa657"
ERR     = "#ff7b72"
WARNT   = "#ffa657"
LOC     = "#d2a8ff"
DOTR = "#ff5f56"; DOTY = "#ffbd2e"; DOTG = "#27c93f"

W = 1280
M = 40
CW = W - 2 * M

F_TITLE = ImageFont.truetype(FONT_PATH, 26, index=0)
F_SUB   = ImageFont.truetype(FONT_PATH, 14, index=0)
F_BAR   = ImageFont.truetype(FONT_PATH, 13, index=0)
F_BODY  = ImageFont.truetype(FONT_PATH, 16, index=0)

LINE_H = 26      # body line height
BAR_H  = 42
PAD    = 20      # panel inner padding
GAP    = 24      # gap between panels

def tw(font, s):
    return font.getlength(s)

def wrap_segments(segs, font, maxw):
    """Wrap a run of segments (text,color) into lines of segments, breaking long text at spaces/CJK."""
    lines = []
    cur = []
    curw = 0
    for text, color in segs:
        # greedy char wrap for this segment
        buf = ""
        for ch in text:
            t = buf + ch
            w = tw(font, t)
            if w > maxw and buf:
                cur.append((buf, color))
                lines.append(cur)
                cur = []
                buf = ch
            else:
                buf = t
        if buf:
            cur.append((buf, color))
    if cur:
        lines.append(cur)
    return lines

# ---- content model ----
# each item: ("title"|"panel_bar"|"line"|"blank", payload)
items = []

items.append(("title", "doc-consistency-auditor"))
items.append(("sub", "Markdown 文档一致性审计器 · 真实运行输出（纯 Python 标准库，零第三方依赖）"))
items.append(("blank", 10))

items.append(("bar", "演示 ① — 审计一份「有问题」的文档"))
items.append(("cmd", [
    ("$ ", PROMPT),
    ("python3 doc-consistency-auditor/scripts/audit.py --path demo/sample_bad.md --glossary doc-consistency-auditor/references/glossary.example.yaml", CMD),
]))
items.append(("blank", 6))
items.append(("line", [("⚠️  审计发现 7 个问题（错误 6，警告 1）：", WARN)]))
findings1 = [
    ("[01]", "R1", ERR, "sample_bad.md:11", "出现禁用写法「github」", "建议：统一为「GitHub」"),
    ("[02]", "R1", ERR, "sample_bad.md:11", "出现禁用写法「Github」", "建议：统一为「GitHub」"),
    ("[03]", "R1", ERR, "sample_bad.md:11", "出现禁用写法「GH」", "建议：统一为「GitHub」"),
    ("[04]", "R4", WARNT, "sample_bad.md:19", "标题「配置环境变量」重复（首次出现在第 15 行）", "建议：重命名或合并重复标题"),
    ("[05]", "R2", ERR, "sample_bad.md:7", "目标「./install.md」不存在", "建议：补文件或修正路径"),
    ("[06]", "R2", ERR, "sample_bad.md:7", "锚点「#config」未命中任何标题", "建议：补同名标题或修正链接"),
    ("[07]", "R2", ERR, "sample_bad.md:17", "目标「./deploy.md」不存在", "建议：补文件或修正路径"),
]
for idx, rule, tagc, loc, desc, sug in findings1:
    items.append(("line", [
        ("  " + idx + " ", TXT),
        ("[" + ("错误" if tagc == ERR else "警告") + "]", tagc),
        (" " + rule, tagc),
        (" @ " + loc, LOC),
    ]))
    items.append(("line", [("        " + desc, TXT)]))
    items.append(("line", [("        " + sug, MUTED)]))
items.append(("blank", 6))
items.append(("line", [("退出码 = 1", PROMPT), ("  （发现问题，可用于 CI 门禁）", MUTED)]))

items.append(("blank", 4))
items.append(("bar", "演示 ② — 审计一份「干净」的文档"))
items.append(("cmd", [
    ("$ ", PROMPT),
    ("python3 doc-consistency-auditor/scripts/audit.py --path demo/sample_clean.md --glossary doc-consistency-auditor/references/glossary.example.yaml", CMD),
]))
items.append(("blank", 6))
items.append(("line", [("✅ 审计通过（demo/sample_clean.md）：未发现一致性问题。", OK)]))
items.append(("line", [("退出码 = 0", PROMPT)]))
items.append(("blank", 4))
items.append(("sub", "五类规则：R0 文件规模 · R1 术语一致性 · R2 内部链接/锚点 · R3 标题层级 · R4 重复标题 · R5 交付物清单　|　输出：终端 + Markdown 报告 + JSON"))

# ---- layout pass ----
# We build a list of draw primitives: (kind, y, payload)
prim = []
y = 28  # top pad

def add_title(seg, font, lh):
    global y
    prim.append(("text", y, (seg, TXT, font, M)))
    y += lh

def add_line(segs, font):
    global y
    wrapped = wrap_segments(segs, font, CW)
    for wl in wrapped:
        prim.append(("text", y, (wl, None, font, M)))
        y += LINE_H

def add_cmd(segs):
    global y
    font = F_BODY
    # render "$ " prefix then wrapped command indented
    prim.append(("text", y, ([("$ ", PROMPT)], None, font, M)))
    # wrap command with indent so continuation aligns
    cmdseg = segs[1]
    wrapped = wrap_segments([cmdseg], font, CW - tw(font, "$ "))
    # first line continues after "$ "
    first = wrapped[0]
    prim.append(("text", y, (first, None, font, M + tw(font, "$ "))))
    y += LINE_H
    for wl in wrapped[1:]:
        prim.append(("text", y, (wl, None, font, M + tw(font, "  "))))
        y += LINE_H

for kind, payload in items:
    if kind == "title":
        prim.append(("text", y, ([(payload, None)], TXT, F_TITLE, M)))
        y += 34
    elif kind == "sub":
        add_line([(payload, MUTED)], F_SUB)
        y += 2
    elif kind == "blank":
        y += payload
    elif kind == "bar":
        # bar background drawn separately; record y range and label
        prim.append(("bar", y, (payload, None)))
        y += BAR_H
    elif kind == "line":
        add_line(payload, F_BODY)
    elif kind == "cmd":
        add_cmd(payload)

y += 28  # bottom pad
HEIGHT = y

# ---- draw pass ----
img = Image.new("RGB", (W, HEIGHT), BG)
d = ImageDraw.Draw(img)

# panels: draw bg + border + bar behind their content. We need panel extents.
# Simpler: draw a full left-right panel behind each bar's block by scanning prim for "bar" markers.
# We'll track bar y positions and next bar, then fill panel rect from bar.y to next bar.y (or a footer).
bar_ys = [(i, p[1]) for i, p in enumerate(prim) if p[0] == "bar"]

def panel_bounds():
    bounds = []
    for bi, (i, by) in enumerate(bar_ys):
        # end = next bar y - GAP, else footer start
        if bi + 1 < len(bar_ys):
            endy = bar_ys[bi+1][1] - GAP
        else:
            endy = HEIGHT - 28 - 20
        bounds.append((by - 6, endy))
    return bounds

pb = panel_bounds()
for (top, bot) in pb:
    d.rounded_rectangle([M - 12, top, W - M + 12, bot], radius=12, fill=PANEL, outline=BORDER, width=1)

for kind, yy, payload in prim:
    if kind == "bar":
        label = payload[0]
        # bar title bar (with dots)
        d.rounded_rectangle([M - 12, yy, W - M + 12, yy + BAR_H], radius=12, fill=BAR)
        # cover bottom corners of bar to blend into panel
        d.rectangle([M - 12, yy + BAR_H - 12, W - M + 12, yy + BAR_H], fill=BAR)
        d.rectangle([M - 12, yy, M + 12, yy + BAR_H], fill=BAR)
        d.rectangle([W - M - 12, yy, W - M + 12, yy + BAR_H], fill=BAR)
        # dots
        cx = M - 12 + 24
        for dotc in (DOTR, DOTY, DOTG):
            d.ellipse([cx, yy + BAR_H//2 - 6, cx + 12, yy + BAR_H//2 + 6], fill=dotc)
            cx += 22
        d.text((cx + 10, yy + (BAR_H - tw(F_BAR, label)) / 2 - 11), label, font=F_BAR, fill=MUTED)
    elif kind == "text":
        segs, _, font, x = payload
        # draw segments with colors
        for (txt, color) in segs:
            c = color if color else TXT
            d.text((x, yy), txt, font=font, fill=c)
            x += tw(font, txt)

img.save(OUT, "PNG")
print("已生成:", OUT)
print("尺寸:", img.size)

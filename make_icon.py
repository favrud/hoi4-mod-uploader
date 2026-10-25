#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HOI4 Mod 上传工具 图标生成器
============================
生成 uploader_icon.ico（16~256 多尺寸）与 icon_256.png 预览图。
设计：深色圆角底 + 黄铜渐变"上传箭头 + 托盘"，呼应 HOI4 的深色黄铜 UI 风。
需要 Pillow：pip install pillow
"""

import os
from PIL import Image, ImageDraw

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
ICO_PATH = os.path.join(TOOL_DIR, "uploader_icon.ico")
PNG_PATH = os.path.join(TOOL_DIR, "icon_256.png")

SS = 4                       # 超采样倍数，抗锯齿
S = 256 * SS

# 配色
BG_TOP = (0x2c, 0x32, 0x3d)  # 背景渐变顶
BG_BOT = (0x10, 0x13, 0x18)  # 背景渐变底
BRASS_TOP = (0xf2, 0xcb, 0x74)   # 黄铜亮部
BRASS_BOT = (0xac, 0x82, 0x2a)   # 黄铜暗部
BORDER = (0xd4, 0xa9, 0x4e, 255) # 外圈描边


def v_gradient(size, top, bot, y0=0, y1=None):
    """生成垂直渐变图层"""
    y1 = size if y1 is None else y1
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    span = max(1, y1 - y0)
    for y in range(size):
        t = min(1.0, max(0.0, (y - y0) / span))
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line([(0, y), (size, y)], fill=c)
    return img


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # ---- 背景：深色渐变圆角方块 ----
    m = 10 * SS
    radius = 58 * SS
    bg = v_gradient(S, BG_TOP, BG_BOT)
    bg_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bg_mask).rounded_rectangle(
        (m, m, S - m, S - m), radius=radius, fill=255)
    img.paste(bg, (0, 0), bg_mask)

    draw = ImageDraw.Draw(img)
    # 外圈黄铜描边
    draw.rounded_rectangle((m, m, S - m, S - m), radius=radius,
                           outline=BORDER, width=5 * SS)
    # 内圈细线，增加层次
    draw.rounded_rectangle((m + 9 * SS, m + 9 * SS, S - m - 9 * SS, S - m - 9 * SS),
                           radius=radius - 9 * SS,
                           outline=(255, 255, 255, 18), width=SS)

    cx = S // 2
    # ---- 上传箭头（黄铜渐变）----
    a_top = 52 * SS       # 箭头顶点
    a_head_h = 64 * SS    # 箭头头部高度
    a_head_w = 118 * SS   # 箭头头部宽度
    a_shaft_w = 42 * SS   # 箭杆宽度
    a_bot = 166 * SS      # 箭杆底部
    arrow = [
        (cx, a_top),
        (cx + a_head_w // 2, a_top + a_head_h),
        (cx + a_shaft_w // 2, a_top + a_head_h),
        (cx + a_shaft_w // 2, a_bot),
        (cx - a_shaft_w // 2, a_bot),
        (cx - a_shaft_w // 2, a_top + a_head_h),
        (cx - a_head_w // 2, a_top + a_head_h),
    ]
    brass = v_gradient(S, BRASS_TOP, BRASS_BOT, a_top, a_bot)
    arrow_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(arrow_mask).polygon(arrow, fill=255)
    img.paste(brass, (0, 0), arrow_mask)

    # ---- 底部托盘（上传符号的下横线）----
    t_y0, t_y1, t_w = 184 * SS, 202 * SS, 148 * SS
    tray_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(tray_mask).rounded_rectangle(
        (cx - t_w // 2, t_y0, cx + t_w // 2, t_y1),
        radius=9 * SS, fill=255)
    img.paste(brass, (0, 0), tray_mask)

    # ---- 缩小抗锯齿输出 ----
    icon = img.resize((256, 256), Image.LANCZOS)
    icon.save(ICO_PATH, format="ICO",
              sizes=[(256, 256), (128, 128), (64, 64), (48, 48),
                     (32, 32), (24, 24), (16, 16)])
    icon.save(PNG_PATH)
    print("已生成:", ICO_PATH)
    print("已生成:", PNG_PATH)


if __name__ == "__main__":
    main()

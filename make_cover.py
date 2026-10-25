#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Wolfenstein 新秩序汉化 mod 封面图"""

import urllib.request
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 背景图URL
BG_URL = "https://aka.doubaocdn.com/s/63Uu2mAZFv"
# 输出目录（与脚本同目录）
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
BG_PATH = os.path.join(OUTPUT_DIR, "cover_bg.png")
FINAL_PATH = os.path.join(OUTPUT_DIR, "thumbnail.png")

# 字体路径
FONT_IMPACT = r"C:\Windows\Fonts\impact.ttf"
FONT_YAHEI_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_YAHEI = r"C:\Windows\Fonts\msyh.ttc"


def download_bg():
    print("下载背景图...")
    urllib.request.urlretrieve(BG_URL, BG_PATH)
    print(f"背景图已保存: {BG_PATH}")


def draw_text_with_glow(draw, pos, text, font, fill, stroke_fill, stroke_width, glow_color=None, glow_radius=0):
    """绘制带发光/描边效果的文字"""
    x, y = pos
    if glow_color and glow_radius > 0:
        # 发光层：多次绘制偏移的半透明文字
        for dx in range(-glow_radius, glow_radius + 1, 2):
            for dy in range(-glow_radius, glow_radius + 1, 2):
                draw.text((x + dx, y + dy), text, font=font, fill=glow_color)
    # 主文字带描边
    draw.text((x, y), text, font=font, fill=fill,
              stroke_width=stroke_width, stroke_fill=stroke_fill)


def main():
    if not os.path.isfile(BG_PATH):
        download_bg()

    img = Image.open(BG_PATH).convert("RGBA")
    W, H = img.size  # 1920x1080
    print(f"图片尺寸: {W}x{H}")

    # 创建半透明渐变遮罩，让底部文字更清晰
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # 底部渐变黑色
    for y in range(H // 2, H):
        alpha = int(180 * (y - H // 2) / (H // 2))
        od.line([(0, y), (W, y)], fill=(0, 0, 0, min(alpha, 200)))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)

    # ===== 主标题 WOLFENSTEIN =====
    font_main = ImageFont.truetype(FONT_IMPACT, 130)
    title = "WOLFENSTEIN"
    bbox = draw.textbbox((0, 0), title, font=font_main, stroke_width=4)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (W - tw) // 2
    ty = int(H * 0.52)
    # 红色发光 + 白色文字 + 黑色粗描边
    draw_text_with_glow(draw, (tx, ty), title, font_main,
                         fill=(245, 240, 235, 255),
                         stroke_fill=(20, 0, 0, 255),
                         stroke_width=5,
                         glow_color=(180, 20, 20, 120),
                         glow_radius=6)

    # ===== 中文副标题 新秩序 =====
    font_sub = ImageFont.truetype(FONT_YAHEI_BOLD, 72)
    subtitle = "新 秩 序"
    bbox = draw.textbbox((0, 0), subtitle, font=font_sub, stroke_width=3)
    sw = bbox[2] - bbox[0]
    sx = (W - sw) // 2
    sy = ty + th + 20
    draw_text_with_glow(draw, (sx, sy), subtitle, font_sub,
                         fill=(230, 220, 210, 255),
                         stroke_fill=(40, 5, 5, 255),
                         stroke_width=3,
                         glow_color=(150, 15, 15, 100),
                         glow_radius=4)

    # ===== 底部 简体中文汉化包 =====
    font_tag = ImageFont.truetype(FONT_YAHEI_BOLD, 38)
    tag = "简 体 中 文 汉 化 包"
    bbox = draw.textbbox((0, 0), tag, font=font_tag, stroke_width=2)
    gw = bbox[2] - bbox[0]
    gx = (W - gw) // 2
    gy = int(H * 0.86)
    # 红色底条
    bar_h = 56
    bar_w = gw + 80
    bar_x = (W - bar_w) // 2
    bar_y = gy - 8
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
                   fill=(140, 15, 15, 220), outline=(200, 40, 40, 255), width=2)
    draw.text((gx, gy), tag, font=font_tag, fill=(255, 250, 245, 255),
              stroke_width=1, stroke_fill=(60, 0, 0, 255))

    # ===== 顶部小字 HOI4 Mod =====
    font_top = ImageFont.truetype(FONT_YAHEI, 26)
    top_text = "HEARTS OF IRON IV  ·  MOD"
    bbox = draw.textbbox((0, 0), top_text, font=font_top)
    tw2 = bbox[2] - bbox[0]
    draw.text(((W - tw2) // 2, 40), top_text, font=font_top,
              fill=(200, 190, 180, 200), stroke_width=1, stroke_fill=(0, 0, 0, 200))

    # 保存
    img = img.convert("RGB")
    img.save(FINAL_PATH, "PNG", quality=95)
    print(f"封面已保存: {FINAL_PATH}")
    print(f"文件大小: {os.path.getsize(FINAL_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    main()

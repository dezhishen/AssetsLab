#!/usr/bin/env python3
"""AssetsLab — 3D 绘制原语（Pillow，纯 Python）。

提供画布与骨架绘制基础函数（canvas / bone / head / joint），
供 skeleton3d 的 3D 渲染（render_view / render_pose）使用。
颜色与线宽为纯常量；2D 遗留渲染（多视图动作帧/接触表/GIF）已随
方案 A 移除——3D 预览是唯一预览路径。
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 960, 600
FLOOR_Y = 470.0
CENTER_X = 480.0
ROOT_X = 480.0

BG = (17, 24, 39)          # 111827
GUIDE = (75, 94, 122)      # 4b5e7a
BONE = (157, 214, 255)     # 9dd6ff
JOINT = (255, 241, 168)    # fff1a8
REAR = (127, 159, 196)     # 7f9fc4
FRONT = (255, 210, 122)    # ffd27a
PELVIS_C = (255, 188, 115)  # ffbc73
ARM = (169, 232, 195)      # a9e8c3
DARK = (30, 58, 95)        # 1e3a5f
BONE_DARK = (30, 42, 63)   # 1e3a5f
HEAD_DARK = (35, 51, 74)   # 23334a
OUTLINE = (90, 130, 170)   # body outline color


def canvas():
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.line([(160, FLOOR_Y), (800, FLOOR_Y)], fill=GUIDE, width=2)
    return image, draw


def bone(draw, a, b, color, width=7):
    draw.line([a, b], fill=BONE_DARK, width=width + 6)
    draw.line([a, b], fill=color, width=width)


def head(draw, center, color=BONE, radius=24, width=3):
    """Draw head as a tall oval (model proportion, taller than wide)."""
    cx, cy = center
    rx, ry = int(radius * 0.78), radius  # tall oval: clearly narrower than tall
    box = (cx - rx, cy - ry, cx + rx, cy + ry)
    draw.ellipse(box, fill=(45, 60, 90), outline=color, width=width)


def joint(draw, point, color=JOINT, radius=7):
    box = (point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius)
    draw.ellipse(box, fill=color, outline=HEAD_DARK, width=2)

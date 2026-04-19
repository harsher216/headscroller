"""Generate a clean installer background for HeadScroller.
Renders at 3x super-sampled resolution, then downsamples with LANCZOS
so lines and arrowhead stay crisp on Retina displays.
"""
from PIL import Image, ImageDraw, ImageFont
import math
import os

SS = 3                          # super-sample factor
W, H = 600, 400                 # final 1x size
WS, HS = W * SS, H * SS

BG_TOP = (250, 246, 239)
BG_BOT = (244, 238, 228)
INK = (24, 24, 28)
MUTED = (100, 100, 110)
ARROW = (110, 110, 120)

img = Image.new("RGB", (WS, HS), BG_TOP)
draw = ImageDraw.Draw(img)

# Vertical gradient
for y in range(HS):
    t = y / HS
    c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
    draw.line([(0, y), (WS, y)], fill=c)


def load_font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


title_font = load_font(
    [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/NewYork.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    ],
    38 * SS,
)
sub_font = load_font(
    [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    14 * SS,
)

# Title
title = "Install HeadScroller"
tb = draw.textbbox((0, 0), title, font=title_font)
tw = tb[2] - tb[0]
draw.text(((WS - tw) // 2, 56 * SS), title, font=title_font, fill=INK)

# Subtitle
sub = "Drag the app into your Applications folder"
sb = draw.textbbox((0, 0), sub, font=sub_font)
sw = sb[2] - sb[0]
draw.text(((WS - sw) // 2, 108 * SS), sub, font=sub_font, fill=MUTED)


def dashed_curve(draw_ctx, start, end, color, width=2, dash_len=6, gap_len=5,
                 curvature=-40):
    x0, y0 = start
    x1, y1 = end
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1
    px, py = -dy / length, dx / length
    cx = mx + px * curvature
    cy = my + py * curvature

    pts = []
    steps = 400
    for i in range(steps + 1):
        t = i / steps
        bx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1
        by = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1
        pts.append((bx, by))

    drawing = True
    remaining = dash_len
    for i in range(1, len(pts)):
        ax, ay = pts[i - 1]
        bx, by = pts[i]
        seg = math.hypot(bx - ax, by - ay)
        if seg == 0:
            continue
        while seg > 0:
            step = min(seg, remaining)
            nx = ax + (bx - ax) * (step / max(seg, 0.0001))
            ny = ay + (by - ay) * (step / max(seg, 0.0001))
            if drawing:
                draw_ctx.line([(ax, ay), (nx, ny)], fill=color, width=width)
            ax, ay = nx, ny
            seg -= step
            remaining -= step
            if remaining <= 0:
                drawing = not drawing
                remaining = dash_len if drawing else gap_len

    ex, ey = pts[-1]
    px2, py2 = pts[-6]
    ang = math.atan2(ey - py2, ex - px2)
    ahl = width * 5
    ahw = width * 3
    p1 = (ex, ey)
    p2 = (ex - ahl * math.cos(ang) + ahw * math.sin(ang),
          ey - ahl * math.sin(ang) - ahw * math.cos(ang))
    p3 = (ex - ahl * math.cos(ang) - ahw * math.sin(ang),
          ey - ahl * math.sin(ang) + ahw * math.cos(ang))
    draw_ctx.polygon([p1, p2, p3], fill=color)


# Arrow between icon positions (Finder coords 160 → 440 at y=250)
dashed_curve(
    draw,
    (230 * SS, 248 * SS),
    (372 * SS, 248 * SS),
    ARROW,
    width=2 * SS,
    dash_len=7 * SS,
    gap_len=6 * SS,
    curvature=-26 * SS,
)

# Footer
foot = "Hands-free scrolling with head tracking"
fb = draw.textbbox((0, 0), foot, font=sub_font)
fw = fb[2] - fb[0]
draw.text(((WS - fw) // 2, (H - 34) * SS), foot, font=sub_font, fill=MUTED)

# Downsample: @2x is W*2, @1x is W
at_2x = img.resize((W * 2, H * 2), Image.LANCZOS)
at_1x = img.resize((W, H), Image.LANCZOS)

out = os.path.dirname(os.path.abspath(__file__))
at_1x.save(os.path.join(out, "dmg-background.png"))
at_2x.save(os.path.join(out, "dmg-background@2x.png"))
print("Wrote dmg-background.png and dmg-background@2x.png (super-sampled)")

"""Generate menu bar and app icons that match the original head silhouette:
a clean, front-facing dome-shaped head (no neck, no shoulders).
"""
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024


def draw_head(size, color=(0, 0, 0, 255), scale=0.78):
    """Return RGBA head silhouette centered, sized to `scale` of the canvas."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Head proportions: dome top, slight taper toward jaw
    # Composite from overlapping ellipses to get a smooth egg/dome shape.
    cx = size / 2
    cy = size * 0.53

    head_w = size * scale * 0.62
    head_h = size * scale * 0.90

    # Main head ellipse (slightly taller than wide)
    d.ellipse(
        [cx - head_w / 2, cy - head_h / 2,
         cx + head_w / 2, cy + head_h / 2],
        fill=color,
    )

    # Slight widening near the jaw (bottom third) for natural silhouette
    jaw_w = head_w * 1.02
    jaw_h = head_h * 0.55
    jaw_cy = cy + head_h * 0.12
    d.ellipse(
        [cx - jaw_w / 2, jaw_cy - jaw_h / 2,
         cx + jaw_w / 2, jaw_cy + jaw_h / 2],
        fill=color,
    )

    return layer


# ── Menu bar icon: head on transparent bg (template rendering) ───────────────
menu_icon = draw_head(SIZE, scale=0.82)
menu_icon.save("MenuBarIcon.png")
print(f"Wrote MenuBarIcon.png ({SIZE}x{SIZE})")

# ── App icon: rounded-square off-white bg + head ─────────────────────────────
CORNER = int(SIZE * 0.22)

mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle(
    [0, 0, SIZE, SIZE], radius=CORNER, fill=255
)

# Soft cream-white gradient background
bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
gd = ImageDraw.Draw(bg)
for y in range(SIZE):
    t = y / SIZE
    r = int(252 - 6 * t)
    g = int(250 - 6 * t)
    b = int(245 - 8 * t)
    gd.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

app = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
app.paste(bg, (0, 0), mask)

# Head, slightly smaller so it sits nicely inside
head_layer = draw_head(SIZE, scale=0.62)
# Shift head up a touch so optical center matches
head_layer = head_layer.transform(
    head_layer.size, Image.AFFINE,
    (1, 0, 0, 0, 1, int(SIZE * 0.02)),  # move content down ~2%
)
clipped_head = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
clipped_head.paste(head_layer, (0, 0), mask)
app = Image.alpha_composite(app, clipped_head)

# Subtle inner shadow around the rounded square edge
shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
for i in range(22):
    a = int(28 * (1 - i / 22))
    sd.rounded_rectangle(
        [i, i, SIZE - i, SIZE - i],
        radius=CORNER - i,
        outline=(0, 0, 0, a),
        width=1,
    )
shadow = shadow.filter(ImageFilter.GaussianBlur(1.5))
shadow_clipped = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
shadow_clipped.paste(shadow, (0, 0), mask)
app = Image.alpha_composite(app, shadow_clipped)

app.save("AppIcon.png")
print(f"Wrote AppIcon.png ({SIZE}x{SIZE})")

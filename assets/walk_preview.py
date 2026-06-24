"""Montage the full-body Marcille sprites (s05..s21), normalized to the same
height and bottom-aligned, with index labels, so we can pick idle + walk cycle."""
from PIL import Image, ImageDraw
import os

SEG = r"C:\Users\tamin\desktop-pet\assets\marc_seg"
OUTDIR = r"C:\Users\tamin\desktop-pet\assets\frames"
TARGET_H = 150
idxs = list(range(5, 22))

cells = []
for n in idxs:
    p = os.path.join(SEG, f"s{n:02d}.png")
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    sc = TARGET_H / im.height
    im = im.resize((max(1, int(im.width * sc)), TARGET_H), Image.LANCZOS)
    cells.append((n, im))

cw = 130
per_row = 9
rows = (len(cells) + per_row - 1) // per_row
sheet = Image.new("RGBA", (per_row * cw, rows * (TARGET_H + 26) + 10), (40, 42, 54, 255))
d = ImageDraw.Draw(sheet)
for i, (n, im) in enumerate(cells):
    col, row = i % per_row, i // per_row
    x = col * cw + (cw - im.width) // 2
    y = row * (TARGET_H + 26) + 22
    sheet.alpha_composite(im, (x, y))
    d.text((col * cw + 4, row * (TARGET_H + 26) + 4), f"s{n:02d}", fill="#ffd166")
sheet.convert("RGB").save(os.path.join(OUTDIR, "preview_walk_pick.png"))
print("saved preview_walk_pick.png with", len(cells), "frames")

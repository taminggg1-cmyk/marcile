"""Manually crop the JPG portrait-key grid (2 rows x 8), key out the checker
per cell (flood-fill from borders), and preview the KEYED result on a dark
background so we can judge whether JPG quality is acceptable."""
from PIL import Image
from collections import deque
import os

SRC = r"C:\Users\tamin\Downloads\1b8d8b0d-1ae1-4273-bd52-772ea2c0f924.jpg"
OUT = r"C:\Users\tamin\desktop-pet\assets\marc2_seg"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert("RGBA")
TOL, GRAY = 30, 30


def is_bg(p):
    if max(p[0], p[1], p[2]) - min(p[0], p[1], p[2]) >= GRAY or p[0] < 150:
        return False
    return True


def flood(crop):
    cw, ch = crop.size
    cp = crop.load()
    seen = bytearray(cw * ch)
    dq = deque([(x, 0) for x in range(cw)] + [(x, ch - 1) for x in range(cw)] +
               [(0, y) for y in range(ch)] + [(cw - 1, y) for y in range(ch)])
    while dq:
        x, y = dq.popleft()
        if not (0 <= x < cw and 0 <= y < ch):
            continue
        i = y * cw + x
        if seen[i]:
            continue
        seen[i] = 1
        if is_bg(cp[x, y]):
            r, g, b, a = cp[x, y]
            cp[x, y] = (r, g, b, 0)
            dq.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
    return crop


bands = [(26, 148), (148, 272)]
ncol = 8
cw = 1024 / ncol
idx = 0
crops = []
for (y0, y1) in bands:
    for c in range(ncol):
        x0 = int(c * cw) + 2
        x1 = int((c + 1) * cw) - 2
        cell = flood(im.crop((x0, y0, x1, y1)).copy())
        bb = cell.getbbox()
        if not bb:
            continue
        cell = cell.crop(bb)
        if cell.width < 20 or cell.height < 20:
            continue
        cell.save(os.path.join(OUT, f"t{idx:02d}.png"))
        crops.append((idx, cell))
        idx += 1

# preview on dark bg, scaled up so fringe is visible
CELL = 190
per = 8
import math
nr = math.ceil(len(crops) / per)
sheet = Image.new("RGBA", (per * CELL, nr * CELL), (38, 40, 50, 255))
from PIL import ImageDraw
d = ImageDraw.Draw(sheet)
for k, (n, c) in enumerate(crops):
    sc = min((CELL - 26) / c.width, (CELL - 26) / c.height)
    c2 = c.resize((max(1, int(c.width * sc)), max(1, int(c.height * sc))), Image.NEAREST)
    ox = (k % per) * CELL + (CELL - c2.width) // 2
    oy = (k // per) * CELL + (CELL - c2.height) // 2
    sheet.alpha_composite(c2, (ox, oy))
    d.text(((k % per) * CELL + 4, (k // per) * CELL + 4), str(n), fill="#ffd166")
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_marc2_keyed.png"))
print("cropped", idx, "faces -> preview_marc2_keyed.png")

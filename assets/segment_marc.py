"""Segment the AI Marcille sprite sheet: detect the checker background,
auto-split into individual sprites, key out the checker (flood-fill from
each crop's border so interior whites like the collar are kept), and save
each sprite + a labeled contact sheet."""
from PIL import Image, ImageDraw, ImageFont
from collections import Counter, deque
import os

SRC = r"C:\Users\tamin\Downloads\Gemini_Generated_Image_hmpyznhmpyznhmpy.png"
OUT = r"C:\Users\tamin\desktop-pet\assets\marc_seg"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert("RGBA")
W, H = im.size
px = im.load()


def grayish(p):
    r, g, b = p[0], p[1], p[2]
    return max(r, g, b) - min(r, g, b) < 18


# find the two checker shades = two most common grayish colors
cnt = Counter()
for y in range(0, H, 4):
    for x in range(0, W, 4):
        p = px[x, y]
        if grayish(p):
            cnt[(p[0] // 8 * 8, p[1] // 8 * 8, p[2] // 8 * 8)] += 1
checker = [c for c, _ in cnt.most_common(3)]
print("checker shades:", checker)


def is_bg(p):
    if not grayish(p):
        return False
    for c in checker:
        if abs(p[0] - c[0]) <= 18 and abs(p[1] - c[1]) <= 18 and abs(p[2] - c[2]) <= 18:
            return True
    return False


# foreground mask
fg = bytearray(W * H)
for y in range(H):
    base = y * W
    for x in range(W):
        if not is_bg(px[x, y]):
            fg[base + x] = 1


def col_counts(x0, x1, y0, y1):
    return [sum(fg[y * W + x] for y in range(y0, y1)) for x in range(x0, x1)]

def row_counts(y0, y1, x0, x1):
    return [sum(fg[y * W + x] for x in range(x0, x1)) for y in range(y0, y1)]


def split(counts, start, gap=10, thr=2, minlen=20):
    """Return list of (a,b) spans where counts>thr, separated by >=gap of <=thr."""
    spans = []
    run_start = None
    gap_run = 0
    for i, c in enumerate(counts):
        if c > thr:
            if run_start is None:
                run_start = i
            gap_run = 0
        else:
            if run_start is not None:
                gap_run += 1
                if gap_run >= gap:
                    b = i - gap_run + 1
                    if b - run_start >= minlen:
                        spans.append((start + run_start, start + b))
                    run_start = None
                    gap_run = 0
    if run_start is not None and len(counts) - run_start >= minlen:
        spans.append((start + run_start, start + len(counts)))
    return spans


def flood_alpha(crop):
    cw, ch = crop.size
    cp = crop.load()
    seen = bytearray(cw * ch)
    dq = deque()
    for x in range(cw):
        for y in (0, ch - 1):
            dq.append((x, y))
    for y in range(ch):
        for x in (0, cw - 1):
            dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        if x < 0 or y < 0 or x >= cw or y >= ch:
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


# rows of the whole sheet
rc = row_counts(0, H, 0, W)
rows = split(rc, 0, gap=24, thr=4, minlen=60)
print("row bands:", rows)

records = []
idx = 0
for ri, (y0, y1) in enumerate(rows):
    cc = col_counts(0, W, y0, y1)
    cols = split(cc, 0, gap=14, thr=2, minlen=40)
    for ci, (x0, x1) in enumerate(cols):
        # tighten vertical to this sprite
        sub = row_counts(y0, y1, x0, x1)
        ys = split(sub, y0, gap=8, thr=1, minlen=30)
        ny0, ny1 = (ys[0][0], ys[-1][1]) if ys else (y0, y1)
        pad = 4
        box = (max(0, x0 - pad), max(0, ny0 - pad),
               min(W, x1 + pad), min(H, ny1 + pad))
        crop = flood_alpha(im.crop(box).copy())
        bb = crop.getbbox()
        if bb:
            crop = crop.crop(bb)
        crop.save(os.path.join(OUT, f"s{idx:02d}.png"))
        records.append((idx, ri, ci, crop.size))
        idx += 1

print("sprites:", idx)

# contact sheet with index labels
cell = 230
per_row = 8
import math
nrows = math.ceil(idx / per_row)
sheet = Image.new("RGBA", (per_row * cell, nrows * cell), (60, 60, 70, 255))
d = ImageDraw.Draw(sheet)
for n in range(idx):
    c = Image.open(os.path.join(OUT, f"s{n:02d}.png")).convert("RGBA")
    sc = min((cell - 30) / c.width, (cell - 30) / c.height)
    c2 = c.resize((max(1, int(c.width * sc)), max(1, int(c.height * sc))), Image.NEAREST)
    cx = (n % per_row) * cell + (cell - c2.width) // 2
    cy = (n // per_row) * cell + (cell - c2.height) // 2
    sheet.alpha_composite(c2, (cx, cy))
    d.text(((n % per_row) * cell + 4, (n // per_row) * cell + 4), str(n), fill="#ffd166")
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_marc_seg.png"))
print("saved preview_marc_seg.png")

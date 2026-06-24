"""Segment the 2nd (JPG) Marcille sheet into individual sprites, with extra
tolerance for JPG compression noise. Saves crops + a labeled contact sheet."""
from PIL import Image, ImageDraw
from collections import Counter, deque
import os, math

SRC = r"C:\Users\tamin\Downloads\1b8d8b0d-1ae1-4273-bd52-772ea2c0f924.jpg"
OUT = r"C:\Users\tamin\desktop-pet\assets\marc2_seg"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC).convert("RGBA")
W, H = im.size
px = im.load()

GRAY = 26      # how "neutral" a pixel must be to count as checker
TOL = 26       # distance to a checker shade


def grayish(p):
    return max(p[0], p[1], p[2]) - min(p[0], p[1], p[2]) < GRAY


cnt = Counter()
for y in range(0, H, 3):
    for x in range(0, W, 3):
        p = px[x, y]
        if grayish(p) and p[0] > 150:        # checker is light
            cnt[(p[0] // 8 * 8, p[1] // 8 * 8, p[2] // 8 * 8)] += 1
checker = [c for c, _ in cnt.most_common(4)]
print("checker:", checker)


def is_bg(p):
    if not grayish(p) or p[0] < 150:
        return False
    return any(abs(p[0]-c[0]) <= TOL and abs(p[1]-c[1]) <= TOL and abs(p[2]-c[2]) <= TOL
               for c in checker)


fg = bytearray(W * H)
for y in range(H):
    b = y * W
    row = [is_bg(px[x, y]) for x in range(W)]
    for x in range(W):
        if not row[x]:
            fg[b + x] = 1


def rc(y0, y1, x0, x1):
    return [sum(fg[y*W+x] for x in range(x0, x1)) for y in range(y0, y1)]

def cc(x0, x1, y0, y1):
    return [sum(fg[y*W+x] for y in range(y0, y1)) for x in range(x0, x1)]


def split(counts, start, gap, thr, minlen):
    spans, run, g = [], None, 0
    for i, c in enumerate(counts):
        if c > thr:
            if run is None:
                run = i
            g = 0
        elif run is not None:
            g += 1
            if g >= gap:
                if i - g + 1 - run >= minlen:
                    spans.append((start+run, start+i-g+1))
                run, g = None, 0
    if run is not None and len(counts)-run >= minlen:
        spans.append((start+run, start+len(counts)))
    return spans


def flood(crop):
    cw, ch = crop.size
    cp = crop.load()
    seen = bytearray(cw*ch)
    dq = deque([(x, 0) for x in range(cw)] + [(x, ch-1) for x in range(cw)] +
               [(0, y) for y in range(ch)] + [(cw-1, y) for y in range(ch)])
    while dq:
        x, y = dq.popleft()
        if x < 0 or y < 0 or x >= cw or y >= ch:
            continue
        i = y*cw+x
        if seen[i]:
            continue
        seen[i] = 1
        if is_bg(cp[x, y]):
            r, g, b, a = cp[x, y]
            cp[x, y] = (r, g, b, 0)
            dq.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
    return crop


rows = split(rc(0, H, 0, W), 0, gap=18, thr=6, minlen=40)
print("rows:", rows)
records = []
idx = 0
for (y0, y1) in rows:
    cols = split(cc(0, W, y0, y1), 0, gap=10, thr=2, minlen=28)
    for (x0, x1) in cols:
        sub = rc(y0, y1, x0, x1)
        ys = split(sub, y0, gap=6, thr=1, minlen=22)
        ny0, ny1 = (ys[0][0], ys[-1][1]) if ys else (y0, y1)
        box = (max(0, x0-3), max(0, ny0-3), min(W, x1+3), min(H, ny1+3))
        crop = flood(im.crop(box).copy())
        bb = crop.getbbox()
        if bb:
            crop = crop.crop(bb)
        if crop.width < 24 or crop.height < 24:
            continue
        crop.save(os.path.join(OUT, f"t{idx:02d}.png"))
        records.append(idx)
        idx += 1
print("sprites:", idx)

cell = 150
per = 10
nr = math.ceil(idx/per)
sheet = Image.new("RGBA", (per*cell, nr*cell), (55, 57, 68, 255))
d = ImageDraw.Draw(sheet)
for n in range(idx):
    c = Image.open(os.path.join(OUT, f"t{n:02d}.png")).convert("RGBA")
    sc = min((cell-22)/c.width, (cell-22)/c.height)
    c2 = c.resize((max(1, int(c.width*sc)), max(1, int(c.height*sc))), Image.NEAREST)
    ox = (n % per)*cell + (cell-c2.width)//2
    oy = (n//per)*cell + (cell-c2.height)//2
    sheet.alpha_composite(c2, (ox, oy))
    d.text(((n % per)*cell+3, (n//per)*cell+3), str(n), fill="#ffd166")
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_marc2_seg.png"))
print("saved preview_marc2_seg.png")

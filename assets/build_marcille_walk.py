"""Build full-body walk-mode frames for Marcille: a front idle + a side walk
cycle (+ run), normalized to the same height and bottom-aligned (feet on a
common baseline) so she walks without jittering. Faces LEFT by default."""
from PIL import Image, ImageDraw
import os

SEG = r"C:\Users\tamin\desktop-pet\assets\marc_seg"
OUT = r"C:\Users\tamin\desktop-pet\assets\frames\marcille_walk"
os.makedirs(OUT, exist_ok=True)

TARGET_H = 150
IDLE = "s08"                       # front standing
WALK = ["s17", "s18", "s19", "s20"]
RUN = ["s21"]


def load_scaled(seg):
    im = Image.open(os.path.join(SEG, f"{seg}.png")).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    sc = TARGET_H / im.height
    return im.resize((max(1, int(im.width * sc)), TARGET_H), Image.LANCZOS)


idle = load_scaled(IDLE)
walk = [load_scaled(s) for s in WALK]
run = [load_scaled(s) for s in RUN]
allf = [idle] + walk + run

CW = max(f.width for f in allf) + 18
CH = TARGET_H + 16
BASE = CH - 8                      # feet baseline


def place(im, name):
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ox = (CW - im.width) // 2
    oy = BASE - im.height
    canvas.alpha_composite(im, (ox, oy))
    canvas.save(os.path.join(OUT, name))
    return canvas


place(idle, "idle.png")
for i, f in enumerate(walk):
    place(f, f"walk_{i}.png")
for i, f in enumerate(run):
    place(f, f"run_{i}.png")

# preview
order = [("idle", idle)] + [(f"walk_{i}", w) for i, w in enumerate(walk)] + \
        [(f"run_{i}", r) for i, r in enumerate(run)]
pad = 8
sheet = Image.new("RGBA", (len(order) * (CW + pad) + pad, CH + 28), (40, 42, 54, 255))
d = ImageDraw.Draw(sheet)
for i, (nm, im) in enumerate(order):
    x = pad + i * (CW + pad)
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((CW - im.width) // 2, BASE - im.height))
    sheet.alpha_composite(canvas, (x, 24))
    d.text((x + 4, 6), nm, fill="#ffd166")
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_marcille_walk.png"))
print(f"built walk frames (canvas {CW}x{CH}) + preview_marcille_walk.png")

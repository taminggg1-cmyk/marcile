"""Recolor the cute Cat&Dog kitten from white/gray to a black cat,
keeping the big eyes and pink nose. Preview idle + walk."""
from PIL import Image
import glob, os, re

base = r"C:\Users\tamin\desktop-pet\assets\catndog\png\cat"
out = r"C:\Users\tamin\desktop-pet\assets\frames"


def load(prefix):
    fs = glob.glob(os.path.join(base, f"{prefix} (*).png"))
    fs.sort(key=lambda p: int(re.search(r"\((\d+)\)", p).group(1)))
    return [Image.open(f).convert("RGBA") for f in fs]


def is_eye(r, g, b):
    return b > 110 and b > r + 25 and b > g + 10

def is_nose(r, g, b):
    return r > 150 and r > g + 35 and r > b + 10


def to_black(im, eye_color=None):
    im = im.copy()
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 20:
                continue
            if is_eye(r, g, b):
                if eye_color:
                    px[x, y] = (*eye_color, a)
                continue
            if is_nose(r, g, b):
                continue
            lum = 0.3 * r + 0.59 * g + 0.11 * b
            v = int(16 + lum / 255 * 52)
            px[x, y] = (v, v, v + 5, a)
    return im


def strip(ims, row_y, sheet, recolor, eye=None):
    for i in range(min(8, len(ims))):
        im = recolor(ims[i], eye) if recolor else ims[i]
        sc = 90 / max(im.size)
        im2 = im.resize((int(im.width * sc), int(im.height * sc)), Image.NEAREST)
        sheet.alpha_composite(im2, (10 + i * 100, row_y))


idle = load("Idle")
walk = load("Walk")

sheet = Image.new("RGBA", (820, 340), (210, 210, 216, 255))
# row 0: black cat, blue eyes (idle)
strip(idle, 10, sheet, to_black, eye=None)
# row 1: black cat, blue eyes (walk)
strip(walk, 120, sheet, to_black, eye=None)
# row 2: black cat, yellow-green eyes (idle) - Jiji style
strip(idle, 230, sheet, to_black, eye=(210, 220, 90))
sheet.convert("RGB").save(os.path.join(out, "preview_black_kitten.png"))
print("saved preview_black_kitten.png "
      "(row1 idle blue-eye, row2 walk blue-eye, row3 idle yellow-eye)")

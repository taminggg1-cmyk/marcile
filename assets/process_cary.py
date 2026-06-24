"""Slice the carysaurus black-cat sheets into frames, trim to a common
bounding box (keeps the cat from jittering), upscale, and save. Preview too."""
from PIL import Image
import os

SRC = r"C:\Users\tamin\desktop-pet\assets\carysaurus\BlackCat_Free_Carysaurus"
OUT = r"C:\Users\tamin\desktop-pet\assets\frames\cary"
os.makedirs(OUT, exist_ok=True)
SCALE = 3
FS = 48


def slice_sheet(name, count):
    im = Image.open(os.path.join(SRC, name)).convert("RGBA")
    return [im.crop((i * FS, 0, (i + 1) * FS, FS)) for i in range(count)]


idle = slice_sheet("Black-Idle.png", 12)
run = slice_sheet("Black-Run.png", 6)
allf = idle + run

# common bbox across every frame
bb = None
for f in allf:
    b = f.getbbox()
    if b is None:
        continue
    bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]),
                               max(bb[2], b[2]), max(bb[3], b[3]))
# pad 1px
bb = (max(0, bb[0] - 1), max(0, bb[1] - 1), min(FS, bb[2] + 1), min(FS, bb[3] + 1))
print("common bbox", bb)


def finish(f):
    f = f.crop(bb)
    return f.resize((f.width * SCALE, f.height * SCALE), Image.NEAREST)


for i, f in enumerate(idle):
    finish(f).save(os.path.join(OUT, f"idle_{i}.png"))
for i, f in enumerate(run):
    finish(f).save(os.path.join(OUT, f"run_{i}.png"))

# preview
cw = (bb[2] - bb[0]) * SCALE
sheet = Image.new("RGBA", (cw * 12 + 20, (bb[3] - bb[1]) * SCALE * 2 + 30),
                  (210, 210, 216, 255))
for i, f in enumerate(idle):
    sheet.alpha_composite(finish(f), (10 + i * cw, 10))
for i, f in enumerate(run):
    sheet.alpha_composite(finish(f), (10 + i * cw, 20 + (bb[3] - bb[1]) * SCALE))
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_cary.png"))
print("frame size:", cw, "x", (bb[3] - bb[1]) * SCALE, "- saved preview_cary.png")

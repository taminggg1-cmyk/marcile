"""Preview the Cat&Dog (LPC) cat: idle + walk frames on a gray bg."""
from PIL import Image
import glob, os, re

base = r"C:\Users\tamin\desktop-pet\assets\catndog\png\cat"
out = r"C:\Users\tamin\desktop-pet\assets\frames"


def frames(prefix):
    fs = glob.glob(os.path.join(base, f"{prefix} (*).png"))
    fs.sort(key=lambda p: int(re.search(r"\((\d+)\)", p).group(1)))
    return [Image.open(f).convert("RGBA") for f in fs]


idle = frames("Idle")
walk = frames("Walk")
print("idle", len(idle), idle[0].size if idle else None,
      "walk", len(walk), walk[0].size if walk else None)

# trim to first 8 of each, scale to fit
def strip(ims, row_y, sheet):
    n = min(8, len(ims))
    for i in range(n):
        im = ims[i]
        sc = 90 / max(im.size)
        im2 = im.resize((int(im.width * sc), int(im.height * sc)), Image.NEAREST)
        sheet.alpha_composite(im2, (10 + i * 100, row_y))

sheet = Image.new("RGBA", (820, 230), (205, 205, 212, 255))
strip(idle, 10, sheet)
strip(walk, 120, sheet)
sheet.convert("RGB").save(os.path.join(out, "preview_catndog.png"))
print("saved preview_catndog.png  (top row = Idle, bottom = Walk)")

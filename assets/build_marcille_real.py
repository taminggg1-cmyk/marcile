"""Turn the segmented Marcille portraits into the 6 emotion frames marcille.py
needs, normalized so the HEAD is the same size & position in every frame
(so swapping emotions doesn't make her jump or resize)."""
from PIL import Image
import os

SEG = r"C:\Users\tamin\desktop-pet\assets\marc_seg"
OUT = r"C:\Users\tamin\desktop-pet\assets\frames\marcille"
os.makedirs(OUT, exist_ok=True)

# emotion -> source segmented sprite
MAP = {
    "normal":  "s00",   # neutral content bust
    "blink":   "s03",   # eyes closed
    "sleepy":  "s03",   # eyes closed
    "happy":   "s16",   # waving, big smile
    "panic":   "s15",   # worried / teary
    "casting": "s13",   # holding spellbook
}

TARGET_HEAD = 120          # head width (incl. ears) every frame is scaled to
CW, CH = 190, 210          # output canvas
HEAD_TOP_Y = 16            # where the top of the head sits


def head_metrics(im):
    """Width and center-x of the head, measured in the top 42% of content."""
    a = im.getchannel("A")
    w, h = im.size
    band = int(h * 0.42)
    left, right = w, 0
    px = a.load()
    for y in range(band):
        for x in range(w):
            if px[x, y] > 40:
                left = min(left, x)
                right = max(right, x)
    if right <= left:
        return w, w / 2
    return right - left, (left + right) / 2


def build(emotion, seg):
    im = Image.open(os.path.join(SEG, f"{seg}.png")).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    hw, hcx = head_metrics(im)
    scale = TARGET_HEAD / hw
    nw, nh = max(1, int(im.width * scale)), max(1, int(im.height * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    hcx *= scale

    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ox = int(CW / 2 - hcx)
    oy = HEAD_TOP_Y
    canvas.alpha_composite(im, (ox, oy))
    canvas.save(os.path.join(OUT, f"{emotion}.png"))
    return canvas


frames = {e: build(e, s) for e, s in MAP.items()}

# preview montage
order = ["normal", "blink", "happy", "panic", "casting", "sleepy"]
pad = 12
sheet = Image.new("RGBA", (len(order) * (CW + pad) + pad, CH + 40), (40, 42, 54, 255))
from PIL import ImageDraw
d = ImageDraw.Draw(sheet)
for i, e in enumerate(order):
    x = pad + i * (CW + pad)
    sheet.alpha_composite(frames[e], (x, 30))
    d.text((x + 4, 8), e, fill="#ffd166")
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_marcille_real.png"))
print("built 6 frames + preview_marcille_real.png  (canvas %dx%d)" % (CW, CH))

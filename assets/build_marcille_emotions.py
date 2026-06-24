"""Build Marcille's full emotion set, normalized so the head is the same size
& position in every frame. Crisp faces come from the clean PNG segments
(marc_seg); extra reaction faces come from the JPG segments (marc2_seg)."""
from PIL import Image, ImageDraw
import os

PNG_SEG = r"C:\Users\tamin\desktop-pet\assets\marc_seg"
JPG_SEG = r"C:\Users\tamin\desktop-pet\assets\marc2_seg"
OUT = r"C:\Users\tamin\desktop-pet\assets\frames\marcille"
os.makedirs(OUT, exist_ok=True)

# emotion -> (segment dir, file stem)
MAP = {
    "normal":      (PNG_SEG, "s00"),
    "blink":       (PNG_SEG, "s03"),
    "sleepy":      (PNG_SEG, "s03"),
    "happy":       (PNG_SEG, "s16"),
    "panic":       (PNG_SEG, "s15"),
    "casting":     (PNG_SEG, "s13"),
    "idea":        (PNG_SEG, "s14"),
    "surprised":   (PNG_SEG, "s02"),
    "sad":         (PNG_SEG, "s04"),
    "angry":       (JPG_SEG, "t06"),
    "crying":      (JPG_SEG, "t04"),
    "embarrassed": (JPG_SEG, "t13"),
    "laughing":    (JPG_SEG, "t12"),
}

TARGET_HEAD = 120
CW, CH = 190, 210
HEAD_TOP_Y = 16


def head_metrics(im):
    a = im.getchannel("A")
    w, h = im.size
    band = max(1, int(h * 0.42))
    px = a.load()
    left, right = w, 0
    for y in range(band):
        for x in range(w):
            if px[x, y] > 60:
                left = min(left, x)
                right = max(right, x)
    if right <= left:
        return w, w / 2
    return right - left, (left + right) / 2


def build(emotion, seg, stem):
    im = Image.open(os.path.join(seg, f"{stem}.png")).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    hw, hcx = head_metrics(im)
    scale = TARGET_HEAD / hw
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                   Image.LANCZOS)
    hcx *= scale
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    canvas.alpha_composite(im, (int(CW / 2 - hcx), HEAD_TOP_Y))
    canvas.save(os.path.join(OUT, f"{emotion}.png"))
    return canvas


order = ["normal", "blink", "happy", "laughing", "embarrassed", "idea",
         "surprised", "sad", "panic", "angry", "crying", "casting", "sleepy"]
frames = {e: build(e, *MAP[e]) for e in order}

pad = 8
cols = 7
rows = (len(order) + cols - 1) // cols
sheet = Image.new("RGBA", (cols * (CW + pad) + pad, rows * (CH + 26) + pad),
                  (40, 42, 54, 255))
d = ImageDraw.Draw(sheet)
for i, e in enumerate(order):
    col, row = i % cols, i // cols
    x = pad + col * (CW + pad)
    y = pad + row * (CH + 26) + 20
    sheet.alpha_composite(frames[e], (x, y))
    d.text((x + 4, y - 18), e, fill="#ffd166")
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_marcille_all.png"))
print("built", len(order), "emotions + preview_marcille_all.png")

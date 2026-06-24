"""Build Marcille's emotion frames from the user's hand-labeled portraits in
assets/emotion_src. Each source is a pixel-art bust on a flat background
(magenta for the tight face crops, light gray/white for the zoomed-out ones).
We key the background out with a border-connected flood (so interior
whites/reds/greens + eye highlights survive), erode the edge 1px to cut the
colored fringe, then normalize every frame so HER HEAD is the same size &
position. Sizing/positioning is measured from her body only (largest connected
blob) so floating decorations (sparkles, sweat drops, lightbulb, music notes)
don't throw off the scale -- that keeps the zoomed-out 'small' poses from
shrinking and floating high. Output overwrites assets/frames/marcille/."""
from PIL import Image, ImageDraw, ImageFilter
from collections import deque
import numpy as np
import os

SRC = os.path.join(os.path.dirname(__file__), "emotion_src")
OUT = r"C:\Users\tamin\desktop-pet\assets\frames\marcille"
os.makedirs(OUT, exist_ok=True)

# app emotion -> source file (no extension). All 21 of the user's portraits.
MAP = {
    "normal":      "normal",
    "blink":       "blinky_sleepy",
    "sleepy":      "blinky_sleepy",
    "happy":       "happy",
    "laughing":    "laughing",
    "embarrassed": "embarassed",
    "shy":         "embarress",
    "idea":        "idea",
    "aha":         "Aha",
    "surprised":   "surprised",
    "sad":         "sad",
    "gloomy":      "sad_(2)",
    "very_sad":    "very_sad",
    "pity":        "pity",
    "nervous":     "panic",
    "panic":       "very_panic",
    "angry":       "angry",
    "crying":      "crying",
    "casting":     "cast_a_spell",
    "thinking":    "thinking",
    "dizzy":       "dizzy",
    "clumsy":      "clumsy",
}

TARGET_HEAD = 116          # head width every frame is scaled to
CW, CH = 200, 240          # canvas size
HEAD_TOP_Y = 18            # y of the top of her head on the canvas
KEY_TOL = 84               # color distance from bg that still counts as background


def key_background(path):
    """Remove the flat background that's connected to the image border.

    The bg color is read from the border itself, so this handles both the
    magenta cells and the white casting cell. Only background-colored pixels
    REACHABLE from the edge are removed, so interior whites / eye highlights
    survive. Edge is eroded 1px to cut the colored halo fringe."""
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    h, w, _ = rgb.shape
    # background color = median of the 1px border ring
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, axis=0)
    # pixels close to bg color
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    similar = dist <= KEY_TOL
    # flood from every border pixel that's similar -> connected background mask
    is_bg = np.zeros((h, w), dtype=bool)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if similar[y, x] and not is_bg[y, x]:
                is_bg[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if similar[y, x] and not is_bg[y, x]:
                is_bg[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and similar[ny, nx] and not is_bg[ny, nx]:
                is_bg[ny, nx] = True
                dq.append((ny, nx))
    alpha = Image.fromarray(np.where(is_bg, 0, 255).astype(np.uint8), "L")
    # erode the edge 1px to cut the colored halo fringe ("cut an edge a bit")
    alpha = alpha.filter(ImageFilter.MinFilter(3))
    out = Image.open(path).convert("RGBA")
    out.putalpha(alpha)
    # zero the RGB of cleared pixels so no bg color bleeds through scaling
    a = np.asarray(alpha)
    arr = np.asarray(out).copy()
    arr[a == 0] = (0, 0, 0, 0)
    return Image.fromarray(arr, "RGBA")


def body_mask(im):
    """Largest connected opaque blob = Marcille's body. Ignores small floating
    decorations (sparkles / sweat / lightbulb / music notes / '!')."""
    a = np.asarray(im.getchannel("A")) > 60
    h, w = a.shape
    seen = np.zeros((h, w), dtype=bool)
    best = None
    best_n = 0
    for sy in range(h):
        for sx in range(w):
            if not a[sy, sx] or seen[sy, sx]:
                continue
            # BFS this component
            comp = []
            dq = deque([(sy, sx)])
            seen[sy, sx] = True
            while dq:
                y, x = dq.popleft()
                comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and a[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        dq.append((ny, nx))
            if len(comp) > best_n:
                best_n = len(comp)
                best = comp
    mask = np.zeros((h, w), dtype=bool)
    for y, x in best:
        mask[y, x] = True
    return mask


def head_metrics(im):
    """From her body only: head width, head center-x, and head top-y.
    Width is measured across the upper part of the head (top 22% of the body
    height), which is the skull -- narrower & more stable than the chin/hair."""
    mask = body_mask(im)
    ys, xs = np.where(mask)
    top = ys.min()
    bottom = ys.max()
    head_band = top + max(4, int((bottom - top) * 0.22))
    band = mask[top:head_band, :]
    bxs = np.where(band.any(axis=0))[0]
    if len(bxs) < 2:
        bxs = xs
    left, right = bxs.min(), bxs.max()
    return float(right - left), float((left + right) / 2), float(top)


def build(emotion, stem):
    im = key_background(os.path.join(SRC, f"{stem}.png"))
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    hw, hcx, htop = head_metrics(im)
    scale = TARGET_HEAD / hw
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                   Image.LANCZOS)
    hcx *= scale
    htop *= scale
    canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    # align her head: top of head -> HEAD_TOP_Y, head center -> canvas center
    canvas.alpha_composite(im, (int(CW / 2 - hcx), int(HEAD_TOP_Y - htop)))
    canvas.save(os.path.join(OUT, f"{emotion}.png"))
    return canvas


order = ["normal", "blink", "sleepy", "happy", "laughing", "embarrassed", "shy",
         "idea", "aha", "surprised", "sad", "gloomy", "very_sad", "pity",
         "nervous", "panic", "angry", "crying", "casting", "thinking", "dizzy",
         "clumsy"]
frames = {e: build(e, MAP[e]) for e in order}

# contact sheet so we can eyeball all of them at once
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
sheet.convert("RGB").save(os.path.join(os.path.dirname(OUT), "preview_marcille_new.png"))
print("built", len(order), "emotions ->", OUT)
print("preview ->", os.path.join(os.path.dirname(OUT), "preview_marcille_new.png"))

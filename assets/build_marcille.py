"""
Placeholder Marcille sprite generator.

Draws a simple chibi pixel mage-girl (blonde, long elf ears, navy robe) in a
handful of emotions, so marcille.py runs immediately. This is a TEMPORARY
stand-in -- drop a real Marcille reference image in assets and we'll replace
these frames with proper art.

Run:  python assets/build_marcille.py
Out:  assets/frames/marcille/{normal,blink,happy,panic,casting,sleepy}.png
"""

import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "frames", "marcille")
os.makedirs(OUT, exist_ok=True)

W, H = 48, 56
SCALE = 3

# palette
SKIN    = (244, 212, 182, 255)
SKIN_SH = (222, 182, 150, 255)
HAIR    = (236, 214, 150, 255)
HAIR_SH = (210, 184, 116, 255)
EYE     = (124, 94, 170, 255)
EYE_HI  = (250, 250, 255, 255)
WHITE   = (248, 248, 250, 255)
ROBE    = (52, 68, 108, 255)
ROBE_SH = (40, 54, 88, 255)
GOLD    = (214, 182, 92, 255)
MOUTH   = (176, 86, 90, 255)
LINE    = (70, 56, 44, 255)
SWEAT   = (120, 196, 232, 255)
STAR    = (255, 226, 138, 255)
BLUSH   = (240, 160, 150, 90)


def base(d):
    """Body, hair, ears, robe -- everything that doesn't change per emotion."""
    # long hair behind, falling down both sides
    d.ellipse((7, 3, 41, 41), fill=HAIR)
    d.rectangle((7, 20, 16, 52), fill=HAIR)
    d.rectangle((32, 20, 41, 52), fill=HAIR)
    d.ellipse((6, 44, 17, 54), fill=HAIR_SH)
    d.ellipse((31, 44, 42, 54), fill=HAIR_SH)

    # long elf ears poking out of the hair
    d.polygon([(13, 21), (1, 16), (14, 31)], fill=SKIN, outline=LINE)
    d.polygon([(35, 21), (47, 16), (34, 31)], fill=SKIN, outline=LINE)

    # face
    d.ellipse((12, 9, 36, 39), fill=SKIN)

    # bangs / side-swept fringe
    d.pieslice((11, 5, 37, 27), 180, 360, fill=HAIR)
    d.polygon([(24, 10), (19, 22), (29, 22)], fill=HAIR_SH)  # center part hint
    d.polygon([(12, 12), (12, 26), (18, 16)], fill=HAIR)
    d.polygon([(36, 12), (36, 26), (30, 16)], fill=HAIR)

    # robe / shoulders
    d.polygon([(15, 38), (33, 38), (40, 56), (8, 56)], fill=ROBE)
    d.polygon([(8, 56), (15, 38), (18, 38), (14, 56)], fill=ROBE_SH)
    # white collar + gold brooch
    d.polygon([(19, 37), (29, 37), (24, 45)], fill=WHITE)
    d.ellipse((22, 41, 26, 45), fill=GOLD)


def eyes_normal(d):
    for cx in (20, 28):
        d.ellipse((cx - 3, 21, cx + 3, 28), fill=WHITE, outline=LINE)
        d.ellipse((cx - 2, 22, cx + 2, 27), fill=EYE)
        d.ellipse((cx, 22, cx + 2, 24), fill=EYE_HI)


def eyes_blink(d):
    for cx in (20, 28):
        d.line((cx - 3, 24, cx + 3, 24), fill=LINE, width=1)


def eyes_happy(d):
    for cx in (20, 28):
        d.arc((cx - 3, 21, cx + 3, 28), 200, 340, fill=LINE, width=2)


def eyes_wide(d):
    for cx in (20, 28):
        d.ellipse((cx - 4, 20, cx + 4, 29), fill=WHITE, outline=LINE)
        d.ellipse((cx - 1, 23, cx + 1, 26), fill=EYE)


def eyes_focus(d):
    for cx in (20, 28):
        d.ellipse((cx - 3, 22, cx + 3, 27), fill=WHITE, outline=LINE)
        d.ellipse((cx - 2, 23, cx + 2, 26), fill=EYE)
        d.line((cx - 4, 21, cx + 4, 21), fill=LINE, width=1)  # focused brow


def eyes_sleep(d):
    for cx in (20, 28):
        d.arc((cx - 3, 22, cx + 3, 28), 20, 160, fill=LINE, width=2)


def brows_up(d):
    d.line((17, 18, 22, 17), fill=LINE, width=1)
    d.line((26, 17, 31, 18), fill=LINE, width=1)


def face(emotion, d):
    if emotion == "normal":
        eyes_normal(d)
        d.arc((21, 30, 27, 35), 20, 160, fill=MOUTH, width=1)
        d.ellipse((15, 28, 19, 31), fill=BLUSH)
        d.ellipse((29, 28, 33, 31), fill=BLUSH)
    elif emotion == "blink":
        eyes_blink(d)
        d.arc((21, 30, 27, 35), 20, 160, fill=MOUTH, width=1)
    elif emotion == "happy":
        eyes_happy(d)
        d.chord((20, 30, 28, 36), 0, 180, fill=MOUTH)
        d.ellipse((14, 28, 18, 31), fill=BLUSH)
        d.ellipse((30, 28, 34, 31), fill=BLUSH)
    elif emotion == "panic":
        eyes_wide(d)
        brows_up(d)
        d.ellipse((21, 30, 27, 37), fill=MOUTH)        # open wailing mouth
        d.ellipse((34, 14, 38, 20), fill=SWEAT)         # sweat drop
    elif emotion == "casting":
        eyes_focus(d)
        d.line((22, 33, 26, 33), fill=MOUTH, width=1)
        # little sparkle by her hand
        d.line((40, 42, 40, 48), fill=STAR, width=1)
        d.line((37, 45, 43, 45), fill=STAR, width=1)
        d.point((40, 45), fill=(255, 255, 255, 255))
    elif emotion == "sleepy":
        eyes_sleep(d)
        d.ellipse((23, 32, 25, 35), fill=MOUTH)
    else:
        eyes_normal(d)


EMOTIONS = ["normal", "blink", "happy", "panic", "casting", "sleepy"]


def build():
    for emo in EMOTIONS:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img, "RGBA")
        base(d)
        face(emo, d)
        big = img.resize((W * SCALE, H * SCALE), Image.NEAREST)
        big.save(os.path.join(OUT, f"{emo}.png"))
    print(f"Wrote {len(EMOTIONS)} placeholder frames to {OUT}")


if __name__ == "__main__":
    build()

"""Build a cute Jiji-style black cat as pixel art, in several emotions and
colors. Saves one PNG per (color, emotion) into assets/frames/, plus a preview
sheet so we can eyeball the expressions.

Run:  python build_cat.py
"""
from PIL import Image, ImageDraw
import os

OUT = r"C:\Users\tamin\desktop-pet\assets\frames"
os.makedirs(OUT, exist_ok=True)

W, H = 56, 64

COLORS = {
    "black":  dict(body=(26, 26, 32, 255),  edge=(46, 46, 58, 255),  ear=(150, 136, 196, 255), eye=(232, 226, 120, 255)),
    "gray":   dict(body=(96, 99, 110, 255), edge=(126, 130, 142, 255), ear=(232, 170, 190, 255), eye=(232, 226, 120, 255)),
    "orange": dict(body=(236, 150, 70, 255), edge=(250, 178, 104, 255), ear=(255, 200, 160, 255), eye=(120, 200, 150, 255)),
}

EYE_D = (120, 150, 60, 255)
PUP = (28, 28, 34, 255)
CLOSED = (216, 214, 226, 255)   # light eyelid line (visible on dark fur)
DROP = (120, 190, 240, 255)     # sweat/tear drop
NOSE = (150, 110, 175, 255)
WHIS = (160, 160, 172, 255)
BLUSH = (255, 140, 160, 200)
HEART = (255, 90, 130, 255)
WHITE = (255, 255, 255, 255)

EMOTIONS = ["normal", "blink", "happy", "love", "sleep", "alert", "sad"]


def heart(d, cx, cy, r, color):
    d.ellipse([cx - r, cy - r, cx, cy], fill=color)
    d.ellipse([cx, cy - r, cx + r, cy], fill=color)
    d.polygon([(cx - r, cy - r // 2), (cx + r, cy - r // 2), (cx, cy + r + 1)], fill=color)


def build(emotion, color):
    P = COLORS[color]
    body, edge, ear, eye = P["body"], P["edge"], P["ear"], P["eye"]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ears
    d.polygon([(13, 4), (9, 26), (26, 20)], fill=body)
    d.polygon([(43, 4), (47, 26), (30, 20)], fill=body)
    d.polygon([(15, 11), (13, 24), (23, 20)], fill=ear)
    d.polygon([(41, 11), (43, 24), (33, 20)], fill=ear)
    if emotion == "alert":   # ears perk up a touch
        d.polygon([(13, 1), (12, 8), (17, 6)], fill=body)
        d.polygon([(43, 1), (44, 8), (39, 6)], fill=body)

    # head + body + tail
    d.ellipse([(11, 16), (45, 40)], fill=body)
    d.polygon([(18, 33), (12, 55), (18, 61), (38, 61), (44, 55), (38, 33)], fill=body)
    d.ellipse([(12, 46), (44, 62)], fill=body)
    d.ellipse([(18, 55), (28, 62)], fill=body)
    d.ellipse([(28, 55), (38, 62)], fill=body)
    tail = [(40, 54), (48, 52), (52, 46), (52, 38), (49, 33)]
    d.line(tail, fill=body, width=6, joint="curve")
    d.ellipse([(46, 31), (52, 37)], fill=body)
    # subtle rim light on the head
    d.arc([(11, 16), (45, 40)], start=200, end=250, fill=edge, width=1)

    # whiskers (skip on alert for clean wide-eyed look)
    if emotion != "alert":
        d.line([(15, 30), (5, 28)], fill=WHIS, width=1)
        d.line([(15, 33), (5, 34)], fill=WHIS, width=1)
        d.line([(41, 30), (51, 28)], fill=WHIS, width=1)
        d.line([(41, 33), (51, 34)], fill=WHIS, width=1)

    # ---------- faces ----------
    def almond(left):
        if left:
            d.polygon([(15, 31), (20, 26), (25, 31), (20, 36)], fill=eye)
        else:
            d.polygon([(41, 31), (36, 26), (31, 31), (36, 36)], fill=eye)

    if emotion in ("normal", "blink") and emotion == "normal":
        for left in (True, False):
            almond(left)
        d.polygon([(20, 36), (25, 31), (22, 34)], fill=EYE_D)
        d.polygon([(36, 36), (31, 31), (34, 34)], fill=EYE_D)
        d.ellipse([(19, 28), (21, 35)], fill=PUP)
        d.ellipse([(35, 28), (37, 35)], fill=PUP)
        d.point((19, 29), fill=WHITE)
        d.point((35, 29), fill=WHITE)
        d.polygon([(27, 31), (29, 31), (28, 33)], fill=NOSE)

    elif emotion == "blink":
        d.line([(16, 31), (24, 32)], fill=CLOSED, width=2)
        d.line([(40, 31), (32, 32)], fill=CLOSED, width=2)
        d.polygon([(27, 31), (29, 31), (28, 33)], fill=NOSE)

    elif emotion == "happy":
        # ^ ^ closed happy eyes
        d.line([(16, 33), (20, 28), (24, 33)], fill=CLOSED, width=2, joint="curve")
        d.line([(32, 33), (36, 28), (40, 33)], fill=CLOSED, width=2, joint="curve")
        d.ellipse([(11, 33), (16, 37)], fill=BLUSH)
        d.ellipse([(40, 33), (45, 37)], fill=BLUSH)
        d.polygon([(27, 31), (29, 31), (28, 33)], fill=NOSE)
        d.arc([(25, 32), (31, 37)], start=20, end=160, fill=CLOSED, width=1)

    elif emotion == "love":
        heart(d, 20, 31, 4, HEART)
        heart(d, 36, 31, 4, HEART)
        d.point((19, 30), fill=WHITE)
        d.point((35, 30), fill=WHITE)
        d.ellipse([(11, 33), (16, 37)], fill=BLUSH)
        d.ellipse([(40, 33), (45, 37)], fill=BLUSH)
        d.polygon([(27, 32), (29, 32), (28, 34)], fill=NOSE)

    elif emotion == "sleep":
        d.line([(16, 30), (20, 33), (24, 30)], fill=CLOSED, width=2, joint="curve")
        d.line([(32, 30), (36, 33), (40, 30)], fill=CLOSED, width=2, joint="curve")
        d.polygon([(27, 31), (29, 31), (28, 33)], fill=NOSE)

    elif emotion == "alert":
        # big round wide eyes, dilated pupils
        d.ellipse([(14, 26), (24, 37)], fill=eye)
        d.ellipse([(32, 26), (42, 37)], fill=eye)
        d.ellipse([(16, 28), (22, 35)], fill=PUP)
        d.ellipse([(34, 28), (40, 35)], fill=PUP)
        d.ellipse([(17, 29), (19, 31)], fill=WHITE)
        d.ellipse([(35, 29), (37, 31)], fill=WHITE)
        d.polygon([(27, 31), (29, 31), (28, 33)], fill=NOSE)

    elif emotion == "sad":
        for left in (True, False):
            almond(left)
        d.ellipse([(19, 32), (21, 36)], fill=PUP)   # pupils low / looking down
        d.ellipse([(35, 32), (37, 36)], fill=PUP)
        d.point((19, 33), fill=WHITE)
        d.point((35, 33), fill=WHITE)
        # worried brows (inner ends raised)
        d.line([(15, 28), (24, 25)], fill=CLOSED, width=1)
        d.line([(41, 28), (32, 25)], fill=CLOSED, width=1)
        d.polygon([(27, 32), (29, 32), (28, 34)], fill=NOSE)
        d.arc([(25, 36), (31, 40)], start=200, end=340, fill=CLOSED, width=1)  # frown
        # tear drop
        d.ellipse([(13, 35), (16, 40)], fill=DROP)

    return img


def main():
    for color in COLORS:
        for em in EMOTIONS:
            build(em, color).save(os.path.join(OUT, f"{color}_{em}.png"))
    # preview sheet of black emotions
    scale = 4
    cols = EMOTIONS
    sheet = Image.new("RGBA", (W * scale * len(cols) + 20, H * scale + 20), (205, 205, 212, 255))
    for i, em in enumerate(cols):
        cat = build(em, "black").resize((W * scale, H * scale), Image.NEAREST)
        sheet.alpha_composite(cat, (10 + i * W * scale, 10))
    sheet.convert("RGB").save(os.path.join(OUT, "preview_emotions.png"))
    print("saved all sprites +", "preview_emotions.png")


if __name__ == "__main__":
    main()

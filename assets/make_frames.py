"""Load the walk GIF, chroma-key the purple background to transparency,
scale up with NEAREST (keeps it pixelated), and save a preview + frame PNGs."""
from PIL import Image, ImageSequence
import os

base = r"C:\Users\tamin\desktop-pet\assets\cat sprite"
out = r"C:\Users\tamin\desktop-pet\assets\frames"
os.makedirs(out, exist_ok=True)

SCALE = 3
TOL = 40  # chroma-key tolerance


def keyed(frame):
    f = frame.convert("RGBA")
    # background = top-left corner pixel
    bg = f.getpixel((0, 0))[:3]
    px = f.load()
    w, h = f.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if abs(r - bg[0]) <= TOL and abs(g - bg[1]) <= TOL and abs(b - bg[2]) <= TOL:
                px[x, y] = (0, 0, 0, 0)
    return f


def load(name):
    im = Image.open(os.path.join(base, name))
    frames = []
    for fr in ImageSequence.Iterator(im):
        k = keyed(fr)
        k = k.resize((k.width * SCALE, k.height * SCALE), Image.NEAREST)
        frames.append(k)
    return frames


walk = load("catwalkx4.gif")
print("walk frames:", len(walk), "scaled size:", walk[0].size)

# Save individual frames
for i, fr in enumerate(walk):
    fr.save(os.path.join(out, f"walk_{i}.png"))

# Build a horizontal contact sheet on a light bg so we can eyeball it
sheet = Image.new("RGBA", (walk[0].width * len(walk), walk[0].height), (230, 230, 235, 255))
for i, fr in enumerate(walk):
    sheet.alpha_composite(fr, (i * walk[0].width, 0))
sheet.convert("RGB").save(os.path.join(out, "preview_walk.png"))
print("saved preview_walk.png")

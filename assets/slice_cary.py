from PIL import Image
import os

base = r"C:\Users\tamin\desktop-pet\assets\carysaurus\BlackCat_Free_Carysaurus"
for name in ("Black-Idle.png", "Black-Run.png"):
    im = Image.open(os.path.join(base, name)).convert("RGBA")
    w, h = im.size
    # frames are square, side == height
    n = round(w / h)
    print(name, "sheet", (w, h), "-> frame", h, "x", h, "count", n,
          "exact_div", w % h == 0)

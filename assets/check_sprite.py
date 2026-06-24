from PIL import Image, ImageSequence
from collections import Counter
import os

base = r"C:\Users\tamin\desktop-pet\assets\cat sprite"

# ImageTk available?
try:
    from PIL import ImageTk  # noqa
    print("ImageTk: OK")
except Exception as e:
    print("ImageTk MISSING:", e)

for name in ("catwalkx4.gif", "catrunx4.gif"):
    im = Image.open(os.path.join(base, name))
    frames = [f.convert("RGBA") for f in ImageSequence.Iterator(im)]
    durs = [f.info.get("duration", "?") for f in ImageSequence.Iterator(Image.open(os.path.join(base, name)))]
    # sample opaque pixel colors of first frame
    f0 = frames[0]
    cnt = Counter()
    for px in f0.getdata():
        if px[3] > 100:
            cnt[px[:3]] += 1
    print(name, "size", im.size, "frames", len(frames), "durations", durs)
    print("   top colors:", cnt.most_common(4))

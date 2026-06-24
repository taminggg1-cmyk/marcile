from PIL import Image
import os

files = [
    r"C:\Users\tamin\Downloads\Gemini_Generated_Image_hmpyznhmpyznhmpy.png",
    r"C:\Users\tamin\Downloads\1b8d8b0d-1ae1-4273-bd52-772ea2c0f924.jpg",
]
for f in files:
    if not os.path.exists(f):
        print("MISSING", f)
        continue
    im = Image.open(f)
    print(os.path.basename(f), "size", im.size, "mode", im.mode)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        a = im.convert("RGBA").getchannel("A")
        lo, hi = a.getextrema()
        print("   alpha extrema:", (lo, hi),
              "-> real transparency" if lo == 0 else "-> opaque (checker baked in)")
    else:
        print("   no alpha channel (checker baked in)")

from PIL import Image
import os
base = r"C:\Users\tamin\desktop-pet\assets\cat sprite"
out = r"C:\Users\tamin\desktop-pet\assets\frames"
im = Image.open(os.path.join(base, "catspritesx4.gif")).convert("RGBA")
bg = im.getpixel((0, 0))[:3]
px = im.load()
for y in range(im.height):
    for x in range(im.width):
        r, g, b, a = px[x, y]
        if abs(r-bg[0]) <= 40 and abs(g-bg[1]) <= 40 and abs(b-bg[2]) <= 40:
            px[x, y] = (0, 0, 0, 0)
flat = Image.new("RGBA", im.size, (230, 230, 235, 255))
flat.alpha_composite(im)
flat.convert("RGB").save(os.path.join(out, "preview_sheet.png"))
print("sheet size", im.size)

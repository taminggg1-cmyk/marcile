from PIL import Image
import glob, os
base = r"C:\Users\tamin\desktop-pet\assets\tinykitten\TINY CAT SPRITE\01_Idle"
out = r"C:\Users\tamin\desktop-pet\assets\frames"
fs = sorted(glob.glob(os.path.join(base, "*.png")))[:8]
sheet = Image.new("RGBA", (820, 130), (210, 210, 216, 255))
for i, f in enumerate(fs):
    im = Image.open(f).convert("RGBA")
    bb = im.getbbox()
    im = im.crop(bb)
    sc = 100 / max(im.size)
    im = im.resize((int(im.width*sc), int(im.height*sc)), Image.NEAREST)
    sheet.alpha_composite(im, (10 + i*100, 15))
sheet.convert("RGB").save(os.path.join(out, "preview_tiny.png"))
print("saved")

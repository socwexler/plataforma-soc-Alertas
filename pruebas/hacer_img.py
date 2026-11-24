"""Logos y boletines ficticios para probar."""
import os
import random
from PIL import Image, ImageDraw
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archivos")
o = Image.new("RGBA", (1400, 700), (0, 0, 0, 0))
g = ImageDraw.Draw(o)
g.ellipse((300, 220, 520, 440), fill=(20, 70, 160, 255))
g.rectangle((560, 270, 1080, 390), fill=(20, 70, 160, 255))
o.save(d + "/logo_oscuro.png")
w = Image.new("RGBA", (900, 300), (0, 0, 0, 0))
ImageDraw.Draw(w).rectangle((100, 100, 800, 200), fill=(255, 255, 255, 255))
w.save(d + "/logo_blanco.png")
j = Image.new("RGB", (1200, 600), "white")
ImageDraw.Draw(j).ellipse((400, 150, 800, 450), fill=(200, 30, 40))
ex = j.getexif()
ex[0x010E] = "DATO PRIVADO"
j.save(d + "/logo.jpg", exif=ex, comment=b"DATO PRIVADO")
for n, (a, b) in {"boletin_v.png": (1400, 2400), "boletin_h.jpg": (2600, 1400)}.items():
    im = Image.new("RGB", (a, b), (12, 18, 40))
    g = ImageDraw.Draw(im)
    random.seed(n)
    for _ in range(40):
        x, y = random.randrange(a), random.randrange(b)
        g.ellipse((x, y, x + 200, y + 200), outline=(255, 0, 61), width=8)
    g.rectangle((40, 40, a - 40, 260), fill=(255, 0, 61))
    im.save(f"{d}/{n}")
Image.new("RGB", (20, 8), "red").save(d + "/mini.png")
Image.new("RGB", (400, 200), "white").save(d + "/blanco.png")
print(os.listdir(d))

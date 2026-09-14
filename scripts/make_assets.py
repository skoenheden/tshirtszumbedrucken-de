#!/usr/bin/env python3
"""Erzeugt logo-icon.png, logo.png, favicon.png/.ico, apple-touch-icon.png und og-image.png in assets/."""
import os
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
YELLOW, INK = "#ffe27a", "#111111"
SHIRT = [(30,15),(40,15),(45,22),(55,22),(60,15),(70,15),(90,32),(80,46),(72,41),(72,88),(28,88),(28,41),(20,46),(10,32)]

def font(size):
    for p in ["/System/Library/Fonts/Supplemental/Arial Black.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def icon(size):
    s = 4  # supersampling
    im = Image.new("RGBA", (size*s, size*s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size*s-1, size*s-1], radius=int(size*s*0.22), fill=YELLOW)
    k = size*s/100
    d.polygon([(x*k, y*k) for x, y in SHIRT], fill=INK)
    d.rectangle([40*k, 50*k, 60*k, 54*k], fill=YELLOW)   # "Druck"-Streifen
    d.rectangle([40*k, 58*k, 54*k, 62*k], fill=YELLOW)
    return im.resize((size, size), Image.LANCZOS)

icon(68).save(os.path.join(OUT, "logo-icon.png"))
icon(512).save(os.path.join(OUT, "logo.png"))
icon(64).save(os.path.join(OUT, "favicon.png"))
icon(180).convert("RGB").save(os.path.join(OUT, "apple-touch-icon.png"))
icon(48).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])

W, H = 1200, 630
og = Image.new("RGB", (W, H), "#fffdf5"); d = ImageDraw.Draw(og)
d.rectangle([0, 0, W, 16], fill=YELLOW)
d.rectangle([0, H-110, W, H], fill=INK)
og.paste(icon(150), (W-80-150, 90), icon(150))
d.text((80, 110), "T-SHIRTS", font=font(92), fill=INK)
d.text((80, 215), "ZUM BEDRUCKEN", font=font(72), fill=INK)
d.text((80, 330), "Rohlinge · Druckverfahren · Mengenpreise 2026", font=font(30), fill="#444444")
d.text((80, 395), "DTF · Siebdruck · Plotter · DTG", font=font(26), fill="#777777")
d.text((80, H-72), "tshirtszumbedrucken.de", font=font(28), fill=YELLOW)
t = "Rohlinge ab 1 Stück · Versand nach DE"
f = font(22); d.text((W-80-d.textlength(t, font=f), H-68), t, font=f, fill="#bbbbbb")
og.save(os.path.join(OUT, "og-image.png"), optimize=True)
print("Assets:", sorted(os.listdir(OUT)))

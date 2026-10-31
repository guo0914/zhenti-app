"""Generate PWA icons for the quiz app."""
from PIL import Image, ImageDraw
import os

base = os.path.dirname(os.path.abspath(__file__))
site = os.path.join(os.path.dirname(base), "site")

def make_icon(size, outpath):
    img = Image.new('RGBA', (size, size), (37, 99, 235, 255))
    draw = ImageDraw.Draw(img)
    margin = int(size * 0.22)
    stroke = max(3, size // 25)
    pts = [
        (margin, int(size * 0.52)),
        (int(size * 0.42), int(size * 0.75)),
        (int(size * 0.78), margin),
    ]
    draw.line([pts[0], pts[1]], fill=(255,255,255,255), width=stroke)
    draw.line([pts[1], pts[2]], fill=(255,255,255,255), width=stroke)
    img.save(outpath, 'PNG')
    print(f"Created {os.path.basename(outpath)} ({size}x{size})")

make_icon(192, os.path.join(site, 'icon-192.png'))
make_icon(512, os.path.join(site, 'icon-512.png'))
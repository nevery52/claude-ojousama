import sys
from PIL import Image, ImageChops
a = Image.open(sys.argv[1]).convert('RGB'); b = Image.open(sys.argv[2]).convert('RGB')
print('sizes', a.size, b.size)
b = b.resize(a.size)
d = ImageChops.difference(a, b).convert('L').point(lambda v: 255 if v > 40 else 0)
print('changed bbox', d.getbbox(), 'changed %', round(100 * sum(1 for p in d.getdata() if p) / (a.size[0] * a.size[1]), 2))
# 2x3 grid of changed share, to see where the differences are
W, H = a.size
for r in range(4):
    row = []
    for c in range(4):
        box = d.crop((c * W // 4, r * H // 4, (c + 1) * W // 4, (r + 1) * H // 4))
        n = sum(1 for p in box.getdata() if p); row.append(f"{100 * n / (box.size[0] * box.size[1]):5.1f}")
    print(' '.join(row))
# side-by-side + overlay preview
o = Image.blend(a, b, 0.5)
s = Image.new('RGB', (W * 3, H), 'white'); s.paste(a, (0, 0)); s.paste(b, (W, 0)); s.paste(o, (2 * W, 0))
s.thumbnail((1500, 500)); s.save(sys.argv[3])

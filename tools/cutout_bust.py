"""把半身立绘抠成桌面挂件用的透明 PNG。

和 cutout.py 的区别：半身图的底边正好切在她身上，米白色衬衫碰到底边，
从底边泛洪会把衣服当成背景挖掉。所以这里只从上、左、右三条边找背景，
底部和两侧靠下的地方再做一段渐隐，让她像从画面下方"浮"出来。

用法：cutout_bust.py 原图 输出 [原图 输出 ...]；原图写成 "闭眼.jpg=睁眼.jpg" 表示沿用睁眼图的轮廓。
"""
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from cutout import flood, hair_ratio, is_white, MIN_GAP, HAIR

WORK = 1024      # 在这个尺寸上算轮廓，太大了纯 Python 泛洪会很慢
OUT = 512        # 输出尺寸，和 art/cut/ 里的 Q 版一致
SCALE = 0.90     # 她占画布高度的比例
BOTTOM = 0.95    # 她的底边在画布里的位置，对应 ojousama.py 的 ART_BOTTOM
FADE = 0.16      # 底部渐隐的高度（占她自身高度）
SIDE = 0.07      # 两侧靠下渐隐的宽度


def outline(im):
    W, H = im.size
    px = im.load()
    seen = bytearray(W * H)
    bg = bytearray(W * H)
    edges = [(x, 0) for x in range(W)] + [(x, y) for y in range(H) for x in (0, W - 1)]
    for i in flood(px, W, H, seen, edges):
        bg[i] = 1

    near = Image.frombytes('L', (W, H), bytes(255 if v else 0 for v in bg))
    for _ in range(8):
        near = near.filter(ImageFilter.MaxFilter(9))
    near = near.tobytes()
    for y in range(H):
        for x in range(W):
            if seen[y * W + x] or not is_white(px[x, y]):
                continue
            region = flood(px, W, H, seen, [(x, y)])
            if len(region) >= MIN_GAP and any(near[i] for i in region) and hair_ratio(px, W, H, region) > HAIR:
                for i in region:
                    bg[i] = 1
    mask = Image.frombytes('L', (W, H), bytes(0 if v else 255 for v in bg))
    return mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))


def fade(size):
    """底部从上往下渐隐；两侧在下半身也往外渐隐，免得头发被画框切出一条直边。"""
    W, H = size
    m = Image.new('L', size, 255)
    d = ImageDraw.Draw(m)
    top = int(H * (1 - FADE))
    for y in range(top, H):
        d.line([(0, y), (W, y)], fill=int(255 * (H - y) / (H - top)))
    side = Image.new('L', size, 255)
    ds = ImageDraw.Draw(side)
    sw = int(W * SIDE)
    for x in range(sw):
        v = int(255 * x / sw)
        ds.line([(x, H // 2), (x, H)], fill=v)
        ds.line([(W - 1 - x, H // 2), (W - 1 - x, H)], fill=v)
    return ImageChops.multiply(m, side.filter(ImageFilter.GaussianBlur(H * 0.05)))


def cutout(src, dst, like=None):
    im = Image.open(src).convert('RGBA').resize((WORK, WORK), Image.LANCZOS)
    mask = outline(Image.open(like or src).convert('RGBA').resize((WORK, WORK), Image.LANCZOS))
    im.putalpha(ImageChops.multiply(mask, fade((WORK, WORK))))
    side = round(OUT * SCALE)
    im = im.resize((side, side), Image.LANCZOS)
    canvas = Image.new('RGBA', (OUT, OUT), (0, 0, 0, 0))
    canvas.paste(im, ((OUT - side) // 2, round(OUT * BOTTOM) - side), im)
    canvas.save(dst, optimize=True)


if __name__ == '__main__':
    for src, dst in zip(sys.argv[1::2], sys.argv[2::2]):
        src, _, like = src.partition('=')
        cutout(src, dst, like or None)
        print('ok', dst)

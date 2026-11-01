"""把立绘的白色背景抠成透明。

1. 从四周边缘开始泛洪，去掉和外面连通的白色；
2. 头发缝隙里被围住的白色小块：如果四周主要是橙色头发，也算背景。
衣服里的白色四周是描线和灰色阴影，不会被误删。
"""
import sys
from collections import deque
from PIL import Image, ImageFilter

THRESH = 232  # 亮度高于这个、且偏灰白的像素算"白"


def is_white(p):
    r, g, b = p[:3]
    return min(r, g, b) >= THRESH and max(r, g, b) - min(r, g, b) < 18


def is_hair(p):
    # 橙色系，包括头发的高光和描线旁边被柔化的浅橙
    r, g, b = p[:3]
    return r >= g >= b and r - b > 45


def flood(px, W, H, seen, starts):
    """从 starts 出发泛洪白色像素，返回这一块的所有像素下标。"""
    q, region = deque(starts), []
    while q:
        x, y = q.popleft()
        i = y * W + x
        if seen[i] or not is_white(px[x, y]):
            continue
        seen[i] = 1
        region.append(i)
        if x > 0: q.append((x - 1, y))
        if x < W - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < H - 1: q.append((x, y + 1))
    return region


def is_dark(p):
    return max(p[:3]) < 110


def hair_ratio(px, W, H, region):
    """这块白色外面一圈像素里（跳过深色描线），橙色头发占多少。"""
    inside = set(region)
    ring = set()
    for i in region:
        x, y = i % W, i // W
        for d in (3, 6):
            for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and ny * W + nx not in inside:
                    ring.add((nx, ny))
    ring = [p for p in ring if not is_dark(px[p])]
    return sum(is_hair(px[p]) for p in ring) / len(ring) if ring else 0


def cutout(src, dst, size=512):
    im = Image.open(src).convert('RGBA')
    W, H = im.size
    px = im.load()
    seen = bytearray(W * H)
    bg = bytearray(W * H)

    edges = [(x, y) for x in range(W) for y in (0, H - 1)] + [(x, y) for y in range(H) for x in (0, W - 1)]
    for i in flood(px, W, H, seen, edges):
        bg[i] = 1

    # 只处理靠近外轮廓的缝隙，眼睛里的高光在脸中间，离得远，不会被误删
    near = Image.frombytes('L', (W, H), bytes(255 if v else 0 for v in bg))
    for _ in range(5):
        near = near.filter(ImageFilter.MaxFilter(9))
    near = near.tobytes()

    for y in range(H):
        for x in range(W):
            if seen[y * W + x] or not is_white(px[x, y]):
                continue
            region = flood(px, W, H, seen, [(x, y)])
            if any(near[i] for i in region) and hair_ratio(px, W, H, region) > 0.5:
                for i in region:
                    bg[i] = 1

    mask = Image.frombytes('L', (W, H), bytes(0 if v else 255 for v in bg))
    # 收一像素边、再轻微羽化，去掉 JPG 留下的白边
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    im.putalpha(mask)
    im.thumbnail((size, size), Image.LANCZOS)
    im.save(dst, optimize=True)


if __name__ == '__main__':
    for src, dst in zip(sys.argv[1::2], sys.argv[2::2]):
        cutout(src, dst)
        print('ok', dst)

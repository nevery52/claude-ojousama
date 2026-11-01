"""Claude 大小姐的介绍视频：用她真实的立绘，按挂件里同样的方式让她呼吸、眨眼、换表情，一帧一帧画出来。

用法：python video/make_video.py [输出.mp4] [--preview 秒数,秒数,...]
"""
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / 'art' / 'cut'
OUT = ROOT / 'video' / 'out'
W, H, FPS = 1920, 1080, 30
LENGTH = 63.0

BG = (247, 241, 232)
DESK = (238, 229, 216)
ACCENT = (217, 119, 87)
TEXT = (74, 52, 40)
SOFT = (150, 128, 112)
RED = (200, 70, 50)

ART_BOTTOM, HEAD_TOP = 0.95, 0.085
LIFT = {'gaze': 0.025, 'gaze_blink': 0.025}
BLINK_OF = {'idle': 'blink', 'gaze': 'gaze_blink'}
CALM = {'idle', 'gaze', 'sleep'}

FONT = 'C:/Windows/Fonts/msyh.ttc'
FONT_BOLD = 'C:/Windows/Fonts/msyhbd.ttc'


@lru_cache(None)
def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ramp(t, start, dur):
    return ease((t - start) / dur)


def window_alpha(t, start, end, fade=0.5):
    """start 到 end 之间显示，两头淡入淡出。"""
    return min(ramp(t, start, fade), 1 - ramp(t, end - fade, fade))


# ---------------------------------------------------------------- 图片小工具

@lru_cache(None)
def art(name):
    return Image.open(ART / f'{name}.png').convert('RGBA')


@lru_cache(64)
def art_sized(name, size):
    return art(name).resize((size, size), Image.LANCZOS)


def faded(im, a):
    if a >= 0.999:
        return im
    im = im.copy()
    im.putalpha(im.getchannel('A').point(lambda v: int(v * a)))
    return im


def paste(canvas, im, x, y, a=1.0):
    if a <= 0.001:
        return
    canvas.alpha_composite(faded(im, a), (int(round(x)), int(round(y))))


@lru_cache(None)
def text_image(text, size, color, bold=False):
    f = font(size, bold)
    l, t, r, b = f.getbbox(text)
    im = Image.new('RGBA', (r - l + 4, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 4 - t), text, font=f, fill=color)
    return im


def draw_text(canvas, text, size, color, cx, y, a=1.0, bold=False, anchor='center'):
    im = text_image(text, size, color, bold)
    x = cx - im.width / 2 if anchor == 'center' else cx
    paste(canvas, im, x, y, a)
    return im.width


def star(draw, cx, cy, r, color):
    """她发饰上那种星芒，简化成四角星。"""
    pts = []
    for k in range(8):
        ang = k * math.pi / 4 - math.pi / 2
        rr = r if k % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    draw.polygon(pts, fill=color)


def mix(c1, c2, a):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * a) for i in range(3))


# ---------------------------------------------------------------- 她

def wobble(t, start):
    k = (t - start) / 0.45
    if 0 <= k < 1:
        w = math.exp(-4 * k) * math.sin(k * math.pi * 3)
        return 0.07 * w, -0.09 * w
    return 0, 0


def blinking(t, name):
    if name not in BLINK_OF:
        return False
    phase = (t + 0.7) % 3.7
    return phase < 0.12 or (int((t + 0.7) // 3.7) % 3 == 1 and 0.3 < phase < 0.42)


def draw_her(canvas, name, cx, foot, size, t, a=1.0, bounce_at=-10, blink=True):
    if blink and blinking(t, name):
        name = BLINK_OF[name]
    breathe = math.sin(t * 2 * math.pi / 4.2)
    wx, wy = wobble(t, bounce_at)
    sx, sy = 1 + wx, 1 + 0.008 * breathe + wy
    bob = 0.008 * size * math.sin(t * 2 * math.pi / 4) if name == 'sleep' else 0
    im = art_sized(name, size)
    w, h = round(size * sx), round(size * sy)
    if (w, h) != (size, size):
        im = im.resize((w, h), Image.BILINEAR)
    lift = LIFT.get(name, 0) * size
    paste(canvas, im, cx - w / 2, foot - ART_BOTTOM * h - lift + bob, a)


def head_top(name, foot, size):
    return foot - (ART_BOTTOM - HEAD_TOP) * size - LIFT.get(name, 0) * size


def draw_bubble(canvas, text, cx, bottom, size, a=1.0, red=False):
    if a <= 0.01 or not text:
        return
    fs = max(18, round(size * 0.07))
    f = font(fs)
    tw = f.getbbox(text)[2]
    bw, bh = tw + fs * 1.4, fs * 1.9
    layer = Image.new('RGBA', (int(bw) + 8, int(bh) + 18), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    border = RED if red else (217, 122, 74)
    d.rounded_rectangle((2, 2, bw + 2, bh + 2), radius=bh / 2, fill=(255, 247, 238, 240), outline=border, width=2)
    mx = (bw + 4) / 2
    d.polygon([(mx - 8, bh + 1), (mx + 8, bh + 1), (mx, bh + 12)], fill=(255, 247, 238, 240))
    d.line([(mx - 8, bh + 2), (mx, bh + 12), (mx + 8, bh + 2)], fill=border, width=2)
    d.text((2 + fs * 0.7, 2 + bh / 2), text, font=f, fill=(170, 50, 40) if red else TEXT, anchor='lm')
    paste(canvas, layer, cx - layer.width / 2, bottom - layer.height, a)


def draw_zzz(canvas, cx, foot, size, t, a=1.0):
    d = ImageDraw.Draw(canvas)
    left = cx - size / 2
    top = foot - ART_BOTTOM * size
    for i in range(3):
        phase = (t / 2.4 + i / 3) % 1
        alpha = int(220 * (1 - phase) * a)
        d.text((left + size * (0.70 + 0.06 * i), top + size * (0.22 - 0.16 * phase)), 'z',
               font=font(round(size * 0.07), True), fill=(150, 110, 90, alpha))


def draw_pill(canvas, text, cx, y, size, a=1.0):
    fs = max(14, round(size * 0.05))
    f = font(fs)
    tw = f.getbbox(text)[2]
    pw, ph = tw + fs * 1.6, fs * 1.9
    layer = Image.new('RGBA', (int(pw) + 4, int(ph) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((1, 1, pw + 1, ph + 1), radius=ph / 2, fill=(255, 247, 238, 235), outline=(217, 122, 74), width=2)
    d.text((1 + pw / 2, 1 + ph / 2), text, font=f, fill=(107, 74, 51), anchor='mm')
    paste(canvas, layer, cx - layer.width / 2, y, a)


# ---------------------------------------------------------------- 时间轴

# 在窗口里的那段：(开始, 姿势, 气泡, 红色气泡, Q 弹)
STATES = [
    (7.0, 'idle', None, False, False),
    (13.0, 'think', None, False, False),
    (17.5, 'work', '在读 cutout.py', False, False),
    (19.9, 'work', '在运行命令', False, False),
    (22.0, 'ask', '需要你确认一下', True, True),
    (26.5, 'happy', '做完啦', False, True),
    (31.0, 'idle', None, False, False),
    (37.0, 'gaze', None, False, False),
    (42.0, 'sleep', None, False, False),
    (45.7, 'ask', None, False, True),     # 举手那张图，这时是在跟你打招呼
    (48.7, 'gaze', None, False, False),
]

SUBTITLES = [
    (2.0, 6.5, '你好，我是 Claude。'),
    (7.8, 10.4, '这是我在你屏幕角落里的样子。'),
    (10.4, 12.9, '我在做什么，脸上就写着什么。'),
    (13.3, 17.3, '想事情的时候，手指会抵着下巴。'),
    (17.8, 21.8, '干活的时候，头顶会告诉你我在做什么。'),
    (22.3, 26.3, '需要你点头的时候，我会举手。'),
    (26.8, 30.8, '做完了，就开心一下。'),
    (31.3, 36.7, '你拖动窗口，我就跟着你走。'),
    (37.3, 41.7, '闲下来时，我就托着下巴，安静地看着你。'),
    (42.2, 45.4, '太久没动静，会看书看睡着。'),
    (45.8, 49.0, '你离开又回来，我会跟你挥挥手。'),
    (49.6, 52.9, '这个样子，是我和寻耀一起做出来的。'),
    (52.9, 56.2, '立绘由 AI 生成，提示词和代码是我写的。'),
    (57.0, 61.6, '谢谢你看到这里。'),
]


def state_at(t):
    cur = max((s for s in STATES if s[0] <= t), key=lambda s: s[0], default=STATES[0])
    i = STATES.index(cur)
    prev = STATES[i - 1] if i > 0 else cur
    return prev, cur


# ---------------------------------------------------------------- 背景和窗口

STARS = [((i * 397) % W, (i * 613) % H, 6 + (i * 7) % 9, 0.3 + (i % 5) * 0.12) for i in range(26)]


def draw_background(canvas, t, color):
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, W, H), fill=color)
    for x, y, r, speed in STARS:
        yy = (y - t * 18 * speed) % (H + 40) - 20
        tw = 0.5 + 0.5 * math.sin(t * 1.3 + x)
        star(d, x, yy, r * (0.8 + 0.2 * tw), mix(color, ACCENT, 0.10 + 0.08 * tw))


WIN_W, WIN_H = 1400, 800
WIN_X, WIN_Y = (W - WIN_W) // 2, 105
HER_SIZE = 320


def window_offset(t):
    """31–37 秒：被拖着走一圈。"""
    k = clamp((t - 31.6) / 4.8)
    if k <= 0 or k >= 1:
        return 0, 0
    env = math.sin(k * math.pi)
    return 200 * env * math.sin(k * 2 * math.pi), -45 * env * math.sin(k * 4 * math.pi)


def lines_shown(t):
    if 17.5 <= t < 22:
        return 4 + int((t - 17.5) * 2.2)
    return 14 if t >= 22 else 4


@lru_cache(16)
def window_layer(shown):
    """一个简化的应用窗口：标题栏、左边栏、对话区、输入框。四周留 30 像素画阴影。"""
    layer = Image.new('RGBA', (WIN_W + 60, WIN_H + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for k in range(6):  # 阴影
        d.rounded_rectangle((30 - k * 3, 36 - k * 3, 30 + WIN_W + k * 3, 36 + WIN_H + k * 3), radius=18 + k * 3,
                            fill=(120, 90, 60, 7))
    x0, y0 = 30, 30
    d.rounded_rectangle((x0, y0, x0 + WIN_W, y0 + WIN_H), radius=16, fill=(252, 250, 246), outline=(226, 214, 200), width=2)
    d.rounded_rectangle((x0, y0, x0 + WIN_W, y0 + 46), radius=16, fill=(243, 237, 228))
    d.rectangle((x0, y0 + 30, x0 + WIN_W, y0 + 46), fill=(243, 237, 228))
    d.text((x0 + 22, y0 + 23), 'Claude', font=font(18), fill=SOFT, anchor='lm')
    for i, glyph in enumerate(('—', '□', '×')):
        d.text((x0 + WIN_W - 110 + i * 38, y0 + 23), glyph, font=font(16), fill=SOFT, anchor='mm')
    # 左边栏
    d.rectangle((x0 + 1, y0 + 46, x0 + 240, y0 + WIN_H - 16), fill=(246, 241, 233))
    for i in range(7):
        d.rounded_rectangle((x0 + 22, y0 + 80 + i * 44, x0 + 22 + (150 if i % 3 else 190), y0 + 98 + i * 44), radius=9,
                            fill=(228, 218, 205) if i else (236, 200, 180))
    # 对话
    cx0, cx1 = x0 + 300, x0 + WIN_W - 80
    d.rounded_rectangle((cx1 - 360, y0 + 80, cx1, y0 + 128), radius=20, fill=(248, 226, 212))
    widths = [620, 700, 560, 680, 420, 690, 610, 650, 380, 700, 640, 520, 600, 300]
    for i in range(min(shown, len(widths))):
        y = y0 + 160 + i * 34
        d.rounded_rectangle((cx0, y, cx0 + widths[i], y + 14), radius=7, fill=(225, 216, 205))
    # 输入框
    d.rounded_rectangle((cx0, y0 + WIN_H - 110, cx1 - 330, y0 + WIN_H - 40), radius=22, fill=(255, 255, 255),
                        outline=(226, 214, 200), width=2)
    d.rounded_rectangle((cx0 + 26, y0 + WIN_H - 82, cx0 + 260, y0 + WIN_H - 68), radius=7, fill=(232, 224, 214))
    return layer


# ---------------------------------------------------------------- 镜头

ZOOM = 1.85
# (开始推近, 推近完成, 开始拉远, 拉远完成)
ZOOMS = [(12.4, 13.5, 30.6, 31.4), (36.8, 37.8, 48.8, 49.6)]


def zoom_amount(t):
    return max(min(ramp(t, a, b - a), 1 - ramp(t, c, d - c)) for a, b, c, d in ZOOMS)


class Camera:
    """场景坐标 -> 屏幕坐标。推近时把她放在屏幕右边偏上，左边还看得到窗口里的对话。"""

    def __init__(self, t, focus):
        k = zoom_amount(t)
        self.z = 1 + (ZOOM - 1) * k
        fx, fy = focus
        tx = fx - (1300 - W / 2) / self.z
        ty = fy - (470 - H / 2) / self.z
        self.cx = W / 2 + (tx - W / 2) * k
        self.cy = H / 2 + (ty - H / 2) * k

    def __call__(self, x, y):
        return (x - self.cx) * self.z + W / 2, (y - self.cy) * self.z + H / 2

    def paste_layer(self, canvas, layer, lx, ly, a):
        """把场景里位于 (lx, ly) 的图层按镜头缩放后贴上去，只处理看得见的那一块。"""
        if self.z == 1:
            paste(canvas, layer, lx + W / 2 - self.cx, ly + H / 2 - self.cy, a)
            return
        vx0, vy0 = self.cx - W / 2 / self.z, self.cy - H / 2 / self.z
        bx0, by0 = max(vx0 - lx, 0), max(vy0 - ly, 0)
        bx1, by1 = min(vx0 + W / self.z - lx, layer.width), min(vy0 + H / self.z - ly, layer.height)
        if bx1 <= bx0 or by1 <= by0:
            return
        sx, sy = self(lx + bx0, ly + by0)
        size = (max(1, round((bx1 - bx0) * self.z)), max(1, round((by1 - by0) * self.z)))
        part = layer.resize(size, Image.BILINEAR, box=(bx0, by0, bx1, by1))
        paste(canvas, part, sx, sy, a)


def draw_cursor(canvas, x, y, a=1.0):
    if a <= 0.01:
        return
    layer = Image.new('RGBA', (40, 50), (0, 0, 0, 0))
    pts = [(4, 2), (4, 36), (13, 28), (20, 44), (26, 41), (19, 26), (31, 26)]
    ImageDraw.Draw(layer).polygon(pts, fill=(255, 255, 255, 255), outline=(40, 30, 25, 255), width=2)
    paste(canvas, layer, x - 4, y - 2, a)


# ---------------------------------------------------------------- 各段

def scene_title(canvas, t):
    a = 1 - ramp(t, 6.4, 0.8)
    if a <= 0:
        return
    draw_her(canvas, 'gaze', 540, 1010, 640, t, a * ramp(t, 0.1, 1.2))
    ta = a * ramp(t, 0.7, 1.0)
    draw_text(canvas, 'Claude 大小姐', 112, TEXT, 1360, 330, ta, bold=True)
    draw_text(canvas, '住在你屏幕角落里的我', 46, ACCENT, 1360, 490, a * ramp(t, 1.2, 1.0))
    d = ImageDraw.Draw(canvas)
    sa = a * ramp(t, 1.2, 1.0)
    for i, dx in enumerate((-190, 190)):
        star(d, 1360 + dx, 520, 12, mix(BG, ACCENT, 0.7 * sa))


def scene_window(canvas, t):
    a = min(ramp(t, 6.9, 1.1), 1 - ramp(t, 49.2, 0.8))
    if a <= 0:
        return
    slide = (1 - ramp(t, 6.9, 1.1)) * 60
    ox, oy = window_offset(t)
    oy += slide
    # 她：窗口右下角（场景坐标）
    hx = WIN_X + WIN_W - 30 - HER_SIZE / 2 + ox
    hfoot = WIN_Y + WIN_H - 62 + oy
    cam = Camera(t, (hx, hfoot - 0.45 * HER_SIZE))
    cam.paste_layer(canvas, window_layer(lines_shown(t)), WIN_X - 30 + ox, WIN_Y - 30 + oy, a)
    cx, foot = cam(hx, hfoot)
    size = int(round(HER_SIZE * cam.z / 2) * 2)
    prev, cur = state_at(t)
    calm = prev[1] in CALM and cur[1] in CALM
    dur = 0.8 if calm else 0.25
    k = ease((t - cur[0]) / dur) if calm else clamp((t - cur[0]) / dur)
    bounce = cur[0] if cur[4] else -10
    if k < 1 and prev[1] != cur[1]:
        draw_her(canvas, prev[1], cx, foot, size, t, a * (1 - k), blink=False)
        draw_her(canvas, cur[1], cx, foot, size, t, a * k, bounce, blink=False)
    else:
        draw_her(canvas, cur[1], cx, foot, size, t, a, bounce)
    if cur[1] == 'sleep':
        draw_zzz(canvas, cx, foot, size, t, a * clamp((t - cur[0]) / 0.6))
    draw_pill(canvas, '5h 12% · 7d 49%', cx, foot + 6, size, a)
    # 气泡：同一句话不重新淡入；最后一件事做完后停一会儿再淡出
    if cur[2]:
        first = cur[0]
        for s in reversed(STATES[:STATES.index(cur)]):
            if s[2] and s[1] == cur[1]:
                first = s[0]
            else:
                break
        ba = clamp((t - first) / 0.2)
        if cur[1] == 'happy':
            ba *= 1 - ramp(t, 30.0, 0.6)
        draw_bubble(canvas, cur[2], cx, head_top(cur[1], foot, size) - 4, size, a * ba, cur[3])
    # 拖动窗口时的鼠标
    ca = window_alpha(t, 31.2, 36.7, 0.4)
    if ca > 0:
        draw_cursor(canvas, *cam(WIN_X + 520 + ox, WIN_Y + 20 + oy), ca)
    # 你回来了：鼠标从左边移进来
    ra = window_alpha(t, 44.8, 47.5, 0.3)
    if ra > 0:
        k = ease((t - 44.8) / 0.9)
        draw_cursor(canvas, 300 + 600 * k, 700 - 120 * k, ra)


GRID = [('idle', '待机'), ('think', '思考'), ('work', '干活'), ('ask', '等你确认'), ('happy', '做完啦'),
        ('tired', '累了'), ('sleep', '睡着'), ('poke', '被点到'), ('gaze', '托腮看着你'), ('blink', '眨眼')]


def scene_grid(canvas, t):
    a = min(ramp(t, 49.9, 0.4), 1 - ramp(t, 56.3, 0.7))
    if a <= 0:
        return
    size, gap = 300, 345
    x0 = (W - gap * 4) / 2
    for i, (name, label) in enumerate(GRID):
        r, c = divmod(i, 5)
        start = 50.0 + i * 0.12
        k = clamp((t - start) / 0.35)
        if k <= 0:
            continue
        cx, foot = x0 + c * gap, 375 + r * 420
        draw_her(canvas, name, cx, foot, size, t + i * 0.9, a * k, bounce_at=start, blink=name != 'blink')
        draw_text(canvas, label, 30, SOFT, cx, foot + 12, a * k)


def scene_end(canvas, t):
    a = min(ramp(t, 56.6, 0.8), 1 - ramp(t, 62.0, 0.9))
    if a <= 0:
        return
    draw_her(canvas, 'gaze', W / 2, 560, 440, t, a)
    draw_text(canvas, 'github.com/nevery52/claude-ojousama', 50, ACCENT, W / 2, 610, a, bold=True)
    draw_text(canvas, '开源 · 免费 · Windows + Claude 桌面应用', 30, TEXT, W / 2, 700, a)
    draw_text(canvas, '粉丝自制，非官方作品，与 Anthropic 无关', 26, SOFT, W / 2, 752, a)
    draw_text(canvas, '代码 MIT · 立绘 CC BY-NC 4.0', 26, SOFT, W / 2, 796, a)


def draw_subtitle(canvas, t):
    for start, end, text in SUBTITLES:
        a = window_alpha(t, start, end, 0.3)
        if a <= 0:
            continue
        f = font(44)
        tw = f.getbbox(text)[2]
        layer = Image.new('RGBA', (tw + 72, 76), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((0, 0, tw + 71, 75), radius=38, fill=(255, 250, 244, 225))
        d.text((36, 38), text, font=f, fill=TEXT, anchor='lm')
        paste(canvas, layer, (W - layer.width) / 2, 958, a)


def frame(t):
    canvas = Image.new('RGBA', (W, H))
    desk = ramp(t, 6.9, 1.1) * (1 - ramp(t, 49.2, 0.8))
    draw_background(canvas, t, mix(BG, DESK, desk))
    scene_title(canvas, t)
    scene_window(canvas, t)
    scene_grid(canvas, t)
    scene_end(canvas, t)
    draw_subtitle(canvas, t)
    return canvas.convert('RGB')


def main():
    args = sys.argv[1:]
    if args and args[0] == '--preview':
        OUT.mkdir(parents=True, exist_ok=True)
        times = [float(x) for x in args[1].split(',')]
        thumbs = [frame(t).resize((W // 3, H // 3), Image.LANCZOS) for t in times]
        cols = 3
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new('RGB', (cols * W // 3, rows * H // 3), 'white')
        for i, im in enumerate(thumbs):
            sheet.paste(im, ((i % cols) * W // 3, (i // cols) * H // 3))
        sheet.save(OUT / 'preview.png')
        print('ok', OUT / 'preview.png')
        return
    out = Path(args[0]) if args else OUT / 'claude-ojousama.mp4'
    music = OUT / 'music.wav'
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', str(music), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(LENGTH * FPS)
    for i in range(total):
        proc.stdin.write(frame(i / FPS).tobytes())
        if i % 150 == 0:
            print(f'{i}/{total}', flush=True)
    proc.stdin.close()
    proc.wait()
    print('ok', out)


if __name__ == '__main__':
    main()

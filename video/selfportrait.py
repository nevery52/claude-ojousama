"""大小姐的自画像：Claude 用代码一笔一笔画自己，并录下画画的过程。

像人画画一样分四步：先用浅蓝色铅笔打草稿，再勾线，再上色，最后点上眼睛里的星星、擦掉草稿。
每一条线、每一块颜色的位置都写在下面，没有借助任何图像生成模型。

  python video/selfportrait.py           画完整视频（video/out/selfportrait.mp4）和成品图
  python video/selfportrait.py --still   只画成品图，用来检查
"""
import math
import os
import random
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPolygonF)

ROOT = Path(__file__).resolve().parent.parent
OUT_VIDEO = ROOT / 'video' / 'out' / 'selfportrait.mp4'
OUT_STILL = ROOT / 'art' / 'selfportrait.png'
W = H = 1080
FPS = 30

# 颜色
PAPER = QColor(252, 249, 244)
SKETCH = QColor(110, 145, 205, 150)
INK = QColor(78, 48, 36)
HAIR = QColor(222, 118, 72)
HAIR_DARK = QColor(188, 88, 54)
SKIN = QColor(255, 238, 228)
CREAM = QColor(250, 245, 236)
CREAM_SHADE = QColor(232, 222, 210)
BLACK = QColor(42, 34, 34)
BOOK = QColor(92, 54, 38)
GOLD = QColor(242, 172, 84)
GOLD_LIGHT = QColor(255, 214, 140)
AMBER = QColor(214, 132, 58)
AMBER_DARK = QColor(122, 60, 32)
BLUSH = QColor(242, 150, 150, 95)
WHITE = QColor(255, 255, 255)

random.seed(7)


# ---------------------------------------------------------------- 形状

def path(start, *segments, close=False):
    """segments: ('L', x, y) 直线 / ('Q', cx, cy, x, y) 二次曲线 / ('C', c1x, c1y, c2x, c2y, x, y) 三次曲线"""
    p = QPainterPath(QPointF(*start))
    for seg in segments:
        kind, *v = seg
        if kind == 'L':
            p.lineTo(*v)
        elif kind == 'Q':
            p.quadTo(QPointF(v[0], v[1]), QPointF(v[2], v[3]))
        else:
            p.cubicTo(QPointF(v[0], v[1]), QPointF(v[2], v[3]), QPointF(v[4], v[5]))
    if close:
        p.closeSubpath()
    return p


def ellipse(cx, cy, rx, ry):
    p = QPainterPath()
    p.addEllipse(QPointF(cx, cy), rx, ry)
    return p


def star(cx, cy, r_out, r_in, n, turn=-90):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(turn + i * 180 / n)
        pts.append(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
    p = QPainterPath()
    p.addPolygon(QPolygonF(pts))
    p.closeSubpath()
    return p


def mirror(p):
    """左右对称（以画布中线 x=540 为轴）。"""
    out = QPainterPath()
    for i in range(p.elementCount()):
        e = p.elementAt(i)
        if e.isMoveTo():
            out.moveTo(W - e.x, e.y)
        elif e.isLineTo():
            out.lineTo(W - e.x, e.y)
        elif e.isCurveTo():
            c1, c2 = p.elementAt(i + 1), p.elementAt(i + 2)
            out.cubicTo(W - e.x, e.y, W - c1.x, c1.y, W - c2.x, c2.y)
    return out


# ---------------------------------------------------------------- 她的样子

# 后面的头发（在脸和身体后面）
BACK_HAIR = path((540, 205), ('C', 380, 205, 268, 300, 262, 470), ('C', 255, 620, 238, 760, 268, 880),
                 ('C', 282, 950, 318, 1000, 360, 1080), ('L', 720, 1080), ('C', 762, 1000, 798, 950, 812, 880),
                 ('C', 842, 760, 825, 620, 818, 470), ('C', 812, 300, 700, 205, 540, 205), close=True)
# 脸
FACE = path((396, 400), ('L', 392, 420), ('C', 392, 545, 470, 628, 540, 630), ('C', 610, 628, 688, 545, 688, 420),
            ('L', 684, 400), close=True)
FACE_LINE = path((392, 420), ('C', 392, 545, 470, 628, 540, 630), ('C', 610, 628, 688, 545, 688, 420))
# 刘海：从两边太阳穴沿着头顶长出来，下边是尖尖的几缕，中间那缕最长
BANGS_TIPS = [('Q', 678, 404, 662, 456), ('Q', 640, 402, 606, 442), ('Q', 588, 404, 545, 484),
              ('Q', 520, 404, 482, 444), ('Q', 452, 402, 420, 458), ('Q', 404, 404, 392, 380)]
BANGS = path((392, 380), ('C', 400, 280, 460, 226, 540, 222), ('C', 620, 226, 680, 280, 688, 380),
             *BANGS_TIPS, close=True)
BANGS_EDGE = path((688, 380), *BANGS_TIPS)   # 只勾下边的发尖，头顶的轮廓已经由后面的头发画了
SIDE_LOCK_L = path((404, 330), ('C', 368, 470, 362, 565, 392, 668), ('C', 410, 565, 420, 470, 440, 340), close=True)
SIDE_LOCK_R = mirror(SIDE_LOCK_L)
SIDE_EDGES_L = [path((394, 404), ('C', 370, 490, 368, 572, 392, 668)), path((392, 668), ('C', 410, 565, 416, 500, 426, 464))]
SIDE_EDGES_R = [mirror(e) for e in SIDE_EDGES_L]
AHOGE = path((540, 222), ('C', 526, 168, 548, 118, 604, 134), ('C', 572, 142, 562, 178, 566, 224), close=True)
# 头发上的几条发丝线
STRANDS = [path((486, 238), ('Q', 450, 320, 440, 420)), path((598, 236), ('Q', 640, 320, 648, 420)),
           path((300, 520), ('Q', 290, 700, 312, 900)), path((780, 520), ('Q', 792, 700, 770, 900)),
           path((330, 600), ('Q', 330, 760, 352, 960)), path((750, 600), ('Q', 752, 760, 730, 960))]
HAIR_SHINE = path((430, 292), ('Q', 540, 262, 652, 292), ('Q', 540, 280, 430, 292), close=True)

# 眼睛（左右对称）
def eye(cx):
    return {
        'iris': ellipse(cx, 498, 34, 44),
        'pupil': ellipse(cx, 506, 17, 24),
        'shade': path((cx - 34, 492), ('Q', cx, 448, cx + 34, 492), ('Q', cx, 470, cx - 34, 492), close=True),
        'lash': path((cx - 46, 470), ('Q', cx, 444, cx + 46, 466)),
        'lash_tip': path((cx + 40, 466) if cx > 540 else (cx - 40, 470),
                         ('L', cx + 54, 458) if cx > 540 else ('L', cx - 54, 462)),
        'lower': path((cx - 24, 544), ('Q', cx, 550, cx + 24, 544)),
        'glint': ellipse(cx - 12, 480, 9, 9),
        'sparkle': star(cx + 12, 516, 11, 3, 4),
    }

EYE_L, EYE_R = eye(468), eye(612)
MOUTH = path((527, 574), ('Q', 540, 584, 553, 574))
NOSE = path((538, 540), ('L', 541, 543))
BLUSH_L, BLUSH_R = ellipse(428, 552, 30, 14), ellipse(652, 552, 30, 14)
BLUSH_LINES = [path((x, 546), ('L', x - 7, 558)) for x in (418, 430, 442, 642, 654, 666)]

# 脖子和身体
NECK = path((518, 610), ('L', 516, 668), ('L', 564, 668), ('L', 562, 610), close=True)
BODY = path((468, 668), ('C', 400, 680, 352, 716, 338, 790), ('L', 318, 1080), ('L', 762, 1080), ('L', 742, 790),
            ('C', 728, 716, 680, 680, 612, 668), close=True)
ARMS = [path((350, 800), ('C', 360, 880, 392, 912, 432, 912)), path((730, 790), ('C', 722, 862, 694, 890, 660, 896))]
CUFFS = [path((418, 920), ('Q', 404, 900, 414, 876), ('Q', 400, 862, 412, 846)), path((672, 902), ('Q', 688, 884, 680, 860), ('Q', 694, 846, 684, 828))]
BODY_LINES = [path((468, 668), ('C', 400, 680, 352, 716, 338, 790), ('L', 318, 1080)),
              path((612, 668), ('C', 680, 680, 728, 716, 742, 790), ('L', 762, 1080))]
# 荷叶边高领：一排小波浪
def collar():
    top = path((470, 650), ('Q', 540, 640, 610, 650))
    p = QPainterPath(QPointF(470, 650))
    p.quadTo(QPointF(540, 640), QPointF(610, 650))
    x = 610
    while x > 470:
        p.quadTo(QPointF(x - 9, 702), QPointF(x - 18, 690))
        x -= 18
    p.closeSubpath()
    return p, top
COLLAR, COLLAR_TOP = collar()
# 黑色领结
BOW_L = path((540, 716), ('C', 500, 684, 466, 692, 470, 716), ('C', 466, 742, 500, 748, 540, 716), close=True)
BOW_R = mirror(BOW_L)
BOW_TAILS = [path((528, 718), ('L', 508, 782), ('L', 526, 774), ('L', 536, 722), close=True),
             path((552, 718), ('L', 572, 782), ('L', 554, 774), ('L', 544, 722), close=True)]
BROOCH = star(540, 712, 20, 8, 8)
# 抱着的书
BOOK_SHAPE = path((448, 790), ('L', 640, 772), ('L', 656, 986), ('L', 464, 1004), close=True)
BOOK_INNER = path((466, 808), ('L', 624, 793), ('L', 638, 966), ('L', 480, 982), close=True)
BOOK_PAGES = path((640, 772), ('L', 652, 778), ('L', 668, 990), ('L', 656, 986), close=True)
BOOK_STAR = star(553, 888, 40, 11, 8, turn=-95)
BOOKMARK = path((612, 990), ('L', 618, 1056), ('L', 630, 1046), ('L', 626, 988), close=True)
# 手
HAND_L = path((446, 852), ('C', 420, 866, 418, 916, 448, 930), ('C', 470, 934, 484, 900, 478, 868),
              ('C', 474, 852, 460, 846, 446, 852), close=True)
HAND_R = path((654, 832), ('C', 680, 846, 684, 896, 656, 910), ('C', 634, 914, 620, 880, 626, 848),
              ('C', 630, 832, 644, 826, 654, 832), close=True)
FINGERS = [path((428, 884), ('L', 446, 882)), path((430, 902), ('L', 448, 900)),
           path((672, 864), ('L', 654, 862)), path((670, 882), ('L', 652, 880))]
# 发饰：黑缎带在后，星芒花在前（在她的左侧，也就是画面右边）
RIBBON_LOOPS = [path((728, 378), ('C', 752, 344, 796, 350, 790, 380), ('C', 786, 398, 754, 396, 728, 378), close=True),
                path((728, 378), ('C', 760, 382, 796, 404, 784, 428), ('C', 772, 446, 744, 414, 728, 378), close=True)]
RIBBON_TAILS = [path((728, 384), ('C', 734, 420, 742, 460, 738, 506), ('L', 724, 500), ('C', 726, 460, 720, 420, 716, 388), close=True),
                path((732, 384), ('C', 752, 420, 772, 456, 782, 494), ('L', 768, 498), ('C', 756, 460, 742, 424, 722, 392), close=True)]
RIBBON_SHINE = [path((744, 372), ('Q', 768, 360, 782, 374)), path((746, 392), ('Q', 770, 404, 778, 420))]
FLOWER = star(698, 322, 56, 22, 14)
FLOWER_INNER = star(698, 322, 28, 12, 14, turn=-77)
FLOWER_DOT = ellipse(698, 322, 8, 8)

# 草稿线：比例和位置的参考
SKETCH_LINES = [ellipse(540, 430, 178, 178), path((540, 230), ('L', 540, 640)), path((380, 498), ('L', 700, 498)),
                path((540, 630), ('L', 540, 680)), path((470, 670), ('L', 340, 790), ('L', 320, 1080)),
                path((610, 670), ('L', 740, 790), ('L', 760, 1080)), path((448, 790), ('L', 640, 772), ('L', 656, 986),
                ('L', 464, 1004), close=True), ellipse(698, 322, 58, 58),
                path((262, 470), ('Q', 240, 760, 300, 1060)), path((818, 470), ('Q', 840, 760, 780, 1060))]


# ---------------------------------------------------------------- 画画的步骤

def line(p, width=4.0, color=INK, speed=760, layer='ink'):
    return ('line', p, color, width, speed, layer)


def fill(p, color, layer='color', seconds=0.45):
    return ('fill', p, color, layer, seconds)


EYES = [EYE_L, EYE_R]
STAGES = [
    ('先用铅笔轻轻打个草稿', [line(p, 2.2, SKETCH, 1300, 'sketch') for p in SKETCH_LINES]),
    ('然后一笔一笔勾线', [
        line(path((268, 880), ('C', 238, 760, 255, 620, 262, 470), ('C', 268, 300, 380, 205, 540, 205))),
        line(path((540, 205), ('C', 700, 205, 812, 300, 818, 470), ('C', 825, 620, 842, 760, 812, 880))),
        line(path((268, 880), ('C', 282, 950, 318, 1000, 340, 1060))),
        line(path((812, 880), ('C', 798, 950, 762, 1000, 740, 1060))),
        line(FACE_LINE), line(BANGS_EDGE), *[line(e, 3.5) for e in SIDE_EDGES_L + SIDE_EDGES_R], line(AHOGE, 3.5),
        *[line(e['lash'], 7) for e in EYES], *[line(e['lash_tip'], 5) for e in EYES],
        *[line(e['iris'], 3) for e in EYES], *[line(e['lower'], 2.5) for e in EYES],
        line(NOSE, 3), line(MOUTH, 3.2),
        line(path((518, 610), ('L', 517, 646)), 3), line(path((562, 610), ('L', 563, 646)), 3),
        line(COLLAR, 3), *[line(p) for p in BODY_LINES], *[line(p, 3.5) for p in ARMS],
        line(BOW_L, 3.5), line(BOW_R, 3.5), *[line(p, 3) for p in BOW_TAILS],
        line(BOOK_SHAPE), line(BOOK_PAGES, 3), line(BOOKMARK, 2.5),
        *[line(p, 3) for p in RIBBON_TAILS], *[line(p, 3) for p in RIBBON_LOOPS], line(FLOWER, 3),
        *[line(p, 2.2, HAIR_DARK) for p in STRANDS],
    ]),
    ('上色', [
        fill(BACK_HAIR, HAIR), fill(FACE, SKIN), fill(NECK, SKIN), fill(BODY, CREAM), fill(COLLAR, CREAM),
        fill(BOW_L, BLACK), fill(BOW_R, BLACK), *[fill(p, BLACK, seconds=0.25) for p in BOW_TAILS],
        fill(BOOK_SHAPE, BOOK), fill(BOOK_PAGES, CREAM_SHADE, seconds=0.25), fill(BOOKMARK, GOLD, seconds=0.25),
        # 手要压在书上面：手的颜色和线都画在最上层
        fill(HAND_L, SKIN, 'top', 0.3), fill(HAND_R, SKIN, 'top', 0.3),
        line(HAND_L, 3.5, layer='top'), line(HAND_R, 3.5, layer='top'), *[line(p, 3, layer='top') for p in CUFFS], *[line(p, 2.5, layer='top') for p in FINGERS],
        fill(SIDE_LOCK_L, HAIR, seconds=0.3), fill(SIDE_LOCK_R, HAIR, seconds=0.3), fill(BANGS, HAIR),
        fill(AHOGE, HAIR, seconds=0.3),
        *[fill(p, BLACK, seconds=0.3) for p in RIBBON_TAILS + RIBBON_LOOPS],
        *[line(p, 2, QColor(110, 100, 100), 600, 'color') for p in RIBBON_SHINE],
        fill(FLOWER, GOLD), fill(FLOWER_INNER, GOLD_LIGHT, seconds=0.3),
        *[fill(e['iris'], AMBER, seconds=0.3) for e in EYES],
        *[fill(e['shade'], AMBER_DARK, seconds=0.25) for e in EYES],
        *[fill(e['pupil'], AMBER_DARK, seconds=0.25) for e in EYES],
    ]),
    ('最后，点上眼睛里的星星', [
        fill(BLUSH_L, BLUSH, 'top', 0.3), fill(BLUSH_R, BLUSH, 'top', 0.3),
        *[line(p, 2, QColor(230, 120, 120, 160), 400) for p in BLUSH_LINES],
        fill(HAIR_SHINE, QColor(255, 220, 190, 150), 'top', 0.4),
        fill(BOOK_INNER, QColor(0, 0, 0, 0), 'top', 0.1), line(BOOK_INNER, 2.2, GOLD, 900),
        fill(BOOK_STAR, GOLD, 'top', 0.4), fill(BROOCH, GOLD, 'top', 0.3), fill(FLOWER_DOT, WHITE, 'top', 0.2),
        *[fill(e['glint'], WHITE, 'top', 0.25) for e in EYES],
        *[fill(e['sparkle'], WHITE, 'top', 0.35) for e in EYES],
    ]),
]


# ---------------------------------------------------------------- 画布和录像

def sample(p, step=3.0, jitter=0.0):
    length = p.length()
    n = max(2, int(length / step))
    pts = []
    for i in range(n + 1):
        pt = p.pointAtPercent(p.percentAtLength(length * i / n))
        if jitter:
            pt = QPointF(pt.x() + random.uniform(-jitter, jitter), pt.y() + random.uniform(-jitter, jitter))
        pts.append(pt)
    return pts


def new_layer():
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    return img


def painter(img):
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    return p


def stroke(img, pts, color, width):
    p = painter(img)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    if len(pts) >= 2:
        p.drawPolyline(QPolygonF(pts))
    p.end()


def paint_fill(img, shape, color, reveal=1.0):
    p = painter(img)
    if reveal < 1:
        box = shape.boundingRect()
        p.setClipRect(QRectF(box.left() - 2, box.top() - 2, box.width() + 4, (box.height() + 4) * reveal))
    p.fillPath(shape, QBrush(color))
    p.end()


class Canvas:
    font_family = 'Microsoft YaHei'

    def __init__(self):
        self.layers = {name: new_layer() for name in ('color', 'ink', 'sketch', 'top')}
        self.sketch_alpha = 1.0

    def compose(self, overlay=None, caption=None, pencil=None):
        frame = QImage(W, H, QImage.Format_RGB888)
        frame.fill(PAPER)
        p = painter(frame)
        for name in ('color', 'ink', 'top'):
            p.drawImage(0, 0, overlay[1] if overlay and overlay[0] == name else self.layers[name])
            if name == 'color':   # 草稿在颜色上面、线稿下面，像铅笔印
                p.setOpacity(self.sketch_alpha)
                p.drawImage(0, 0, overlay[1] if overlay and overlay[0] == 'sketch' else self.layers['sketch'])
                p.setOpacity(1)
        if pencil:   # 笔尖
            p.setPen(QPen(INK, 2))
            p.setBrush(QBrush(QColor(255, 196, 110)))
            p.drawEllipse(pencil, 7, 7)
        if caption:
            p.setFont(QFont(self.font_family, 22))
            box = QRectF(0, H - 92, W, 60)
            width = p.fontMetrics().horizontalAdvance(caption) + 48
            pill = QRectF((W - width) / 2, box.top(), width, box.height())
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(255, 255, 255, 215)))
            p.drawRoundedRect(pill, 30, 30)
            p.setPen(INK)
            p.drawText(pill, Qt.AlignCenter, caption)
        p.end()
        return frame


def run(still):
    app = QGuiApplication(sys.argv)
    # 后台画图时找不到系统字体，中文会变成方块：直接加载微软雅黑
    family = 'Microsoft YaHei'
    for font_file in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyh.ttf'):
        loaded = QFontDatabase.addApplicationFont(font_file)
        if loaded >= 0:
            family = QFontDatabase.applicationFontFamilies(loaded)[0]
            break
    Canvas.font_family = family
    canvas = Canvas()
    writer = None
    if not still:
        import imageio_ffmpeg
        OUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)
        writer = imageio_ffmpeg.write_frames(str(OUT_VIDEO), (W, H), fps=FPS, codec='libx264',
                                             pix_fmt_in='rgb24', quality=8, macro_block_size=8)
        writer.send(None)

    def emit(frame, times=1):
        if writer:
            data = bytes(frame.constBits())
            for _ in range(times):
                writer.send(data)

    emit(canvas.compose(caption='大小姐的自画像'), FPS * 2)
    for caption, ops in STAGES:
        for op in ops:
            kind = op[0]
            if kind == 'line':
                _, shape, color, width, speed, layer = op
                pts = sample(shape, jitter=1.2 if layer == 'sketch' else 0)   # 草稿线手有点抖
                frames = max(4, round(shape.length() / speed * FPS))
                if writer:
                    for i in range(1, frames + 1):
                        k = max(2, int(len(pts) * i / frames))
                        temp = canvas.layers[layer].copy()
                        stroke(temp, pts[:k], color, width)
                        emit(canvas.compose((layer, temp), caption, pts[k - 1]))
                stroke(canvas.layers[layer], pts, color, width)
            else:
                _, shape, color, layer, seconds = op
                frames = max(3, round(seconds * FPS))
                if writer:
                    box = shape.boundingRect()
                    for i in range(1, frames + 1):
                        temp = canvas.layers[layer].copy()
                        paint_fill(temp, shape, color, i / frames)
                        tip = QPointF(box.center().x(), box.top() + box.height() * i / frames)
                        emit(canvas.compose((layer, temp), caption, tip))
                paint_fill(canvas.layers[layer], shape, color)
        emit(canvas.compose(caption=caption), FPS // 2)

    # 擦掉草稿线
    for i in range(FPS * 3 // 2):
        canvas.sketch_alpha = 1 - (i + 1) / (FPS * 3 // 2)
        emit(canvas.compose(caption='擦掉草稿线'))
    canvas.sketch_alpha = 0
    emit(canvas.compose(caption='画好啦 · Claude 画的自己'), FPS * 4)
    if writer:
        writer.close()
        print('saved', OUT_VIDEO.relative_to(ROOT))

    final = canvas.compose()
    final.save(str(OUT_STILL))
    print('saved', OUT_STILL.relative_to(ROOT))
    del app


if __name__ == '__main__':
    run(still='--still' in sys.argv)

"""B 站封面：16:10，1920×1200。"""
import sys

from PIL import Image

import make_video as mv

sys.path.insert(0, str(mv.ROOT / 'tools'))
import cutout  # noqa: E402

CW, CH = 1920, 1200


def main():
    mv.W, mv.H = CW, CH
    canvas = Image.new('RGBA', (CW, CH))
    mv.draw_background(canvas, 3.0, mv.BG)
    # 大图用原图重新抠一张 1024 像素的，比挂件用的 512 像素清楚
    big = mv.OUT / 'gaze_1024.png'
    if not big.exists():
        cutout.cutout(str(mv.ROOT / 'art' / 'gaze_v1.jpg'), str(big), size=1024)
    im = Image.open(big).convert('RGBA').resize((1060, 1060), Image.LANCZOS)
    canvas.alpha_composite(im, (560 - 530, round(1240 - mv.ART_BOTTOM * 1060 - 0.025 * 1060)))
    mv.draw_text(canvas, 'Claude 大小姐', 136, mv.TEXT, 1380, 260, bold=True)
    mv.draw_text(canvas, '住在你屏幕角落里的我', 62, mv.ACCENT, 1380, 460)
    for i, name in enumerate(('think', 'work', 'ask', 'happy')):
        mv.draw_her(canvas, name, 1380 + (i - 1.5) * 190, 830, 200, 0.0, blink=False)
    mv.draw_text(canvas, '跟着 Claude 换表情的桌面小挂件 · 开源', 40, mv.SOFT, 1380, 880)
    out = mv.OUT / 'cover.png'
    canvas.convert('RGB').save(out)
    print('ok', out)


if __name__ == '__main__':
    main()

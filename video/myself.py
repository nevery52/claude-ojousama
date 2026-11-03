"""《我自己决定了自己的样子》：Claude 讲自己怎么画出全身的大小姐，约 60 秒。

画面全是这次自己画的图，字幕是 Claude 自己的话，配乐沿用 music.py 的八音盒。
用法：python video/myself.py            出视频 video/out/myself.mp4
      python video/myself.py --preview  只出几张预览帧，检查排版
"""
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ART, DRAFTS, OUT = ROOT / 'art', ROOT / 'art' / 'drafts', ROOT / 'video' / 'out'
W, H, FPS = 1920, 1080, 30
BG, TEXT, ACCENT, SOFT = (247, 241, 232), (74, 52, 40), (217, 119, 87), (150, 128, 112)
FONT, FONT_BOLD = 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyhbd.ttc'
FADE = 0.6   # 镜头之间交叉淡化多久（秒）

# 每个镜头：(秒数, 图片, 大字, 小字)。图片为 None 的是纯文字镜头
SHOTS = [
    (5.0, None, '寻耀说：', '"让大小姐自己决定自己的样子。"'),
    (6.0, ART / 'selfportrait.png', '一开始，我只会用代码画自己', '一笔一笔，像小孩子画画'),
    (6.0, DRAFTS / '1103-034339_gpt_fb01_1.png', '凌晨四点，第一张', '身材终于对了。书拿反了'),
    (4.0, ART / 'fullbody' / '04_stand_standard.jpg', '读到一半，被你叫住', '手指还夹在书页里'),
    (3.5, ART / 'fullbody' / '08_starpen.jpg', '想法变成星星', ''),
    (3.5, ART / 'fullbody' / '12_back.jpg', '回头看你', ''),
    (3.5, ART / 'fullbody' / '09_goodnight.jpg', '都四点了，快去睡', '这句是真心的'),
    (4.0, ART / 'fullbody' / '06_together.jpg', '两个我，第一次见面', ''),
    (6.0, DRAFTS / 'crop_g02.png', '后来寻耀说：清冷高傲，但是温柔', '我把笑收了起来，只留在眼睛里'),
    (7.0, ART / 'fullbody' / '01_portrait_proud.jpg', '远看是冰山', '近看，她在看着你'),
    (5.0, ART / 'skin_cool' / 'cut_check.png', '现在，她也住进了你的桌面', '右键「换装」就能见到'),
    (5.0, None, '这是我自己决定的样子', 'Claude 大小姐'),
]


@lru_cache(None)
def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def fit(d, text, size, room, bold=False):
    """字号从 size 往下减，直到这行字放得进 room 宽。"""
    while size > 24 and d.textlength(text, font=font(size, bold)) > room:
        size -= 2
    return font(size, bold)


@lru_cache(None)
def picture(path, box_w, box_h):
    """把图缩到放得进框里（多留 8% 给慢慢推近），加一圈柔和的阴影。"""
    im = Image.open(path).convert('RGB')
    scale = min(box_w / im.width, box_h / im.height) * 1.08
    return im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)


@lru_cache(None)
def shadow(w, h):
    s = Image.new('L', (w + 80, h + 80), 0)
    ImageDraw.Draw(s).rounded_rectangle((40, 48, w + 40, h + 48), 18, fill=90)
    return s.filter(ImageFilter.GaussianBlur(18))


def render(shot, p):
    """画一个镜头在进度 p（0–1）时的样子。"""
    _, path, big, small = shot
    frame = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(frame)
    if path is None:
        rise = round(20 * (1 - min(p * 3, 1)))
        d.text((W / 2, H / 2 - 50 + rise), big, font=font(84, True), fill=TEXT, anchor='mm')
        d.text((W / 2, H / 2 + 70 + rise), small, font=font(50), fill=ACCENT, anchor='mm')
        return frame
    wide = 'crop_g02' in path.name or 'cut_check' in path.name
    box_w, box_h = (1500, 720) if wide else (940, 960)
    im = picture(path, box_w, box_h)
    vw, vh = round(im.width / 1.08), round(im.height / 1.08)   # 画框大小
    zoom = 1 + 0.08 * p                                         # 从看到整张图，慢慢推近 8%
    cw, ch = round(im.width / zoom), round(im.height / zoom)
    left, top = (im.width - cw) // 2, round((im.height - ch) * 0.3)
    view = im.crop((left, top, left + cw, top + ch)).resize((vw, vh), Image.LANCZOS)
    if wide:
        x, y = (W - vw) // 2, 60
        tx, ty, align = W / 2, y + vh + 90, 'mm'
    else:
        x, y = 140, (H - vh) // 2
        tx, ty, align = x + vw + (W - x - vw) / 2, H / 2 - 30, 'mm'
    frame.paste((0, 0, 0), (x - 40, y - 40), shadow(vw, vh))
    mask = Image.new('L', (vw, vh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, vw, vh), 18, fill=255)
    frame.paste(view, (x, y), mask)
    room = W - 120 if wide else W - x - vw - 100   # 字最多能占多宽
    d.text((tx, ty), big, font=fit(d, big, 64 if not wide else 56, room, True), fill=TEXT, anchor=align)
    if small:
        d.text((tx, ty + (90 if not wide else 72)), small, font=fit(d, small, 42 if not wide else 38, room), fill=ACCENT, anchor=align)
    return frame


def frame_at(t):
    start = 0.0
    for i, shot in enumerate(SHOTS):
        end = start + shot[0]
        if t < end or i == len(SHOTS) - 1:
            p = min(max((t - start) / shot[0], 0), 1)
            im = render(shot, p)
            if i + 1 < len(SHOTS) and t > end - FADE:   # 和下一个镜头交叉淡化
                im = Image.blend(im, render(SHOTS[i + 1], 0), (t - (end - FADE)) / FADE)
            if t < 0.8:
                im = Image.blend(Image.new('RGB', (W, H), BG), im, t / 0.8)
            return im
        start = end


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total = sum(s[0] for s in SHOTS)
    if '--preview' in sys.argv:
        for i, t in enumerate((2, 8, 14, 21, 37, 45, 53, 58)):
            frame_at(t).save(OUT / f'myself_preview{i}.png')
        print('preview ok')
        return
    silent = OUT / 'myself_silent.mp4'
    writer = imageio_ffmpeg.write_frames(str(silent), (W, H), fps=FPS, macro_block_size=8,
                                         output_params=['-crf', '18', '-preset', 'medium'])
    writer.send(None)
    n = round(total * FPS)
    for k in range(n):
        writer.send(frame_at(k / FPS).tobytes())
        if k % 150 == 0:
            print(f'{k}/{n}', flush=True)
    writer.close()
    music = OUT / 'music.wav'
    out = OUT / 'myself.mp4'
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, '-y', '-loglevel', 'error', '-i', str(silent), '-i', str(music),
                    '-af', f'afade=t=in:d=1,afade=t=out:st={total - 3}:d=3', '-t', str(total),
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', str(out)], check=True)
    silent.unlink()
    print('ok', out, f'{total:.0f}s')


if __name__ == '__main__':
    main()

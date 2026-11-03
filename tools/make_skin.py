"""做一套换装皮肤：先有一张底图，再让 Gemini 在底图上改出 12 个表情，最后抠成桌面用的透明图。

用法：
  python tools/make_skin.py faces <皮肤文件夹> [表情 ...]   在 <文件夹>/idle_src.png 上改出表情（不写就全做）
                                                         <文件夹>/prompts/ 里有同名提示词时优先用它
  python tools/make_skin.py cut   <皮肤文件夹>              抠图，输出到 <文件夹>/cut/，再拼一张 cut_check.png

表情的提示词在 art/drafts/prompts/skin/，和清冷版共用。
gaze_blink 是在 gaze 上闭眼，blink 和 gaze_blink 抠图时沿用睁眼图的轮廓，眨眼时边缘不会跳。
Gemini 偶尔超时（503，不收费），每张最多重试 3 次。
"""
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / 'art' / 'drafts' / 'prompts' / 'skin'
DRAFTS = ROOT / 'art' / 'drafts'
NAMES = ['idle', 'blink', 'think', 'work', 'ask', 'happy', 'tired', 'sleep', 'poke', 'gaze', 'gaze_blink', 'pout', 'huff']
EDITS = [n for n in NAMES if n not in ('idle', 'gaze_blink')]
LIKE = {'blink': 'idle', 'gaze_blink': 'gaze'}


def edit(folder, name):
    ref = folder / ('gaze_src.jpg' if name == 'gaze_blink' else 'idle_src.png')
    tag = f'{folder.name}_{name}'
    own = folder / 'prompts' / f'{name}.txt'   # 这套皮肤自己的表情提示词
    prompt = own if own.exists() else PROMPTS / f'{name}.txt'
    for attempt in range(3):
        r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'imagegen.py'), 'gemini', '--model', 'gemini-3-pro-image',
                            '--aspect', '1:1', '--image-size', '2K', '--prompt-file', str(prompt),
                            '--ref', str(ref), '--tag', tag], capture_output=True, text=True, encoding='utf-8')
        saved = [line.split(' ', 1)[1] for line in r.stdout.splitlines() if line.startswith('saved ')]
        if saved:
            (ROOT / saved[0]).replace(folder / f'{name}_src.jpg')
            return f'{name} ok'
        time.sleep(5)
    return f'{name} FAILED: {(r.stdout + r.stderr)[-200:]}'


def faces(folder, names):
    first = [n for n in names if n != 'gaze_blink']
    with ThreadPoolExecutor(4) as pool:
        for line in pool.map(lambda n: edit(folder, n), first):
            print(line, flush=True)
    if 'gaze_blink' in names:   # 要等托腮图画好
        print(edit(folder, 'gaze_blink'), flush=True)


def cut(folder):
    sys.path.insert(0, str(ROOT / 'tools'))
    import cutout_bust
    (folder / 'cut').mkdir(exist_ok=True)
    src = lambda n: folder / ('idle_src.png' if n == 'idle' else f'{n}_src.jpg')
    for n in NAMES:
        cutout_bust.cutout(str(src(n)), str(folder / 'cut' / f'{n}.png'), str(src(LIKE[n])) if n in LIKE else None)
    sheet = Image.new('RGB', (7 * 260, 2 * 270), (40, 44, 52))
    for i, n in enumerate(NAMES):
        im = Image.open(folder / 'cut' / f'{n}.png').resize((256, 256))
        sheet.paste(im, ((i % 7) * 260, (i // 7) * 270), im)
        ImageDraw.Draw(sheet).text(((i % 7) * 260 + 6, (i // 7) * 270 + 4), n, fill='white')
    sheet.save(folder / 'cut_check.png')
    print('cut ok', folder / 'cut_check.png')


if __name__ == '__main__':
    step, folder = sys.argv[1], (ROOT / sys.argv[2]).resolve()
    if step == 'faces':
        faces(folder, sys.argv[3:] or EDITS + ['gaze_blink'])
    elif step == 'cut':
        cut(folder)

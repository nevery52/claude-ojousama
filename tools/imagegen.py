"""让 Claude 自己给大小姐画图：调用 OpenAI（GPT Image）和 Google（Gemini / Nano Banana）的图片接口。

密钥只从两个地方读，绝不写进项目、绝不打印：
  1. 环境变量 OPENAI_API_KEY / GEMINI_API_KEY
  2. 用户自己建的文件 ~/.ojousama/keys.env（每行一个 KEY=值），在项目文件夹外面，不会被提交

用法：
  python tools/imagegen.py check                      看看两家各有哪些图片模型可用
  python tools/imagegen.py gpt    --prompt-file p.txt [--ref 图.jpg ...] [--n 2]
  python tools/imagegen.py gemini --prompt-file p.txt [--ref 图.jpg ...] [--n 2]

有 --ref 时，GPT 走"改图/参考图"接口，Gemini 把图和文字一起发过去；没有就是从头画。
出图存在 art/drafts/，每次调用记一行到 state/imagegen_log.jsonl（不含密钥），方便算花了多少张。
"""
import argparse
import base64
import http.client
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / 'art' / 'drafts'
LOG = ROOT / 'state' / 'imagegen_log.jsonl'
KEY_FILE = Path.home() / '.ojousama' / 'keys.env'

MAX_PER_RUN = 4            # 一次最多画几张，防止不小心花太多
DEFAULT_MODELS = {         # 默认模型；以 check 查到的为准，可用 --model 改
    'gpt': 'gpt-image-2',
    'gemini': 'gemini-3.1-flash-image',
}


# ---------------------------------------------------------------- 密钥

def load_key(name):
    if os.environ.get(name):
        return os.environ[name].strip()
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text('utf-8-sig').splitlines():
            key, _, value = line.partition('=')
            if key.strip() == name and value.strip():
                return value.strip().strip('"').strip("'")
    return None


def need_key(name):
    key = load_key(name)
    if not key:
        sys.exit(f'没找到 {name}。请把它写进 {KEY_FILE}（一行：{name}=你的密钥），或设成环境变量。')
    return key


# ---------------------------------------------------------------- 网络

def request(url, *, headers=None, data=None, timeout=300):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST' if data else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as err:
        body = err.read().decode('utf-8', 'replace')[:800]
        sys.exit(f'接口返回错误 {err.code}：{body}')
    except urllib.error.URLError as err:
        sys.exit(f'连不上接口：{err.reason}（如果平时要开代理，确认 HTTPS_PROXY 设置了）')
    except (ConnectionError, http.client.HTTPException, TimeoutError) as err:
        sys.exit(f'连接中途断了：{type(err).__name__}（网络不稳，或者参考图太大；可以稍后重试，或缩小参考图）')


def multipart(fields, files):
    """把普通字段和图片文件拼成 multipart/form-data。"""
    boundary = uuid.uuid4().hex
    out = bytearray()
    for name, value in fields:
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    for name, path in files:
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
                f'Content-Type: {mime}\r\n\r\n').encode()
        out += path.read_bytes() + b'\r\n'
    out += f'--{boundary}--\r\n'.encode()
    return bytes(out), f'multipart/form-data; boundary={boundary}'


# ---------------------------------------------------------------- 两家接口

def gpt(prompt, refs, n, model, size, quality):
    key = need_key('OPENAI_API_KEY')
    auth = {'Authorization': f'Bearer {key}'}
    if refs:
        fields = [('model', model), ('prompt', prompt), ('n', str(n)), ('size', size), ('quality', quality)]
        body, ctype = multipart(fields, [('image[]', p) for p in refs])
        result = request('https://api.openai.com/v1/images/edits', headers={**auth, 'Content-Type': ctype}, data=body)
    else:
        body = json.dumps({'model': model, 'prompt': prompt, 'n': n, 'size': size, 'quality': quality}).encode()
        result = request('https://api.openai.com/v1/images/generations',
                         headers={**auth, 'Content-Type': 'application/json'}, data=body)
    return [base64.b64decode(item['b64_json']) for item in result.get('data', []) if item.get('b64_json')]


def gemini(prompt, refs, n, model, aspect, image_size):
    key = need_key('GEMINI_API_KEY')
    parts = [{'inline_data': {'mime_type': mimetypes.guess_type(p.name)[0] or 'image/png',
                              'data': base64.b64encode(p.read_bytes()).decode()}} for p in refs]
    parts.append({'text': prompt})
    payload = {
        'contents': [{'parts': parts}],
        'generationConfig': {'responseModalities': ['IMAGE'],
                             'imageConfig': {'aspectRatio': aspect, 'imageSize': image_size}},
    }
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    images = []
    for _ in range(n):   # Gemini 一次出一张，要几张就调几次
        result = request(url, headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
                         data=json.dumps(payload).encode())
        for cand in result.get('candidates', []):
            for part in cand.get('content', {}).get('parts', []):
                blob = part.get('inlineData') or part.get('inline_data')
                if blob and blob.get('data'):
                    images.append(base64.b64decode(blob['data']))
        if not images:
            sys.exit(f'Gemini 没有返回图片：{json.dumps(result, ensure_ascii=False)[:800]}')
    return images


def check():
    for provider, name in (('GPT', 'OPENAI_API_KEY'), ('Gemini', 'GEMINI_API_KEY')):
        key = load_key(name)
        if not key:
            print(f'{provider}：还没有密钥（{name}）')
            continue
        if provider == 'GPT':
            data = request('https://api.openai.com/v1/models', headers={'Authorization': f'Bearer {key}'})
            models = sorted(m['id'] for m in data.get('data', []) if 'image' in m['id'])
        else:
            data = request('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000',
                           headers={'x-goog-api-key': key})
            models = sorted(m['name'].removeprefix('models/') for m in data.get('models', [])
                            if 'image' in m['name'] or 'banana' in m['name'])
        print(f'{provider}：密钥可用，图片模型有 {len(models)} 个')
        for m in models:
            print('   ', m)


# ---------------------------------------------------------------- 主程序

def main():
    ap = argparse.ArgumentParser(description='给大小姐画图')
    ap.add_argument('provider', choices=['gpt', 'gemini', 'check'])
    ap.add_argument('--prompt', help='提示词')
    ap.add_argument('--prompt-file', type=Path, help='从文件读提示词（中文长提示词推荐用这个）')
    ap.add_argument('--ref', type=Path, action='append', default=[], help='参考图/要改的图，可以给多张')
    ap.add_argument('--n', type=int, default=1, help=f'画几张（最多 {MAX_PER_RUN}）')
    ap.add_argument('--model', help='模型名，默认见 DEFAULT_MODELS')
    ap.add_argument('--size', default='1024x1536', help='GPT 的尺寸，竖版默认 1024x1536')
    ap.add_argument('--quality', default='high', help='GPT 的质量：high / medium / low')
    ap.add_argument('--aspect', default='9:16', help='Gemini 的宽高比')
    ap.add_argument('--image-size', default='2K', help='Gemini 的清晰度：1K / 2K / 4K')
    ap.add_argument('--tag', default='draft', help='文件名里的标签，方便认')
    args = ap.parse_args()

    if args.provider == 'check':
        return check()
    prompt = args.prompt or (args.prompt_file.read_text('utf-8') if args.prompt_file else None)
    if not prompt:
        sys.exit('请用 --prompt 或 --prompt-file 给提示词')
    if not 1 <= args.n <= MAX_PER_RUN:
        sys.exit(f'--n 要在 1 到 {MAX_PER_RUN} 之间')
    for ref in args.ref:
        if not ref.exists():
            sys.exit(f'找不到参考图：{ref}')

    model = args.model or DEFAULT_MODELS[args.provider]
    started = time.time()
    if args.provider == 'gpt':
        images = gpt(prompt, args.ref, args.n, model, args.size, args.quality)
    else:
        images = gemini(prompt, args.ref, args.n, model, args.aspect, args.image_size)

    DRAFTS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%m%d-%H%M%S')
    saved = []
    for i, data in enumerate(images, 1):
        ext = '.jpg' if data[:3] == b'\xff\xd8\xff' else '.webp' if data[8:12] == b'WEBP' else '.png'
        path = DRAFTS / f'{stamp}_{args.provider}_{args.tag}_{i}{ext}'
        path.write_bytes(data)
        saved.append(path)
        print('saved', path.relative_to(ROOT))

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'at': stamp, 'provider': args.provider, 'model': model, 'n': len(images),
                            'refs': [str(r) for r in args.ref], 'files': [p.name for p in saved],
                            'seconds': round(time.time() - started)}, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()

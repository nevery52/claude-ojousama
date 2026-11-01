"""给介绍视频写一段八音盒小曲：C 大调，I–V–vi–IV，每分钟 80 拍，约 63 秒。完全用代码合成。"""
import sys
import wave

import numpy as np

SR = 44100
BPM = 80
BEAT = 60 / BPM
BAR = 4 * BEAT                 # 3 秒一小节
LENGTH = 63.0

NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def freq(name):
    """'E5' -> 频率"""
    return 440 * 2 ** ((NOTE[name[0]] + 12 * (int(name[1:]) + 1) - 69) / 12)


CHORDS = [('C3', ['C4', 'E4', 'G4']), ('G2', ['B3', 'D4', 'G4']),
          ('A2', ['A3', 'C4', 'E4']), ('F2', ['A3', 'C4', 'F4'])]

# 两种旋律：分解和弦，和一段会唱的小旋律。(拍位置, 音)
ARP = [[(0, 'E5'), (1, 'G5'), (2, 'C6'), (3, 'G5')],
       [(0, 'D5'), (1, 'G5'), (2, 'B5'), (3, 'G5')],
       [(0, 'C5'), (1, 'E5'), (2, 'A5'), (3, 'E5')],
       [(0, 'C5'), (1, 'F5'), (2, 'A5'), (3, 'G5')]]
SONG = [[(0, 'E5'), (1.5, 'D5'), (2, 'C5'), (3, 'G5')],
        [(0, 'D5'), (1.5, 'B4'), (2, 'G4'), (3, 'D5')],
        [(0, 'C5'), (1, 'E5'), (2, 'A5'), (3.5, 'G5')],
        [(0, 'A5'), (1, 'G5'), (2, 'F5'), (2.5, 'E5'), (3, 'D5')]]


def music_box(f, dur=2.4, vol=0.22):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t / 0.55) * np.minimum(t / 0.004, 1)
    tone = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.2)
            + 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t / 0.1))
    return vol * env * tone


def pad(fs, dur, vol=0.05):
    t = np.arange(int(SR * dur)) / SR
    env = np.minimum(t / 0.8, 1) * np.minimum((dur - t) / 0.8, 1)
    tone = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) for f in fs)
    return vol * env * tone / len(fs)


def bass(f, dur, vol=0.12):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t / 1.4) * np.minimum(t / 0.01, 1)
    return vol * env * np.sin(2 * np.pi * f * t)


def put(track, sound, at):
    i = int(at * SR)
    n = min(len(sound), len(track) - i)
    if n > 0:
        track[i:i + n] += sound[:n]


def reverb(x):
    """简单的混响：和一段指数衰减的噪声做卷积。"""
    rng = np.random.default_rng(7)
    n = int(SR * 1.6)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR / 0.35)
    ir[0] = 0
    ir /= np.abs(ir).sum() / 2.5
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]
    return x + 0.35 * wet


def main(out):
    track = np.zeros(int(SR * LENGTH))
    bars = int(LENGTH // BAR)                      # 21 小节，最后一小节收尾
    for b in range(bars):
        start = b * BAR
        root, chord = CHORDS[b % 4]
        cycle = b // 4
        last = b == bars - 1
        if last:                                   # 结尾：一个长长的 C 和弦
            for k, n in enumerate(['C5', 'E5', 'G5', 'C6']):
                put(track, music_box(freq(n), 4, 0.18), start + k * 0.12)
            put(track, bass(freq('C3'), 4), start)
            put(track, pad([freq(n) for n in ['C4', 'E4', 'G4']], 3.5), start)
            break
        if cycle >= 1:
            put(track, bass(freq(root), BAR), start)
            put(track, pad([freq(n) for n in chord], BAR + 0.6), start)
        melody = SONG if cycle in (2, 4) else ARP
        quiet = 0.14 if b < 2 else 0.2            # 开头轻一点
        for beat, n in melody[b % 4]:
            put(track, music_box(freq(n), vol=quiet), start + beat * BEAT)
        if cycle in (2, 4):                        # 唱旋律时，底下轻轻垫一层分解和弦
            for beat, n in ARP[b % 4]:
                put(track, music_box(freq(n) / 2, vol=0.07), start + beat * BEAT + 0.02)
    track = reverb(track)
    t = np.arange(len(track)) / SR
    track *= np.minimum(t / 1.0, 1) * np.clip((LENGTH - t) / 3.0, 0, 1)
    track /= np.abs(track).max() / 0.8
    left = track
    right = np.roll(track, int(SR * 0.012))         # 一点点左右差，听起来更宽
    pcm = (np.stack([left, right], 1) * 32767).astype(np.int16)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'music.wav')

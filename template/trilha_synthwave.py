"""Gera uma trilha original estilo synthwave/trap de "cidade à noite" (clima de jogo de mundo aberto).

Não usa nenhuma música protegida: tudo é sintetizado aqui com numpy.
Uso: python3 trilha_synthwave.py saida.wav [duracao_seg]
"""
import sys
import wave

import numpy as np

SR = 44100
BPM = 92
BEAT = 60 / BPM
STEP = BEAT / 4  # semicolcheia


def note_hz(n):  # n = semitons a partir de A4
    return 440.0 * 2 ** (n / 12)


def env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) * np.exp(-t / r)
    return e


def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    out = 0
    for d in (-detune, 0, detune):
        ph = (t * f * (1 + d)) % 1
        out = out + (2 * ph - 1)
    return out / 3


def lowpass_fast(x, k):
    # média móvel em cascata (rápido o bastante para trilhas curtas)
    ker = np.ones(k) / k
    return np.convolve(np.convolve(x, ker, "same"), ker, "same")


def kick(n):
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 30)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 6)


def snare(n, rng):
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - lowpass_fast(noise, 8)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    return (noise * np.exp(-t * 14) * 0.7 + tone * 0.5)


def hat(n, rng):
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - lowpass_fast(noise, 3)
    return noise * np.exp(-t * 60)


def main(out, dur):
    rng = np.random.default_rng(7)
    total = int(SR * dur)
    L = np.zeros(total + SR * 2)
    R = np.zeros_like(L)

    # progressão em Fá menor: Fm - Db - Ab - Eb (2 compassos cada acorde = 1 compasso aqui)
    chords = [[-4, -1, 3], [-8, -4, -1], [-1, 3, 6], [-6, -2, 1]]
    roots = [-28, -32, -25, -30]
    bar = BEAT * 4
    nbars = int(dur / bar) + 2
    side = np.ones_like(L)

    for b in range(nbars):
        t0 = b * bar
        ci = b % 4
        i0 = int(t0 * SR)
        # pad
        n = int(bar * SR)
        if i0 + n > len(L):
            break
        pad = sum(saw(note_hz(c), n, 0.004) for c in chords[ci]) / 3
        pad = lowpass_fast(pad, 40) * np.minimum(1, np.arange(n) / (0.3 * SR))
        L[i0:i0 + n] += pad * 0.22
        R[i0:i0 + n] += np.roll(pad, 300) * 0.22
        # baixo em colcheias
        for s in range(8):
            j = i0 + int(s * BEAT / 2 * SR)
            m = int(BEAT / 2 * SR * 0.9)
            oct_ = 12 if s in (3, 7) else 0
            bs = saw(note_hz(roots[ci] + oct_), m) * env(m, 0.003, 0.18)
            bs = lowpass_fast(bs, 25)
            L[j:j + m] += bs * 0.45
            R[j:j + m] += bs * 0.45
        # arpejo (entra depois de 4 compassos)
        if b >= 4:
            arp = chords[ci] + [chords[ci][0] + 12]
            for s in range(16):
                j = i0 + int(s * STEP * SR)
                m = int(STEP * SR)
                f = note_hz(arp[s % 4] + 12)
                a = saw(f, m, 0.002) * env(m, 0.002, 0.08)
                a = lowpass_fast(a, 6)
                pan = 0.5 + 0.35 * np.sin(s)
                L[j:j + m] += a * 0.12 * (1 - pan)
                R[j:j + m] += a * 0.12 * pan
        # bateria
        for s in range(16):
            j = i0 + int(s * STEP * SR)
            if s in (0, 6, 10) or (b % 2 and s == 14):
                m = int(0.5 * SR)
                k = kick(m) * 0.9
                L[j:j + m] += k
                R[j:j + m] += k
                side[j:j + int(0.25 * SR)] = np.minimum(
                    side[j:j + int(0.25 * SR)], 0.35 + 0.65 * np.linspace(0, 1, int(0.25 * SR)))
            if s in (4, 12):
                m = int(0.3 * SR)
                sn = snare(m, rng) * 0.35
                L[j:j + m] += sn
                R[j:j + m] += sn
            if b >= 2:
                m = int(0.05 * SR)
                h = hat(m, rng) * (0.12 if s % 2 == 0 else 0.07)
                L[j:j + m] += h * 0.8
                R[j:j + m] += h * 1.2

    # sidechain no pad/baixo (efeito "pump")
    L *= side
    R *= side
    L, R = L[:total], R[:total]
    fade = int(1.5 * SR)
    for ch in (L, R):
        ch[:int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))
        ch[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([L, R], 1)
    st = np.tanh(st * 1.2)
    st = st / np.max(np.abs(st)) * 0.89
    pcm = (st * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 60)

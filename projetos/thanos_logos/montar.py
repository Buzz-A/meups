"""DIA 8: logos dos jogos presos no rosto dos heróis, virando pó junto com eles.

python3 montar.py fonte.mp4 faces.json pasta_logos saida_sem_audio.mp4 saida_audio.wav
Usa trechos.json e as regras de SEG abaixo. Saída 1440x1080, 30 fps.
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

src, faces_json, pasta_logos, saida, saida_wav = sys.argv[1:6]
AQUI = os.path.dirname(os.path.abspath(__file__))
TRECHOS = json.load(open(os.path.join(AQUI, "trechos.json")))
FACES = json.load(open(faces_json))
W, H, OW, FPS = 1920, 1080, 1440, 30

# logo, filtro do rosto alvo (xmin, xmax, wmin), tempo do pó (segundos dentro do trecho), escala, manual
SEG = {
    "thanos":   dict(logo=None),
    "bucky":    dict(logo="fortnite", x=(0, 1000), w=0, po=3.3, esc=3.0, cx=None),
    "pantera":  dict(logo="roblox", x=(0, 1920), w=60, po=None, esc=1.3,
                     extra=[(3.45, 4.4, (900, 420, 260))], po_extra=3.9),
    "wanda":    dict(logo="warzone", x=(0, 1920), w=40, po=4.1, esc=1.7),
    "falcao":   dict(logo="r6", x=(0, 1920), w=150, po=1.9, esc=1.3),
    "mantis":   dict(logo="forza", x=(0, 1920), w=80, po=2.8, esc=1.3),
    "drax":     dict(logo="cs2", x=(0, 1200), w=30, po=3.9, esc=2.4),
    "starlord": dict(logo="eafc", x=(0, 1920), w=120, po=2.0, esc=1.25, desde=0.1),
    "estranho": dict(logo="rdr2", x=(0, 1920), w=120, po=3.0, esc=1.2),
    "aranha1":  dict(logo="minecraft", x=(0, 1920), w=120, po=None, esc=1.25, desde=0.1),
    "aranha2":  dict(logo="minecraft", x=(0, 1000), w=100, po=7.0, esc=1.25),
    "tony":     dict(logo=None, cx=760),
}

CARTAS = {  # arquivo, cor de fundo, pintar logo de branco?
    "fortnite": ("fortnite.png", [(58, 91, 217), (156, 60, 224)], True),
    "roblox": ("roblox.png", [(255, 255, 255)], False),
    "warzone": ("call_of_duty_warzone.png", [(24, 36, 22), (52, 66, 40)], True),
    "r6": ("rainbow_six_siege.png", [(20, 20, 24), (60, 60, 70)], True),
    "forza": ("forza_horizon_5.png", [(255, 255, 255)], False),
    "cs2": ("counter_strike_2.png", [(222, 155, 53), (160, 90, 20)], True),
    "eafc": ("ea_sports_fc.png", [(43, 255, 138), (0, 190, 100)], False),
    "rdr2": ("red_dead_redemption_2.png", [(20, 10, 10), (90, 10, 10)], False),
    "minecraft": ("minecraft.png", [(98, 160, 60), (60, 110, 40)], False),
}


def carta(nome):
    arq, cores, branco = CARTAS[nome]
    cw, ch, r = 420, 320, 64
    fundo = Image.new("RGBA", (cw, ch))
    c0 = np.array(cores[0], float); c1 = np.array(cores[-1], float)
    t = np.linspace(0, 1, ch)[:, None, None]
    grad = (c0 * (1 - t) + c1 * t).repeat(cw, 1)
    fundo = Image.fromarray(np.dstack([grad, np.full((ch, cw), 255.0)]).astype(np.uint8), "RGBA")
    m = Image.new("L", (cw, ch), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, ch - 1), r, fill=255)
    fundo.putalpha(m)
    lg = Image.open(os.path.join(pasta_logos, arq)).convert("RGBA")
    lg = lg.crop(lg.getbbox())
    if branco:
        a = lg.split()[3]; lg = Image.new("RGBA", lg.size, (255, 255, 255, 255)); lg.putalpha(a)
    lg.thumbnail((cw - 70, ch - 80), Image.LANCZOS)
    fundo.alpha_composite(lg, ((cw - lg.width) // 2, (ch - lg.height) // 2))
    # borda branca fina
    ImageDraw.Draw(fundo).rounded_rectangle((2, 2, cw - 3, ch - 3), r - 2, outline=(255, 255, 255, 230), width=5)
    return np.asarray(fundo).astype(np.float32) / 255.0


def trilha(nome, cfg, n):
    """Centro (x, y) e largura do rosto alvo em cada frame, suavizado e com buracos preenchidos."""
    xs = np.full(n, np.nan); ys = np.full(n, np.nan); ws = np.full(n, np.nan)
    x0, x1 = cfg.get("x", (0, W))
    for i, fs in enumerate(FACES[nome][:n]):
        if i < cfg.get("desde", 0) * FPS: continue
        cand = [f for f in fs if x0 <= f[0] + f[2] / 2 <= x1 and f[2] >= cfg.get("w", 0)]
        if not cand: continue
        f = max(cand, key=lambda f: f[2] * f[3])
        xs[i], ys[i], ws[i] = f[0] + f[2] / 2, f[1] + f[3] * 0.45, f[2]
    ok = ~np.isnan(xs)
    if not ok.any():
        return None
    idx = np.arange(n)
    out = []
    for v in (xs, ys, ws):
        v = np.interp(idx, idx[ok], v[ok])
        k = 7; v = np.convolve(np.pad(v, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
        out.append(v)
    return np.stack(out, 1)


def particulas(card, rng):
    """Quebra a carta em blocos de 6 px."""
    ch, cw = card.shape[:2]; b = 6
    ps = []
    for y in range(0, ch, b):
        for x in range(0, cw, b):
            blk = card[y:y + b, x:x + b]
            if blk[..., 3].mean() < 0.05: continue
            ps.append((x, y))
    ps = np.array(ps, float)
    atraso = (ps[:, 0] / cw) * 0.55 + rng.random(len(ps)) * 0.3
    vel = np.stack([rng.uniform(80, 260, len(ps)), rng.uniform(-160, -30, len(ps))], 1)
    return ps, atraso, vel, b


def colar(frame, img, cx, cy, escala, alpha=1.0):
    h, w = img.shape[:2]
    nw, nh = max(2, int(w * escala)), max(2, int(h * escala))
    im = np.asarray(Image.fromarray((img * 255).astype(np.uint8), "RGBA").resize((nw, nh), Image.LANCZOS)).astype(np.float32) / 255
    x, y = int(cx - nw / 2), int(cy - nh / 2)
    xa, ya, xb, yb = max(0, x), max(0, y), min(W, x + nw), min(H, y + nh)
    if xa >= xb or ya >= yb: return
    sub = im[ya - y:yb - y, xa - x:xb - x]
    a = sub[..., 3:4] * alpha
    frame[ya:yb, xa:xb] = frame[ya:yb, xa:xb] * (1 - a) + sub[..., :3][..., ::-1] * 255 * a


def desenhar_po(frame, card, ps, atraso, vel, b, cx, cy, escala, t):
    """t = segundos desde o início do pó."""
    ch, cw = card.shape[:2]
    s = escala
    for (px, py), d, v in zip(ps, atraso, vel):
        dt = t - d
        blk = card[int(py):int(py) + b, int(px):int(px) + b]
        if dt <= 0:
            alpha, ox, oy = 1.0, 0, 0
            cor = blk
        else:
            alpha = max(0.0, 1 - dt / 0.9)
            if alpha <= 0: continue
            ox, oy = v[0] * dt + 60 * dt * dt, v[1] * dt - 30 * dt * dt
            cor = blk.copy(); escurece = min(1, dt * 2.5)
            cor[..., :3] = cor[..., :3] * (1 - escurece) + np.array([0.33, 0.26, 0.2]) * escurece
        sz = max(1, int(round(b * s * (1 - 0.4 * min(1, max(0, dt))))))
        x = int(cx + (px - cw / 2) * s + ox); y = int(cy + (py - ch / 2) * s + oy)
        if x < 0 or y < 0 or x + sz > W or y + sz > H: continue
        c = cor.reshape(-1, 4).mean(0)
        a = c[3] * alpha
        frame[y:y + sz, x:x + sz] = frame[y:y + sz, x:x + sz] * (1 - a) + c[:3][::-1] * 255 * a


def main():
    rng = np.random.default_rng(8)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                            "-pix_fmt", "yuv420p", saida], stdin=subprocess.PIPE)
    wavs = []
    for nome, (ini, fim) in TRECHOS.items():
        cfg = SEG[nome]
        n = int(round((fim - ini) * FPS))
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(ini), "-t", str(fim - ini), "-i", src,
                                "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        wav = saida_wav + f".{nome}.wav"; wavs.append(wav)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(ini), "-t", f"{n / FPS:.4f}", "-i", src, "-vn",
                        "-ac", "2", "-ar", "48000", wav], check=True)
        tr = trilha(nome, cfg, n) if cfg.get("logo") else None
        card = carta(cfg["logo"]) if cfg.get("logo") else None
        if card is not None:
            ps, atraso, vel, b = particulas(card, rng)
        # janela de corte fixa por trecho, centrada no rosto
        if tr is not None:
            cx_med = float(np.median(tr[:, 0]))
        else:
            cx_med = cfg.get("cx") or W / 2
        x0 = int(np.clip(cx_med - OW / 2, 0, W - OW))
        po = cfg.get("po")
        for i in range(n):
            buf = dec.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                buf = last
            last = buf
            fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32)
            t = i / FPS
            if card is not None:
                manual = None
                for (a0, a1, pos) in cfg.get("extra", []):
                    if a0 <= t < a1: manual = (a0, pos)
                if manual:
                    (a0, (mx, my, mw)) = manual
                    esc = mw * cfg["esc"] / card.shape[1]
                    tp = t - cfg["po_extra"]
                    if tp < 0: colar(fr, card, mx, my, esc)
                    else: desenhar_po(fr, card, ps, atraso, vel, b, mx, my, esc, tp)
                elif not (cfg.get("extra") and t >= cfg["extra"][0][0]):
                    if po is not None and t >= po:
                        j = min(int(po * FPS), n - 1)
                        cx, cy, fw = tr[j]
                        desenhar_po(fr, card, ps, atraso, vel, b, cx, cy, fw * cfg["esc"] / card.shape[1], t - po)
                    else:
                        cx, cy, fw = tr[i]
                        colar(fr, card, cx, cy, fw * cfg["esc"] / card.shape[1])
            enc.stdin.write(np.clip(fr[:, x0:x0 + OW], 0, 255).astype(np.uint8).tobytes())
        dec.stdout.close(); dec.wait()
        print(nome, "ok", n, "frames, x0", x0, flush=True)
    enc.stdin.close(); enc.wait()
    # áudio: concatena com fade de 20 ms em cada ponta (sem perder sincronia)
    args = ["ffmpeg", "-v", "error", "-y"]
    for w in wavs: args += ["-i", w]
    fc = "".join(f"[{k}:a]afade=t=in:d=0.02,areverse,afade=t=in:d=0.02,areverse[a{k}];" for k in range(len(wavs)))
    fc += "".join(f"[a{k}]" for k in range(len(wavs))) + f"concat=n={len(wavs)}:v=0:a=1[out]"
    args += ["-filter_complex", fc, "-map", "[out]", saida_wav]
    subprocess.run(args, check=True)
    for w in wavs: os.remove(w)


main()

#!/usr/bin/env python3
"""CTA em motion design: "COMENTA" + pílula com a palavra-chave + linha de apoio.
Entrada: bloco surge com pop (overshoot), a pílula abre da esquerda pra direita revelando o texto,
linhas de cima/baixo sobem com fade. Depois: pulso suave a cada ciclo + brilho passando na pílula.
Escreve frames RGBA (1080 x ALT) no stdout para o ffmpeg sobrepor no y desejado.

Uso: python3 cta_motion.py "COMENTA" "QUERO PRISM" "PRA RECEBER O LINK..." --fonte X.ttf --inicio 6.6 --dur 52.6 | ffmpeg ...
"""
import argparse
import math
import sys

from PIL import Image, ImageDraw, ImageFont, ImageFilter

AZUL = (0, 91, 215)
W, ALT = 1080, 420
FPS = 30


def ease_out_back(x, s=1.7):
    x = min(max(x, 0), 1) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def ease_out(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cima")
    ap.add_argument("destaque")
    ap.add_argument("baixo")
    ap.add_argument("--fonte", required=True)
    ap.add_argument("--inicio", type=float, default=0)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--escala", type=float, default=0.9)
    ap.add_argument("--ciclo", type=float, default=2.4, help="segundos entre pulsos")
    a = ap.parse_args()

    k = a.escala
    f_p = ImageFont.truetype(a.fonte, round(46 * k))
    f_g = ImageFont.truetype(a.fonte, round(92 * k))
    cima, dest, baixo = a.cima.upper(), a.destaque.upper(), a.baixo.upper()
    pw, ph = int(f_g.getlength(dest) + 88 * k), int(124 * k)
    cx, cy = W // 2, ALT // 2
    py = cy - ph // 2

    # camadas fixas pré-renderizadas
    pilula = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    dp = ImageDraw.Draw(pilula)
    dp.rounded_rectangle((0, 0, pw - 1, ph - 1), ph // 2, fill=AZUL + (255,))
    dp.text((pw / 2, ph / 2 + 33 * k), dest, font=f_g, fill="white", anchor="ms")
    mask_pil = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask_pil).rounded_rectangle((0, 0, pw - 1, ph - 1), ph // 2, fill=255)

    def linha(txt):
        w = int(f_p.getlength(txt)) + 20
        im = Image.new("RGBA", (w, int(60 * k)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((w / 2, 46 * k), txt, font=f_p, fill="white", anchor="ms")
        return im

    l_cima, l_baixo = linha(cima), linha(baixo)
    sombra = Image.new("RGBA", (W, ALT), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle(
        (cx - pw / 2 - 50, cy - ph / 2 - 80 * k, cx + pw / 2 + 50, cy + ph / 2 + 80 * k), 40, fill=(0, 0, 0, 110))
    sombra = sombra.filter(ImageFilter.GaussianBlur(28))

    vazio = bytes(W * ALT * 4)
    n = int(round(a.dur * FPS))
    out = sys.stdout.buffer
    for i in range(n):
        t = i / FPS - a.inicio
        if t < 0:
            out.write(vazio)
            continue
        fr = Image.new("RGBA", (W, ALT), (0, 0, 0, 0))
        # sombra entra com fade
        s = sombra.copy()
        s.putalpha(s.getchannel("A").point(lambda v: int(v * ease_out(t / 0.4))))
        fr.alpha_composite(s)

        # pílula: pop de escala + abertura horizontal
        pop = ease_out_back(t / 0.45)
        # pulso periódico depois da entrada
        if t > 1.2:
            fase = ((t - 1.2) % a.ciclo) / 0.5
            if fase < 1:
                pop *= 1 + 0.07 * math.sin(math.pi * fase)
        abre = ease_out(t / 0.5)
        sw, sh = max(int(pw * pop * (0.25 + 0.75 * abre)), 2), max(int(ph * pop), 2)
        p = pilula.copy()
        # brilho diagonal passando (na entrada e a cada ciclo)
        tb = t - 0.5 if t < 1.2 else ((t - 1.2) % a.ciclo) - 0.15
        if 0 <= tb <= 0.6:
            bx = int(-120 + (pw + 240) * (tb / 0.6))
            brilho = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
            ImageDraw.Draw(brilho).polygon(
                [(bx, 0), (bx + 60, 0), (bx + 20, ph), (bx - 40, ph)], fill=(255, 255, 255, 90))
            brilho.putalpha(Image.composite(brilho.getchannel("A"), Image.new("L", (pw, ph), 0), mask_pil))
            p.alpha_composite(brilho)
        p = p.resize((sw, sh), Image.LANCZOS)
        fr.alpha_composite(p, (cx - sw // 2, cy - sh // 2))

        # linhas de apoio sobem com fade (escalonadas)
        for img, y_final, t0 in ((l_cima, py - int(70 * k), 0.15), (l_baixo, py + ph + int(12 * k), 0.3)):
            e = ease_out((t - t0) / 0.4)
            if e <= 0:
                continue
            im = img.copy()
            im.putalpha(im.getchannel("A").point(lambda v, e=e: int(v * e)))
            fr.alpha_composite(im, (cx - im.width // 2, int(y_final + 24 * (1 - e))))
        out.write(fr.tobytes())


if __name__ == "__main__":
    main()

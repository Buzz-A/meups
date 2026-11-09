#!/usr/bin/env python3
"""CTA centralizado e clean: linha pequena em cima, palavra-chave numa pílula azul, linha pequena embaixo.
Gera PNG transparente 1080x1920 (bloco centralizado em x; centro vertical em --cy).

Uso: python3 cta_clean.py "COMENTA" "QUERO PRISM" "PRA RECEBER O LINK E GARANTIR O SEU" saida.png --cy 1330 --fonte Novecento.ttf
"""
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

AZUL = (0, 91, 215, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cima")
    ap.add_argument("destaque")
    ap.add_argument("baixo")
    ap.add_argument("saida")
    ap.add_argument("--cy", type=int, default=1330)
    ap.add_argument("--fonte", required=True)
    a = ap.parse_args()
    W = 1080
    f_p = ImageFont.truetype(a.fonte, 46)
    f_g = ImageFont.truetype(a.fonte, 92)
    dest = a.destaque.upper()
    wd = f_g.getlength(dest)
    pw, ph = int(wd + 2 * 44), 124
    total = 52 + 18 + ph + 18 + 52
    top = a.cy - total // 2
    im = Image.new("RGBA", (W, 1920), (0, 0, 0, 0))
    # sombra suave atrás de tudo, para ler em qualquer fundo
    sombra = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sombra)
    ds.rounded_rectangle((W / 2 - pw / 2 - 40, top - 20, W / 2 + pw / 2 + 40, top + total + 20), 40, fill=(0, 0, 0, 120))
    im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(30)))
    d = ImageDraw.Draw(im)
    d.text((W / 2, top + 44), a.cima.upper(), font=f_p, fill="white", anchor="ms")
    py = top + 52 + 18
    d.rounded_rectangle((W / 2 - pw / 2, py, W / 2 + pw / 2, py + ph), ph // 2, fill=AZUL)
    d.text((W / 2, py + ph / 2 + 33), dest, font=f_g, fill="white", anchor="ms")
    d.text((W / 2, py + ph + 18 + 44), a.baixo.upper(), font=f_p, fill="white", anchor="ms")
    im.save(a.saida)


if __name__ == "__main__":
    main()

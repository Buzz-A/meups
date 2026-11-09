#!/usr/bin/env python3
"""Gera a chamada fixa (CTA) do tipo "COMENTA [QUERO PRISM] PRA RECEBER O LINK" em PNG 1080x1920
transparente, com a palavra-chave em destaque (pílula azul MEUPS, texto branco).

Uso: python3 cta.py "COMENTA" "QUERO PRISM" "PRA RECEBER O LINK E GARANTIR O SEU" saida.png --y 340 --fonte Novecento.ttf
"""
import argparse
from PIL import Image, ImageDraw, ImageFont

AZUL = (0, 91, 215, 255)
BRANCO = (255, 255, 255, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("antes")
    ap.add_argument("destaque")
    ap.add_argument("depois")
    ap.add_argument("saida")
    ap.add_argument("--y", type=int, default=340)
    ap.add_argument("--fonte", required=True)
    a = ap.parse_args()

    f1 = ImageFont.truetype(a.fonte, 62)
    f2 = ImageFont.truetype(a.fonte, 40)
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = 0, a.y
    pad = 80
    antes = a.antes.upper() + "  "
    w_antes = f1.getlength(antes)
    w_dest = f1.getlength(a.destaque.upper())
    w_dep = f2.getlength(a.depois.upper())
    larg = int(pad + max(w_antes + w_dest + 36, w_dep) + 40)
    alt = 160
    # caixa branca com cantos arredondados à direita (mesmo estilo do chapéu)
    d.rounded_rectangle((x0, y0, larg, y0 + alt), 16, fill=BRANCO, corners=(False, True, True, False))
    base1 = y0 + 78
    d.text((pad, base1), antes, font=f1, fill=AZUL, anchor="ls")
    # pílula azul de destaque
    px = pad + w_antes + 4
    d.rounded_rectangle((px - 14, base1 - 62, px + w_dest + 14, base1 + 14), 12, fill=AZUL)
    d.text((px, base1), a.destaque.upper(), font=f1, fill=BRANCO, anchor="ls")
    d.text((pad, y0 + 136), a.depois.upper(), font=f2, fill=AZUL, anchor="ls")
    im.save(a.saida)
    # versão "piscando" da pílula (cores invertidas + contorno) para chamar atenção
    pis = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dp = ImageDraw.Draw(pis)
    dp.rounded_rectangle((px - 14, base1 - 62, px + w_dest + 14, base1 + 14), 12, fill=(255, 196, 0, 255))
    dp.text((px, base1), a.destaque.upper(), font=f1, fill=AZUL, anchor="ls")
    pis.save(a.saida.replace(".png", "_pisca.png"))
    print(a.saida, larg)


if __name__ == "__main__":
    main()

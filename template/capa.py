#!/usr/bin/env python3
"""Gera a capa 1080x1920 dos reels no layout MEUPS (capa_assets/capa_reels.psd).

Grid do PSD:
- margens laterais: x = 60 e x = 1020 (centro em 540)
- área que aparece no feed (4:5): y = 285 até y = 1635 — título e logos ficam aqui dentro
- imagem no topo, degradê de contraste (#0D141D) de y≈400 a 1635 e base sólida até 1920
- título centralizado, caixa alta, entrelinha 100, última linha com base em y = 1506
- "MEUPS.COM.BR" em x = 80, base y = 406; ícone MEUPS em (918, 345)

Uso:
  python3 capa.py imagem.jpg "TÍTULO DO VÍDEO" saida.png --foco-x 0.5 --foco-y 0.3 --zoom 1.0
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

AQUI = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(AQUI, "capa_assets")
W, H = 1080, 1920
FEED_TOPO, FEED_BASE = 285, 1635
MARGEM = 60


def fonte_cap(caminho, cap_px):
    tam = cap_px
    for _ in range(4):
        f = ImageFont.truetype(caminho, tam)
        _, y0, _, y1 = f.getbbox("H", anchor="ls")
        tam = round(tam * cap_px / (y1 - y0))
    return ImageFont.truetype(caminho, tam)


def quebrar_equilibrado(texto, f, largura):
    """Quebra em linhas que cabem na largura, deixando as linhas com tamanhos parecidos."""
    if "|" in texto:
        return [l.strip() for l in texto.split("|")]
    palavras = texto.split()

    def greedy(lim):
        linhas, atual = [], ""
        for p in palavras:
            t = (atual + " " + p).strip()
            if f.getlength(t) <= lim or not atual:
                atual = t
            else:
                linhas.append(atual)
                atual = p
        return linhas + [atual]

    base = greedy(largura)
    melhor = base
    lim = largura
    while lim > largura * 0.5:
        lim -= 10
        t = greedy(lim)
        if len(t) > len(base):
            break
        melhor = t
    return melhor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("imagem")
    ap.add_argument("titulo")
    ap.add_argument("saida")
    ap.add_argument("--foco-x", type=float, default=0.5, help="0 = esquerda, 1 = direita da imagem")
    ap.add_argument("--foco-y", type=float, default=0.3)
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--desce", type=int, default=0,
                    help="desce a imagem N px (rostos no alto da foto ficam fora do corte do feed, y<285); "
                         "o espaço de cima é preenchido com a própria imagem desfocada")
    ap.add_argument("--fonte", default=os.path.join(AQUI, "fonts/BarlowCondensed-ExtraBold.ttf"))
    ap.add_argument("--fonte-light", default=os.path.join(AQUI, "fonts/BarlowCondensed-Light.ttf"))
    a = ap.parse_args()

    capa = Image.new("RGB", (W, H), (13, 20, 29))
    # imagem ocupa o topo até y≈1480 (o degradê esconde a parte de baixo)
    area_h = H  # imagem preenche a capa inteira; o degradê cobre só a parte de baixo
    img = Image.open(a.imagem).convert("RGB")
    s = max(W / img.width, area_h / img.height) * a.zoom
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = round((img.width - W) * a.foco_x)
    y = round((img.height - area_h) * a.foco_y)
    recorte = img.crop((x, y, x + W, y + area_h))
    if a.desce:
        from PIL import ImageFilter
        fundo = recorte.crop((0, 0, W, 300)).resize((W, H)).filter(ImageFilter.GaussianBlur(50)).point(lambda v: int(v * 0.55))
        capa.paste(fundo, (0, 0))
        # emenda suave: os primeiros 120 px da imagem entram em degradê sobre o fundo
        m = Image.linear_gradient("L").resize((W, 120))
        mask = Image.new("L", recorte.size, 255)
        mask.paste(m, (0, 0))
        capa.paste(recorte, (0, a.desce), mask)
    else:
        capa.paste(recorte, (0, 0))
    capa = capa.convert("RGBA")

    deg = Image.open(os.path.join(A, "degrade_contraste.png")).convert("RGBA")
    capa.alpha_composite(deg, (0, 400), (68, 0, 68 + W, deg.height))
    ext = Image.open(os.path.join(A, "degrade_extensao.png")).convert("RGBA")
    capa.alpha_composite(ext, (0, 1631))

    d = ImageDraw.Draw(capa)
    # site com espaçamento largo, igual ao PSD (tracking 375)
    f_site = fonte_cap(a.fonte_light, 25)
    xx = 80
    for ch in "MEUPS.COM.BR":
        d.text((xx, 406), ch, font=f_site, fill=(255, 255, 255, 235), anchor="ls")
        xx += f_site.getlength(ch) + f_site.size * 0.375
    icone = Image.open(os.path.join(A, "icone_meups.png")).convert("RGBA")
    capa.alpha_composite(icone, (918, 345))

    # título: centralizado entre as margens, última linha com base em y=1506
    f = fonte_cap(a.fonte, 71)
    linhas = quebrar_equilibrado(a.titulo.upper(), f, W - 2 * MARGEM)
    while max(f.getlength(l) for l in linhas) > W - 2 * MARGEM or len(linhas) > 4:
        f = ImageFont.truetype(a.fonte, f.size - 4)  # título longo: reduz para caber no grid
        linhas = quebrar_equilibrado(a.titulo.upper(), f, W - 2 * MARGEM)
    entrelinha = round(100 * f.size / fonte_cap(a.fonte, 71).size)
    base = 1506
    topo = base - entrelinha * (len(linhas) - 1) - 71
    assert topo > 460, "título alto demais: invade a imagem/logos"
    for i, l in enumerate(linhas):
        d.text((W / 2, base - entrelinha * (len(linhas) - 1 - i)), l, font=f, fill="white", anchor="ms")
    capa.convert("RGB").save(a.saida, quality=95)
    print(a.saida, linhas)


if __name__ == "__main__":
    main()

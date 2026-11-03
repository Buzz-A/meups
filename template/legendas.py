"""Legendas animadas (estilo "pop") para o layout MEUPS.

Arquivo de legendas (JSON): lista de frases
  {"ini": 0.0, "fim": 0.5, "texto": "Comprar *GTA 6*", "y": 852, "grande": false, "cobrir": 0}
- texto: palavras entre *asteriscos* ficam amarelas
- y: centro vertical da legenda no quadro final 1080x1920
- grande: legenda de destaque (números, palavras de impacto)
- cobrir: largura mínima da caixa (px) para esconder uma legenda antiga queimada no vídeo

gerar_frames() devolve um gerador de quadros RGBA 1080x1920 (bytes) para mandar ao ffmpeg.
"""
import json

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
AMARELO = (255, 212, 0, 255)
BRANCO = (255, 255, 255, 255)


def _tokens(texto):
    partes = texto.split("*")
    return [(p, i % 2 == 1) for i, p in enumerate(partes) if p]


def render_legenda(frase, fonte_path, azul):
    tam = 92 if frase.get("grande") else 62
    f = ImageFont.truetype(fonte_path, tam)
    toks = [(t.upper(), dest) for t, dest in _tokens(frase["texto"])]
    larg_txt = sum(f.getlength(t) for t, _ in toks)
    x0, y0, x1, y1 = f.getbbox("ÁG", anchor="ls")
    pad_x, pad_y = 44, 22
    larg = int(max(larg_txt + 2 * pad_x, frase.get("cobrir", 0)))
    alt = int((y1 - y0) + 2 * pad_y)
    im = Image.new("RGBA", (larg + 12, alt + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 10, larg + 6, alt + 10), 22, fill=(0, 0, 0, 90))  # sombra
    d.rounded_rectangle((6, 6, larg + 6, alt + 6), 22, fill=azul)
    x = 6 + (larg - larg_txt) / 2
    base = 6 + pad_y - y0
    for t, dest in toks:
        d.text((x, base), t, font=f, fill=AMARELO if dest else BRANCO, anchor="ls")
        x += f.getlength(t)
    return im


def _escala(dt):
    """Pop com leve exagero (ease-out-back) nos primeiros 0,16 s."""
    d = 0.16
    if dt >= d:
        return 1.0, 255
    p = dt / d
    c1 = 1.70158
    c3 = c1 + 1
    s = 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
    return 0.6 + 0.4 * s, int(255 * min(1, p * 2))


def gerar_frames(caminho_json, fonte_path, azul, fps, n_frames):
    with open(caminho_json, encoding="utf-8") as fp:
        frases = json.load(fp)
    for fr in frases:
        fr["_img"] = render_legenda(fr, fonte_path, azul)
    vazio = Image.new("RGBA", (W, H), (0, 0, 0, 0)).tobytes()
    for i in range(n_frames):
        t = i / fps
        ativas = [fr for fr in frases if fr["ini"] <= t < fr["fim"]]
        if not ativas:
            yield vazio
            continue
        quadro = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for fr in ativas:
            s, a = _escala(t - fr["ini"])
            img = fr["_img"]
            if s != 1.0:
                img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
            if a < 255:
                alpha = img.getchannel("A").point(lambda v: v * a // 255)
                img = img.copy()
                img.putalpha(alpha)
            quadro.alpha_composite(img, (int(W / 2 - img.width / 2), int(fr["y"] - img.height / 2)))
        yield quadro.tobytes()

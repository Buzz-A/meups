#!/usr/bin/env python3
"""Evolução das aberturas de GTA (GTA 1 ao GTA VI).

Monta duas versões a partir das intros de cada jogo:
  - YouTube 16:9 (1920x1080): card de abertura, cada intro em tela cheia com tag
    animada "NOME + ANO", linha do tempo embaixo, logo MEUPS e card final de CTA.
  - Redes 9:16 (1080x1920): cada intro inteira na largura sobre fundo desfocado,
    tag abaixo do vídeo e linha do tempo; depois passe em ../../template/render.py
    (logo + chapéu + título com --titulo-ate 10).

Uso:
  python evolucao.py segmentos.json SAIDA_DIR --base E:\\MEUPS\\_evolucao_intros \
      --fonte "...\\Novecento CondUltraBold.ttf" --fonte-light "...\\NOVECENTO CONDLIGHT.OTF"
  (--so-quadros gera só um frame de cada segmento para conferir, sem renderizar)
"""
import argparse
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.normpath(os.path.join(AQUI, "..", "..", "template"))
AZUL = (0, 91, 215, 255)
BRANCO = (255, 255, 255, 255)
FPS = 30


def run(cmd):
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def fonte(path, cap_px):
    """Tamanho da fonte para que a maiúscula tenha cap_px de altura."""
    tam = cap_px
    for _ in range(3):
        f = ImageFont.truetype(path, tam)
        _, y0, _, y1 = f.getbbox("H")
        tam = max(4, round(tam * cap_px / (y1 - y0)))
    return ImageFont.truetype(path, tam)


# ---------------------------------------------------------------- gráficos
def _sombra(im, raio=10, forca=0.7, dy=4):
    """Sombra preta suave atrás do conteúdo (mesmo tamanho do canvas)."""
    s = Image.new("RGBA", im.size, (0, 0, 0, 0))
    s.paste(Image.new("RGBA", im.size, (0, 0, 0, 255)), (0, dy), im.split()[3].point(lambda v: int(v * forca)))
    s = s.filter(ImageFilter.GaussianBlur(raio))
    s.alpha_composite(im)
    return s


def tag_png(nome, ano, idx, total, f_bold, f_light, escala, destino, largura):
    """Cartela do jogo, centralizada e sem caixas (não confunde com o título do layout):
    '—— 2001  ·  03/10 ——' em cima, nome grande branco com contorno e sublinhado azul."""
    margem = int(70 * escala)
    cap = int(72 * escala)
    fn = fonte(f_bold, cap)
    while fn.getlength(nome) > largura - 2 * margem and cap > 20:
        cap -= 2
        fn = fonte(f_bold, cap)
    fa = fonte(f_bold, int(30 * escala))
    fc = fonte(f_light, int(30 * escala))
    H = int(cap * 1.6 + 110 * escala)
    im = Image.new("RGBA", (largura, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = largura // 2
    # linha do ano
    y_ano = int(42 * escala)
    contador = f"  ·  {idx:02d}/{total:02d}"
    w_ano = fa.getlength(ano) + fc.getlength(contador)
    x0 = cx - w_ano / 2
    d.text((x0, y_ano), ano, font=fa, fill=(120, 180, 255, 255), anchor="ls")
    d.text((x0 + fa.getlength(ano), y_ano), contador, font=fc, fill=(255, 255, 255, 210), anchor="ls")
    gap, comp = int(22 * escala), int(70 * escala)
    yl = y_ano - int(11 * escala)
    lw = max(2, int(3 * escala))
    d.line((x0 - gap - comp, yl, x0 - gap, yl), fill=(255, 255, 255, 200), width=lw)
    d.line((x0 + w_ano + gap, yl, x0 + w_ano + gap + comp, yl), fill=(255, 255, 255, 200), width=lw)
    # nome do jogo com contorno escuro
    y_nome = y_ano + int(22 * escala) + cap
    d.text((cx, y_nome), nome, font=fn, fill=BRANCO, anchor="ms",
           stroke_width=max(2, int(4 * escala)), stroke_fill=(0, 0, 0, 230))
    # sublinhado azul de destaque
    wb = int(min(fn.getlength(nome) * 0.35, 260 * escala))
    yb = y_nome + int(20 * escala)
    d.rounded_rectangle((cx - wb // 2, yb, cx + wb // 2, yb + int(8 * escala)), int(4 * escala), fill=AZUL)
    im = _sombra(im, raio=int(12 * escala), forca=0.75)
    im.save(destino)
    return im.size


def timeline_png(segs, atual, largura, f_bold, f_light, escala, destino):
    """Linha do tempo num painel escuro de destaque: trecho percorrido em azul,
    jogo atual com anel brilhante e o ano numa pílula azul."""
    n = len(segs)
    margem = int(40 * escala)
    Wp = largura - 2 * margem
    Hp = int(150 * escala)
    im = Image.new("RGBA", (largura, Hp + int(30 * escala)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(26 * escala)
    d.rounded_rectangle((margem, 0, margem + Wp, Hp), r, fill=(6, 10, 22, 190),
                        outline=(255, 255, 255, 70), width=max(1, int(2 * escala)))
    fy = fonte(f_bold, int(20 * escala))
    fy_at = fonte(f_bold, int(26 * escala))
    y = int(56 * escala)
    m = margem + int(60 * escala)
    xs = [m + (largura - 2 * m) * i / (n - 1) for i in range(n)]
    lw = max(3, int(6 * escala))
    d.line((xs[0], y, xs[-1], y), fill=(255, 255, 255, 70), width=lw)
    d.line((xs[0], y, xs[atual], y), fill=AZUL, width=lw)
    brilho = Image.new("RGBA", im.size, (0, 0, 0, 0))
    db = ImageDraw.Draw(brilho)
    for i, (x, s) in enumerate(zip(xs, segs)):
        if i == atual:
            R = int(22 * escala)
            db.ellipse((x - R * 2, y - R * 2, x + R * 2, y + R * 2), fill=(40, 130, 255, 200))
            d.ellipse((x - R - 5 * escala, y - R - 5 * escala, x + R + 5 * escala, y + R + 5 * escala), fill=BRANCO)
            d.ellipse((x - R, y - R, x + R, y + R), fill=AZUL)
            tw = fy_at.getlength(s["ano"]) + int(28 * escala)
            ty = y + int(42 * escala)
            th = int(44 * escala)
            d.rounded_rectangle((x - tw / 2, ty, x + tw / 2, ty + th), th // 2, fill=AZUL)
            d.text((x, ty + th / 2), s["ano"], font=fy_at, fill=BRANCO, anchor="mm")
        else:
            R = int(10 * escala)
            if i < atual:
                d.ellipse((x - R, y - R, x + R, y + R), fill=BRANCO, outline=AZUL, width=max(2, int(3 * escala)))
                cor = (255, 255, 255, 215)
            else:
                d.ellipse((x - R, y - R, x + R, y + R), fill=(30, 34, 46, 255),
                          outline=(255, 255, 255, 150), width=max(2, int(3 * escala)))
                cor = (255, 255, 255, 120)
            d.text((x, y + int(66 * escala)), s["ano"], font=fy, fill=cor, anchor="ms")
    brilho = brilho.filter(ImageFilter.GaussianBlur(int(14 * escala)))
    brilho.alpha_composite(im)
    im = _sombra(brilho, raio=int(16 * escala), forca=0.5, dy=int(6 * escala))
    im.save(destino)
    return im.size


def gradiente_png(W, H, y0, destino, forca=200):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = im.load()
    for y in range(y0, H):
        a = int(forca * ((y - y0) / (H - y0)) ** 1.4)
        for x in range(W):
            px[x, y] = (0, 0, 0, a)
    im.save(destino)


def logo_yt(destino):
    """Logo MEUPS (caixa azul do PSD) colado na borda direita, 80% do tamanho."""
    psd = Image.open(os.path.join(TEMPLATE, "assets", "layout_overlay_completo.png")).convert("RGBA")
    logo = psd.crop((584, 220, 1080, 316))
    logo = logo.resize((int(496 * 0.8), int(96 * 0.8)), Image.LANCZOS)
    logo.save(destino)
    return logo.size


def card_texto(W, H, linhas, f_bold, destino, fundo=None, escala=1.0):
    """Card com linhas [(texto, 'azul'|'branco', cap_px)] centralizadas em caixas."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)) if fundo is None else fundo.convert("RGBA").resize((W, H))
    d = ImageDraw.Draw(im)
    blocos = []
    for txt, cor, cap in linhas:
        f = fonte(f_bold, int(cap * escala))
        pad = int(cap * 0.55 * escala)
        w = int(f.getlength(txt) + 2 * pad)
        h = int(cap * escala * 1.9)
        blocos.append((txt, cor, f, w, h))
    tot = sum(b[4] for b in blocos) + int(8 * escala) * (len(blocos) - 1)
    y = (H - tot) // 2
    for txt, cor, f, w, h in blocos:
        x = (W - w) // 2
        fill, tc = (AZUL, BRANCO) if cor == "azul" else (BRANCO, AZUL)
        d.rounded_rectangle((x, y, x + w, y + h), int(12 * escala), fill=fill)
        d.text((W // 2, y + h // 2), txt, font=f, fill=tc, anchor="mm")
        y += h + int(8 * escala)
    im.save(destino)


# ---------------------------------------------------------------- vídeo
def normalizar(seg, base, destino):
    """Junta os trechos do jogo em 1920x1080/30fps com flash branco e fades de áudio."""
    partes = []
    for k, tr in enumerate(seg["trechos"]):
        ini, fim = tr[0], tr[1]
        arq = os.path.join(base, tr[2] if len(tr) > 2 else seg["arquivo"])
        p = destino.replace(".mp4", f"_p{k}.mp4")
        dur = fim - ini
        crop = f"crop={seg['crop']}," if seg.get("crop") else ""
        vf = (f"{crop}scale=1920:1080:force_original_aspect_ratio=decrease,"
              f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={FPS},format=yuv420p")
        af = (f"aresample=48000,aformat=channel_layouts=stereo,"
              f"afade=t=in:st=0:d=0.12,afade=t=out:st={max(dur - 0.25, 0)}:d=0.25")
        if k > 0:
            vf += ",fade=t=in:st=0:d=0.2"
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", str(ini), "-t", str(dur),
               "-i", arq,
               "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo"]
        # se o arquivo não tiver áudio, usa silêncio
        tem_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                    "stream=index", "-of", "csv=p=0", arq],
                                   capture_output=True, text=True).stdout.strip()
        amap = "0:a:0" if tem_audio else "1:a"
        cmd += ["-filter_complex", f"[0:v]{vf}[v];[{amap}]{af}[a]", "-map", "[v]", "-map", "[a]",
                "-t", str(dur), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                "-c:a", "pcm_s16le", destino.replace(".mp4", f"_p{k}.mkv")]
        run(cmd)
        partes.append(destino.replace(".mp4", f"_p{k}.mkv"))
    lista = destino.replace(".mp4", "_lista.txt")
    with open(lista, "w") as f:
        for p in partes:
            f.write(f"file '{os.path.abspath(p)}'\n")
    vol = seg.get("volume", 1.0)
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista,
         "-vf", "fade=t=in:st=0:d=0.25:color=white",
         "-af", f"volume={vol},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", destino.replace(".mp4", ".mkv")])
    for p in partes:
        os.remove(p)
    return destino.replace(".mp4", ".mkv")


def duracao(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", p], capture_output=True, text=True).stdout)


EASE = "(1-pow(1-min(max((t-{t0})/{d},0),1),3))"


ALFA = ("format=rgba,fade=t=in:st=0.3:d=0.45:alpha=1,"
        "fade=t=out:st={fo}:d=0.4:alpha=1")
SOBE = "{y}+24*(1-{e})"


def segmento_yt(norm, tag, tag_wh, tl, tl_wh, grad, logo, logo_wh, saida, dur, primeiro):
    tw, th = tag_wh
    y_tl = 1080 - tl_wh[1] - 12
    y_tag = SOBE.format(y=y_tl - th + 6, e=EASE.format(t0=0.3, d=0.5))
    lw, lh = logo_wh
    x_logo = f"1920-{lw}+{lw}*(1-{EASE.format(t0=0.2, d=0.5)})" if primeiro else f"1920-{lw}"
    fc = (f"[0:v][1:v]overlay=0:0[a];"
          f"[a][2:v]overlay=0:{y_tl}[b];"
          f"[3:v]{ALFA.format(fo=dur - 0.55)}[tg];"
          f"[b][tg]overlay=x=0:y='{y_tag}':eval=frame[c];"
          f"[c][4:v]overlay=x='{x_logo}':y=40:eval=frame,format=yuv420p[v]")
    run(["ffmpeg", "-y", "-v", "error", "-i", norm, "-loop", "1", "-i", grad, "-loop", "1", "-i", tl,
         "-loop", "1", "-framerate", str(FPS), "-i", tag, "-loop", "1", "-i", logo, "-filter_complex", fc,
         "-map", "[v]", "-map", "0:a", "-t", str(dur), "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-r", str(FPS), "-c:a", "pcm_s16le", "-ar", "48000", saida])


def segmento_vertical(norm, tag, tag_wh, tl, tl_wh, saida, dur):
    tw, th = tag_wh
    TOP = 420  # vídeo 1080x608 entre o logo (até y316) e o título (y1221)
    y_tag = SOBE.format(y=TOP + 608 + 6, e=EASE.format(t0=0.3, d=0.5))
    y_tl = 1490  # painel logo abaixo do título (que vai até y1470) e dentro da área do feed (até 1635)
    fc = (f"[0:v]split[s1][s2];"
          f"[s1]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          f"boxblur=40:2,eq=brightness=-0.15:saturation=1.1[fb];"
          f"[s2]scale=1080:-2[fg];[fb][fg]overlay=0:{TOP}[a];"
          f"[1:v]{ALFA.format(fo=dur - 0.55)}[tg];"
          f"[a][tg]overlay=x=0:y='{y_tag}':eval=frame[b];"
          f"[b][2:v]overlay=0:{y_tl},format=yuv420p[v]")
    run(["ffmpeg", "-y", "-v", "error", "-i", norm, "-loop", "1", "-framerate", str(FPS), "-i", tag,
         "-loop", "1", "-i", tl,
         "-filter_complex", fc, "-map", "[v]", "-map", "0:a", "-t", str(dur), "-c:v", "libx264",
         "-preset", "medium", "-crf", "18", "-r", str(FPS), "-c:a", "pcm_s16le",
         "-ar", "48000", saida])


def card_video(png, dur, saida, W, H, musica_de=None, fade_out=True):
    vf = f"fade=t=in:st=0:d=0.3"
    if fade_out:
        vf += f",fade=t=out:st={dur - 0.5}:d=0.5"
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", png,
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-vf", vf + ",format=yuv420p",
         "-t", str(dur), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS),
         "-c:a", "pcm_s16le", "-ar", "48000", saida])


def concat(partes, saida):
    lista = saida + ".txt"
    with open(lista, "w") as f:
        for p in partes:
            f.write(f"file '{os.path.abspath(p)}'\n")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista,
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", saida])
    os.remove(lista)


def frame(video, t, destino):
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", destino])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("saida_dir")
    ap.add_argument("--base", required=True, help="pasta com as intros")
    ap.add_argument("--fonte", default=os.path.join(TEMPLATE, "fonts", "BarlowCondensed-ExtraBold.ttf"))
    ap.add_argument("--fonte-light", default=os.path.join(TEMPLATE, "fonts", "BarlowCondensed-Light.ttf"))
    ap.add_argument("--so-quadros", action="store_true", help="só gera prévias PNG de cada trecho")
    ap.add_argument("--so", help="renderiza só estes índices (ex: 0,3)")
    a = ap.parse_args()

    cfg = json.load(open(a.config, encoding="utf-8"))
    segs = cfg["segmentos"]
    tmp = os.path.join(a.saida_dir, "_tmp")
    os.makedirs(tmp, exist_ok=True)

    if a.so_quadros:
        for i, s in enumerate(segs):
            for k, tr in enumerate(s["trechos"]):
                ini, fim = tr[0], tr[1]
                for frac in (0.1, 0.5, 0.9):
                    t = ini + (fim - ini) * frac
                    frame(os.path.join(a.base, tr[2] if len(tr) > 2 else s["arquivo"]), t,
                          os.path.join(tmp, f"q{i:02d}_t{k}_{int(frac * 100)}.png"))
        return

    grad = os.path.join(tmp, "grad.png")
    gradiente_png(1920, 1080, 620, grad)
    logo = os.path.join(tmp, "logo.png")
    logo_wh = logo_yt(logo)

    so = set(int(x) for x in a.so.split(",")) if a.so else None
    yt_partes, vt_partes = [], []

    # card de abertura (YouTube)
    ab = os.path.join(tmp, "abertura.png")
    card_texto(1920, 1080, [(cfg["abertura"][0], "branco", 46), (cfg["abertura"][1], "azul", 96),
                            (cfg["abertura"][2], "azul", 96)], a.fonte, ab,
               fundo=Image.new("RGB", (1920, 1080), (8, 10, 18)))
    ab_v = os.path.join(tmp, "abertura.mkv")
    card_video(ab, cfg.get("dur_abertura", 2.5), ab_v, 1920, 1080)
    yt_partes.append(ab_v)

    for i, s in enumerate(segs):
        norm_out = os.path.join(tmp, f"n{i:02d}.mp4")
        yt_out = os.path.join(tmp, f"yt{i:02d}.mkv")
        vt_out = os.path.join(tmp, f"vt{i:02d}.mkv")
        if so is None or i in so or not os.path.exists(yt_out):
            norm = normalizar(s, a.base, norm_out)
            dur = duracao(norm)
            tag = os.path.join(tmp, f"tag_yt{i:02d}.png")
            twh = tag_png(s["nome"], s["ano"], i + 1, len(segs), a.fonte, a.fonte_light, 1.0, tag, 1920)
            tl = os.path.join(tmp, f"tl_yt{i:02d}.png")
            tlwh = timeline_png(segs, i, 1920, a.fonte, a.fonte_light, 0.85, tl)
            segmento_yt(norm, tag, twh, tl, tlwh, grad, logo, logo_wh, yt_out, dur, i == 0)
            tagv = os.path.join(tmp, f"tag_vt{i:02d}.png")
            twhv = tag_png(s["nome"], s["ano"], i + 1, len(segs), a.fonte, a.fonte_light, 0.9, tagv, 1080)
            tlv = os.path.join(tmp, f"tl_vt{i:02d}.png")
            tlwhv = timeline_png(segs, i, 1080, a.fonte, a.fonte_light, 0.72, tlv)
            segmento_vertical(norm, tagv, twhv, tlv, tlwhv, vt_out, dur)
            if i == len(segs) - 1:
                frame(norm, dur - 0.1, os.path.join(tmp, "ultimo.png"))
        yt_partes.append(yt_out)
        vt_partes.append(vt_out)

    # card final com pergunta (CTA de comentário) sobre o último quadro desfocado
    ult = Image.open(os.path.join(tmp, "ultimo.png")).convert("RGB")
    fundo_yt = ult.resize((1920, 1080)).filter(ImageFilter.GaussianBlur(24)).point(lambda v: int(v * 0.55))
    fim_png = os.path.join(tmp, "final_yt.png")
    card_texto(1920, 1080, [(cfg["final"][0], "azul", 84), (cfg["final"][1], "branco", 56)],
               a.fonte, fim_png, fundo=fundo_yt)
    im = Image.open(fim_png).convert("RGBA")
    im.alpha_composite(Image.open(logo).convert("RGBA"), (1920 - logo_wh[0], 40))
    im.save(fim_png)
    fim_v = os.path.join(tmp, "final_yt.mkv")
    card_video(fim_png, cfg.get("dur_final", 4), fim_v, 1920, 1080)
    yt_partes.append(fim_v)

    fundo_vt = ult.resize((3413, 1920)).crop((1166, 0, 2246, 1920)).filter(
        ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.55))
    fim_png_v = os.path.join(tmp, "final_vt.png")
    card_texto(1080, 1920, [(cfg["final_vertical"][0], "azul", 62), (cfg["final_vertical"][1], "azul", 62),
                            (cfg["final_vertical"][2], "branco", 44)], a.fonte, fim_png_v, fundo=fundo_vt)
    fim_vv = os.path.join(tmp, "final_vt.mkv")
    card_video(fim_png_v, cfg.get("dur_final", 4), fim_vv, 1080, 1920)
    vt_partes.append(fim_vv)

    concat(yt_partes, os.path.join(a.saida_dir, cfg["saida_yt"]))
    concat(vt_partes, os.path.join(a.saida_dir, cfg["saida_vertical_sem_layout"]))
    print("OK")


if __name__ == "__main__":
    main()

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
def tag_png(nome, ano, idx, total, f_bold, f_light, escala, destino):
    """Caixa azul com o nome do jogo + caixa branca com o ano (estilo chapéu MEUPS)."""
    fn = fonte(f_bold, int(64 * escala))
    fa = fonte(f_bold, int(34 * escala))
    fc = fonte(f_light, int(26 * escala))
    pad = int(36 * escala)
    h_nome = int(112 * escala)
    h_ano = int(62 * escala)
    contador = f"{idx:02d}/{total:02d}"
    w_nome = int(pad * 2 + fn.getlength(nome))
    w_ano = int(pad * 2 + fa.getlength(ano) + fc.getlength(contador) + pad)
    W = max(w_nome, w_ano) + 10
    H = h_ano + h_nome
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(14 * escala)
    d.rounded_rectangle((0, 0, w_ano - 1, h_ano - 1), r, fill=BRANCO, corners=(False, True, False, False))
    d.text((pad, h_ano - int(17 * escala)), ano, font=fa, fill=AZUL, anchor="ls")
    d.text((pad * 1.6 + fa.getlength(ano), h_ano - int(18 * escala)), contador, font=fc,
           fill=(0, 91, 215, 170), anchor="ls")
    d.rounded_rectangle((0, h_ano - r, w_nome - 1, H - 1), r, fill=AZUL, corners=(False, True, True, False))
    d.text((pad, H - int(26 * escala)), nome, font=fn, fill=BRANCO, anchor="ls")
    # sombra suave
    sombra = Image.new("RGBA", (W + 40, H + 40), (0, 0, 0, 0))
    a = im.split()[3].point(lambda v: int(v * 0.45))
    sombra.paste(Image.new("RGBA", im.size, (0, 0, 0, 255)), (20, 26), a)
    sombra = sombra.filter(ImageFilter.GaussianBlur(10))
    sombra.alpha_composite(im, (20, 20))
    sombra.save(destino)
    return sombra.size


def timeline_png(segs, atual, largura, f_bold, f_light, escala, destino):
    """Linha do tempo com um ponto por jogo: passados cheios, atual azul grande."""
    n = len(segs)
    m = int(70 * escala)
    H = int(118 * escala)
    im = Image.new("RGBA", (largura, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fy = fonte(f_bold, int(20 * escala))
    fy_at = fonte(f_bold, int(26 * escala))
    y = int(40 * escala)
    xs = [m + (largura - 2 * m) * i / (n - 1) for i in range(n)]
    lw = max(2, int(4 * escala))
    d.line((xs[0], y, xs[-1], y), fill=(255, 255, 255, 90), width=lw)
    d.line((xs[0], y, xs[atual], y), fill=(255, 255, 255, 235), width=lw)
    for i, (x, s) in enumerate(zip(xs, segs)):
        if i == atual:
            R = int(19 * escala)
            d.ellipse((x - R - 6 * escala, y - R - 6 * escala, x + R + 6 * escala, y + R + 6 * escala),
                      fill=(255, 255, 255, 255))
            d.ellipse((x - R, y - R, x + R, y + R), fill=AZUL)
            d.text((x, y + int(64 * escala)), s["ano"], font=fy_at, fill=BRANCO, anchor="ms")
        elif i < atual:
            R = int(9 * escala)
            d.ellipse((x - R, y - R, x + R, y + R), fill=BRANCO)
            d.text((x, y + int(56 * escala)), s["ano"], font=fy, fill=(255, 255, 255, 200), anchor="ms")
        else:
            R = int(9 * escala)
            d.ellipse((x - R, y - R, x + R, y + R), fill=(20, 20, 20, 200),
                      outline=(255, 255, 255, 150), width=max(2, int(3 * escala)))
            d.text((x, y + int(56 * escala)), s["ano"], font=fy, fill=(255, 255, 255, 120), anchor="ms")
    # contorno escuro para ler sobre fundo claro
    sombra = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sombra.paste(Image.new("RGBA", im.size, (0, 0, 0, 255)), (0, 0), im.split()[3].point(lambda v: int(v * 0.6)))
    sombra = sombra.filter(ImageFilter.GaussianBlur(6))
    sombra.alpha_composite(im)
    sombra.save(destino)


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


def segmento_yt(norm, tag, tag_wh, tl, grad, logo, logo_wh, saida, dur, primeiro):
    tw, th = tag_wh
    x_in = EASE.format(t0=0.35, d=0.5)
    x_out = EASE.format(t0=dur - 0.6, d=0.45)
    x_tag = f"-{tw}+({tw}+40)*{x_in}-({tw}+60)*{x_out}"
    y_tag = 1080 - 150 - th
    lw, lh = logo_wh
    x_logo = f"1920-{lw}+{lw}*(1-{EASE.format(t0=0.2, d=0.5)})" if primeiro else f"1920-{lw}"
    fc = (f"[0:v][1:v]overlay=0:0[a];"
          f"[a][2:v]overlay=0:H-h-8:eval=frame[b];"
          f"[b][3:v]overlay=x='{x_tag}':y={y_tag}:eval=frame[c];"
          f"[c][4:v]overlay=x='{x_logo}':y=40:eval=frame,format=yuv420p[v]")
    run(["ffmpeg", "-y", "-v", "error", "-i", norm, "-loop", "1", "-i", grad, "-loop", "1", "-i", tl,
         "-loop", "1", "-i", tag, "-loop", "1", "-i", logo, "-filter_complex", fc,
         "-map", "[v]", "-map", "0:a", "-t", str(dur), "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-r", str(FPS), "-c:a", "pcm_s16le", "-ar", "48000", saida])


def segmento_vertical(norm, tag, tag_wh, tl, saida, dur):
    tw, th = tag_wh
    x_in = EASE.format(t0=0.35, d=0.5)
    x_out = EASE.format(t0=dur - 0.6, d=0.45)
    x_tag = f"-{tw}+{tw}*{x_in}-({tw}+20)*{x_out}"
    TOP = 420  # vídeo 1080x608 entre o logo (até y316) e o título (y1221)
    fc = (f"[0:v]split[s1][s2];"
          f"[s1]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          f"boxblur=40:2,eq=brightness=-0.15:saturation=1.1[fb];"
          f"[s2]scale=1080:-2[fg];[fb][fg]overlay=0:{TOP}[a];"
          f"[a][1:v]overlay=x='{x_tag}':y={TOP + 608 + 20}:eval=frame[b];"
          f"[b][2:v]overlay=0:1505,format=yuv420p[v]")
    run(["ffmpeg", "-y", "-v", "error", "-i", norm, "-loop", "1", "-i", tag, "-loop", "1", "-i", tl,
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
            twh = tag_png(s["nome"], s["ano"], i + 1, len(segs), a.fonte, a.fonte_light, 1.0, tag)
            tl = os.path.join(tmp, f"tl_yt{i:02d}.png")
            timeline_png(segs, i, 1920, a.fonte, a.fonte_light, 1.0, tl)
            segmento_yt(norm, tag, twh, tl, grad, logo, logo_wh, yt_out, dur, i == 0)
            tagv = os.path.join(tmp, f"tag_vt{i:02d}.png")
            twhv = tag_png(s["nome"], s["ano"], i + 1, len(segs), a.fonte, a.fonte_light, 0.95, tagv)
            tlv = os.path.join(tmp, f"tl_vt{i:02d}.png")
            timeline_png(segs, i, 1080, a.fonte, a.fonte_light, 0.62, tlv)
            segmento_vertical(norm, tagv, twhv, tlv, vt_out, dur)
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

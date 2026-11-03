#!/usr/bin/env python3
"""Renderiza um vídeo 1080x1920 no layout MEUPS "video legenda".

Exemplo:
  python3 render.py entrada.mp4 saida.mp4 \
      --chapeu "GTA NA VIDA REAL" \
      --titulo "CARRO SEM RODA TENTA FUGIR DA PM EM SUZANO" \
      --inicio 0 --fim 46 \
      --crop 619:0:681:1080 \
      --musica trilha.wav

--crop recorta só a parte útil do vídeo original, no formato x:y:largura:altura.
Sem --crop o vídeo é cortado no centro para preencher 9:16.
"""
import argparse
import json
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920


def carregar_layout():
    with open(os.path.join(AQUI, "layout.json"), encoding="utf-8") as f:
        return json.load(f)


def fonte_para_altura_de_caixa_alta(caminho, cap_px):
    """Escolhe o tamanho da fonte para que a letra maiúscula tenha cap_px de altura,
    igual ao PSD (Novecento 60px -> 44px de caixa alta; 40px -> 28px)."""
    tam = cap_px
    for _ in range(4):
        f = ImageFont.truetype(caminho, tam)
        x0, y0, x1, y1 = f.getbbox("H", anchor="ls")
        tam = round(tam * cap_px / (y1 - y0))
    return ImageFont.truetype(caminho, tam)


def quebrar(texto, fonte, largura_max, max_linhas):
    palavras = texto.split()
    linhas, atual = [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if fonte.getlength(teste) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    linhas.append(atual)
    if len(linhas) > max_linhas:
        raise SystemExit(f"Título passa de {max_linhas} linhas: {linhas}")
    return linhas


def caixa(draw, xy, cor, raio, cantos):
    draw.rounded_rectangle(xy, raio, fill=cor, corners=cantos)


def gerar_overlays(lay, chapeu, titulo, fonte_path, pasta, credito=None):
    azul = lay["cores"]["azul_meups"]
    branco = lay["cores"]["branco"]
    f_tit = fonte_para_altura_de_caixa_alta(fonte_path, 44)
    f_chap = fonte_para_altura_de_caixa_alta(fonte_path, 28)

    # --- logo (recortado do PSD, idêntico ao original) ---
    psd_overlay = Image.open(os.path.join(AQUI, "assets/layout_overlay_completo.png")).convert("RGBA")
    logo = psd_overlay.crop((584, 220, 1080, 316))
    logo.save(os.path.join(pasta, "logo.png"))

    # --- lower third (chapéu + título), largura acompanha o texto ---
    linhas = quebrar(titulo.upper(), f_tit, 736, 2)
    larg_txt = max(f_tit.getlength(l) for l in linhas)
    larg_tit = int(80 + larg_txt + 36)
    larg_chap = int(80 + f_chap.getlength(chapeu.upper()) + 36)

    y0 = 1221  # topo do chapéu no PSD
    alt = 1470 - y0 if len(linhas) == 2 else 1470 - y0 - 67
    f_cred = fonte_para_altura_de_caixa_alta(fonte_path, 21)
    larg_cred = int(80 + f_cred.getlength(credito) + 20) if credito else 0
    alt_total = alt + (46 if credito else 0)
    lt = Image.new("RGBA", (max(larg_tit, larg_chap, larg_cred), alt_total), (0, 0, 0, 0))
    d = ImageDraw.Draw(lt)
    caixa(d, (0, 0, larg_chap - 1, 1303 - y0 - 1), branco, 12, (False, True, False, False))
    caixa(d, (0, 1285 - y0, larg_tit - 1, alt - 1), azul, 16, (False, True, True, False))
    d.text((80, 1271 - y0), chapeu.upper(), font=f_chap, fill=azul, anchor="ls")
    for i, l in enumerate(linhas):
        d.text((80, 1372 - y0 + i * 67), l, font=f_tit, fill=branco, anchor="ls")
    if credito:
        # crédito pequeno logo abaixo do título, dentro da margem de segurança (acima de y=1500)
        base = alt + 30
        d.text((82, base + 2), credito, font=f_cred, fill=(0, 0, 0, 160), anchor="ls")
        d.text((80, base), credito, font=f_cred, fill=branco, anchor="ls")
    lt.save(os.path.join(pasta, "lower.png"))
    return lt.size, y0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("saida")
    ap.add_argument("--chapeu", required=True)
    ap.add_argument("--titulo", required=True)
    ap.add_argument("--inicio", type=float, default=0)
    ap.add_argument("--fim", type=float)
    ap.add_argument("--crop", help="x:y:w:h da área útil do vídeo original")
    ap.add_argument("--modo", choices=["preencher", "desfoque"], default="preencher",
                    help="preencher: corta o vídeo para ocupar 9:16; desfoque: vídeo inteiro na largura "
                         "com fundo desfocado (bom para vídeos quadrados/horizontais)")
    ap.add_argument("--pos-y", type=int, help="modo desfoque: topo do vídeo (padrão: centralizado)")
    ap.add_argument("--legendas", help="JSON com as frases da legenda animada (ver legendas.py)")
    ap.add_argument("--credito", help='texto pequeno de crédito, ex: "VÍDEO DE: @perfil (instagram)"')
    ap.add_argument("--musica", help="arquivo de áudio da trilha")
    ap.add_argument("--vol-musica", type=float, default=0.8)
    ap.add_argument("--vol-original", type=float, default=0.35)
    ap.add_argument("--fonte", default=os.path.join(AQUI, "fonts/BarlowCondensed-ExtraBold.ttf"),
                    help="use a Novecento-CondUltraBold.otf aqui quando tiver o arquivo")
    a = ap.parse_args()

    lay = carregar_layout()
    pasta = tempfile.mkdtemp()
    (lw, lh), ly = gerar_overlays(lay, a.chapeu, a.titulo, a.fonte, pasta, a.credito)

    if a.fim is None:
        total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                      "-of", "csv=p=0", a.entrada], capture_output=True, text=True).stdout)
        a.fim = total
    dur = a.fim - a.inicio
    fps = 30
    if a.crop:
        x, y, w, h = a.crop.split(":")
        crop = f"crop={w}:{h}:{x}:{y},"
    else:
        crop = ""
    # preenche 9:16 cortando o excesso, sem bordas pretas
    fundo = f"[0:v]{crop}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps}[bg]"
    if a.modo == "desfoque":
        y = a.pos_y if a.pos_y is not None else "(H-h)/2"
        fundo = (f"[0:v]{crop}setsar=1,fps={fps},split[s1][s2];"
                 f"[s1]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 f"boxblur=40:2,eq=brightness=-0.12[fb];"
                 f"[s2]scale={W}:-2[fg];[fb][fg]overlay=0:{y}[bg]")

    # animações: logo entra pela direita, lower third pela esquerda (ease-out)
    ease = "(1-pow(1-min(max((t-{t0})/{d},0),1),3))"
    x_logo = f"584+(496)*(1-{ease.format(t0=0.2, d=0.5)})"
    x_low = f"-{lw}+{lw}*{ease.format(t0=0.5, d=0.6)}"

    if a.legendas:
        fundo += ";[bg][LEG]overlay=0:0:shortest=1[bgl]"
        base_v = "bgl"
    else:
        base_v = "bg"
    fc = [
        fundo,
        f"[{base_v}][1:v]overlay=x='{x_logo}':y=220:eval=frame:shortest=1[v1]",
        f"[v1][2:v]overlay=x='{x_low}':y={ly}:eval=frame:shortest=1,format=yuv420p[v]",
    ]
    cmd = ["ffmpeg", "-y", "-ss", str(a.inicio)]
    cmd += ["-t", str(dur)]
    cmd += ["-i", a.entrada,
            "-loop", "1", "-i", os.path.join(pasta, "logo.png"),
            "-loop", "1", "-i", os.path.join(pasta, "lower.png")]
    prox = 3
    if a.musica:
        cmd += ["-i", a.musica]
        prox += 1
        fc.append(f"[0:a]volume={a.vol_original}[ao];[3:a]volume={a.vol_musica}[am];"
                  f"[ao][am]amix=inputs=2:duration=first:normalize=0,"
                  f"alimiter=limit=0.89,afade=t=out:st={max(dur - 1.5, 0)}:d=1.5[a]")
        amap = "[a]"
    else:
        amap = "0:a?"
    proc_in = None
    if a.legendas:
        cmd += ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "pipe:0"]
        fc[0] = fc[0].replace("[LEG]", f"[{prox}:v]")
        proc_in = subprocess.PIPE
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", amap,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]
    cmd += ["-t", str(dur)]
    cmd.append(a.saida)
    if not a.legendas:
        subprocess.run(cmd, check=True)
        return
    from legendas import gerar_frames
    proc = subprocess.Popen(cmd, stdin=proc_in)
    try:
        for quadro in gerar_frames(a.legendas, a.fonte, lay["cores"]["azul_meups"], fps,
                                   int(dur * fps) + fps):
            proc.stdin.write(quadro)
    except BrokenPipeError:
        pass
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg falhou")


if __name__ == "__main__":
    main()

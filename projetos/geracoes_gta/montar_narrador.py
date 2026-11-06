"""Monta o DIA 7 (narrador de cada GTA) a partir dos comerciais de TV.

Uso: python montar_narrador.py <pasta _fontes/narrador> <saida.mp4>
Precisa de ffmpeg no PATH e Pillow. Usa template/render.py deste repositório.
Fontes esperadas na pasta: tv_vicecity.mp4, tv_sanandreas.mp4, tv_gta4.mp4,
tv_gta5.mp4, tv_gta6_nbc_corte2.mp4 (46-56 s do spot NBC),
gta6_46_56_vocals.m4a e gta6_46_56_resto.m4a (stems demucs do mesmo trecho).
"""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(AQUI, "..", "..", "template", "render.py")

FUNDO = ("[0:v]{crop}split[a][b];"
         "[a]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
         "boxblur=20:2,eq=brightness=-0.08[bg];"
         "[b]scale=1280:720:force_original_aspect_ratio=decrease[fg];"
         "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[v]")

# arquivo, inicio, duracao, crop, fade de saida (inicio, dur), ganho dB
PECAS = [
    ("tv_vicecity.mp4", 23.0, 2.0, "320:170:0:38", None, 5.6),
    ("tv_vicecity.mp4", 25.0, 3.7, "", (3.4, 0.3), 5.6),
    ("tv_sanandreas.mp4", 21.5, 3.8, "428:242:22:40", None, -2.8),
    ("tv_sanandreas.mp4", 25.3, 3.95, "", (3.75, 0.2), -2.8),
    ("tv_gta4.mp4", 57.0, 7.0, "", (6.8, 0.2), 3.0),
    ("tv_gta5.mp4", 19.0, 6.45, "1280:576:0:72", (6.3, 0.15), -3.1),
]


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def main(src, saida):
    tmp = tempfile.mkdtemp()
    partes = []
    for i, (arq, ss, t, crop, fade, ganho) in enumerate(PECAS):
        out = os.path.join(tmp, f"p{i}.mkv")
        af = "aresample=48000,aformat=channel_layouts=stereo"
        if fade:
            af += f",afade=t=out:st={fade[0]}:d={fade[1]}"
        af += f",volume={ganho}dB,alimiter=limit=0.95"
        ff("-ss", str(ss), "-t", str(t), "-i", os.path.join(src, arq),
           "-filter_complex", FUNDO.format(crop=f"crop={crop}," if crop else ""),
           "-map", "[v]", "-map", "0:a", "-af", af,
           "-c:v", "libx264", "-crf", "16", "-c:a", "pcm_s16le", out)
        partes.append(out)
    # GTA VI: voz do narrador (stem) bem na frente da trilha
    out = os.path.join(tmp, "p6.mkv")
    ff("-ss", "0.8", "-t", "8.7", "-i", os.path.join(src, "tv_gta6_nbc_corte2.mp4"),
       "-ss", "0.8", "-t", "8.7", "-i", os.path.join(src, "gta6_46_56_vocals.m4a"),
       "-ss", "0.8", "-t", "8.7", "-i", os.path.join(src, "gta6_46_56_resto.m4a"),
       "-filter_complex",
       "[0:v]scale=1280:720,setsar=1,fps=30,format=yuv420p[v];"
       "[1:a]aresample=48000,volume=21dB,acompressor=threshold=-18dB:ratio=3:attack=5:release=120,volume=2dB[vo];"
       "[2:a]aresample=48000,volume=13dB[re];"
       "[vo][re]amix=inputs=2:normalize=0,alimiter=limit=0.95,afade=t=in:d=0.1,afade=t=out:st=8.2:d=0.5[a]",
       "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-c:a", "pcm_s16le", out)
    partes.append(out)

    lista = os.path.join(tmp, "lista.txt")
    with open(lista, "w") as f:
        for p in partes:
            f.write(f"file '{p}'\n".replace("\\", "/"))
    base = os.path.join(tmp, "narrador.mp4")
    ff("-f", "concat", "-safe", "0", "-i", lista, "-c:v", "libx264", "-crf", "16",
       "-c:a", "aac", "-b:a", "192k", base)

    leg = os.path.join(AQUI, "legendas_narrador.json")
    subprocess.run([sys.executable, RENDER, base, saida, "--chapeu", "GTA VI",
                    "--titulo", "20 ANOS DEPOIS E A ROCKSTAR|AINDA USA O MESMO NARRADOR",
                    "--modo", "desfoque", "--pos-y", "480", "--legendas", leg],
                   check=True, cwd=os.path.dirname(RENDER))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]))

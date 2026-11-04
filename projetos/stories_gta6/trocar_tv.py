#!/usr/bin/env python3
"""Troca a imagem da TV do meme de stories (Code Veronica) por prints do GTA VI.

python3 trocar_tv.py entrada.mp4 pasta_prints saida.mp4 [--preview]
Para cada story: linhas da borda de cima/baixo da TV (medidas no 1º quadro), lados,
imagem + foco. O movimento da câmera é seguido com SIFT+RANSAC contra o 1º quadro
do story, ignorando legenda/cabeçalho (que são fixos na tela).
"""
import sys, os, json, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE = os.path.join(AQUI, "../../template/fonts/BarlowCondensed-ExtraBold.ttf")
W, H = 720, 1176

# (ini, fim) em quadros a 60 fps, linhas y = a + b*x, lados como (x no meio, inclinação dx/dy)
SHOTS = [
    dict(f=(0, 168), top=(350, 0.034), bot=(1320, -0.02), left=-330, right=1000,
         img="GTAVI_Jason_and_Lucia_01.jpg", foco=(0.62, 0.45), zoom=1.0, cap=(170, 245, 560, 355), ui="home"),
    dict(f=(168, 345), top=(10, 0.267), bot=(1120, -0.04), left=-600, right=1100, fora=True,
         img="GTAVI_Jason_and_Lucia_13.jpg", foco=(0.35, 0.4), zoom=1.15, cap=(190, 600, 530, 695)),
    dict(f=(345, 530), top=(86, 0.59), bot=(1330, 0.18), left=-420, right=1050,
         img="GTAVI_Jason_and_Lucia_11.jpg", foco=(1.0, 0.45), zoom=1.4, cap=(230, 185, 665, 310), ui="menu", capfull=True),
    dict(f=(530, 716), top=(82, 0.334), bot=(1091, -0.088), left=-260, right=657,
         img="GTAVI_Jason_and_Lucia_04.jpg", foco=(0.4, 0.45), zoom=1.0, cap=(130, 810, 680, 900)),
    dict(f=(716, 894), top=(-36, 0.4876), bot=(913.5, 0.25), left=-450, right=1300,
         img="GTAVI_Jason_and_Lucia_09.jpg", foco=(0.6, 0.5), zoom=1.0, cap=(55, 1025, 330, 1115)),
    dict(f=(894, 1065), top=(-100, 0.532), bot=(960, 0.24), left=-450, right=1300,
         fora=True, img="GTAVI_Jason_Duval_07.jpg", foco=(0.5, 0.45), zoom=1.0, cap=(220, 600, 505, 700)),
]
SEG = 116
TEMPOS = ["7 min", "6 min", "6 min", "5 min", "3 min", "56 s"]
LEGENDAS = ["dia de jogar GTA VI", "abrindo", "menu", "indo na loja de sapatos", "fugindo da polícia", "5 estrelas"]
CAP_Y = [300, 650, 268, 600, 1070, 652]  # centro vertical da legenda nova


def interseca(l1, xs):
    a, b = l1
    return np.array([xs, a + b * xs])


def quad(s):
    """Cantos TL,TR,BR,BL: lados perpendiculares à direção média das bordas."""
    ang = np.arctan((s["top"][1] + s["bot"][1]) / 2)
    d = np.array([-np.sin(ang), np.cos(ang)])  # direção "vertical" da tela
    pts = []
    for lado in (s["left"], s["right"]):
        # reta lateral passando por (lado, y_meio) com direção d
        ym = (s["top"][0] + s["top"][1] * lado + s["bot"][0] + s["bot"][1] * lado) / 2
        p0 = np.array([lado, ym])
        res = []
        for (a, b) in (s["top"], s["bot"]):
            # p0 + t d sobre y = a + b x
            t = (a + b * p0[0] - p0[1]) / (d[1] - b * d[0])
            res.append(p0 + t * d)
        pts.append(res)
    (tl, bl), (tr, br) = pts
    return np.float32([tl, tr, br, bl])


def tela_virtual(s, pasta, q):
    larg = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    alt = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    asp = larg / alt
    im = Image.open(os.path.join(pasta, s["img"])).convert("RGB")
    iw, ih = im.size
    ch = ih / s["zoom"]
    cw = min(iw, ch * asp)
    ch = cw / asp
    x0 = (iw - cw) * s["foco"][0]
    y0 = (ih - ch) * s["foco"][1]
    cr = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((1600, int(1600 / asp)), Image.LANCZOS)
    d = ImageDraw.Draw(cr)
    if s.get("ui") == "home":
        # tela inicial estilo console: nome do jogo e botão Jogar sobre a arte
        f1 = ImageFont.truetype(FONTE, 64)
        f2 = ImageFont.truetype(FONTE, 40)
        g = Image.linear_gradient("L").rotate(90).resize(cr.size)
        sombra = Image.new("RGB", cr.size, (0, 0, 0))
        cr = Image.composite(cr, sombra, g.point(lambda v: min(255, v * 2 + 60)))
        d = ImageDraw.Draw(cr)
        y = int(cr.height * 0.62)
        d.text((int(cr.width*0.36), y), "Grand Theft Auto VI", font=f1, fill="white")
        xb = int(cr.width*0.36)
        d.rounded_rectangle((xb, y + 95, xb + 220, y + 160), 32, fill="white")
        d.text((xb + 110, y + 128), "Jogar", font=f2, fill="black", anchor="mm")
    if s.get("ui") == "menu":
        f2 = ImageFont.truetype(FONTE, 46)
        d.text((cr.width * 0.52, cr.height * 0.86), "PRESSIONE QUALQUER BOTÃO", font=f2, fill="white", anchor="mm")
    return np.asarray(cr)[:, :, ::-1].copy()


def mascara_legenda(fr, box, lim=200):
    x0, y0, x1, y1 = box
    m = np.zeros(fr.shape[:2], np.uint8)
    roi = fr[y0:y1, x0:x1].astype(int)
    b, g, r = roi[..., 0], roi[..., 1], roi[..., 2]
    branco = (b > lim) & (g > lim) & (r > lim)
    verm = (r > 130) & (r - g > 70) & (r - b > 50)
    m[y0:y1, x0:x1] = ((branco | verm) * 255).astype(np.uint8)
    return cv2.dilate(m, np.ones((7, 7), np.uint8))


def main():
    ent, pasta, saida = sys.argv[1:4]
    preview = "--preview" in sys.argv
    cap = cv2.VideoCapture(ent)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
    print("quadros", len(frames))
    sift = cv2.SIFT_create(2000)
    esc = 0.5
    proc = None
    if not preview:
        proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                                 "-r", "60", "-i", "pipe:0", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
                                 "-pix_fmt", "yuv420p", saida], stdin=subprocess.PIPE)
    for k, s in enumerate(SHOTS):
        a, b = s["f"]
        b = min(b, len(frames))
        q0 = quad(s)
        tv = tela_virtual(s, pasta, q0)
        th, tw = tv.shape[:2]
        src = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]])
        ref = frames[a]
        mk = np.full((H, W), 255, np.uint8)
        mk[:100] = 0
        x0, y0, x1, y1 = s["cap"]
        mk[y0 - 10:y1 + 10, max(0, x0 - 10):x1 + 10] = 0
        if s.get("fora"):
            # conteúdo da TV se mexe sozinho: rastreia só a moldura/parede fora da tela
            tela = np.zeros((H, W), np.uint8)
            cv2.fillConvexPoly(tela, q0.astype(np.int32), 255)
            mk[cv2.dilate(tela, np.ones((15, 15), np.uint8)) > 0] = 0
        mks = cv2.resize(mk, None, fx=esc, fy=esc)
        kr, dr = sift.detectAndCompute(cv2.resize(cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY), None, fx=esc, fy=esc), mks)
        bf = cv2.BFMatcher()
        Hprev = np.eye(3)
        rng = [a] if preview else range(a, b)
        for i in rng:
            fr = frames[i]
            Hm = np.eye(3)
            if i != a:
                kf, df = sift.detectAndCompute(cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), None, fx=esc, fy=esc), mks)
                ok = False
                if df is not None and len(kf) > 10:
                    mt = [m for m, n in bf.knnMatch(dr, df, k=2) if m.distance < 0.75 * n.distance]
                    if len(mt) > (8 if s.get("fora") else 15):
                        p1 = np.float32([kr[m.queryIdx].pt for m in mt]) / esc
                        p2 = np.float32([kf[m.trainIdx].pt for m in mt]) / esc
                        Hm, inl = cv2.findHomography(p1, p2, cv2.RANSAC, 4.0)
                        ok = Hm is not None and inl.sum() > (6 if s.get("fora") else 12)
                if not ok:
                    Hm = Hprev
                # suaviza tremedeira do rastreio
                Hm = 0.6 * Hm + 0.4 * Hprev
            Hprev = Hm
            q = cv2.perspectiveTransform(q0[None], Hm)[0]
            M = cv2.getPerspectiveTransform(src, q)
            # apaga legenda e cabeçalho antigos
            base = fr.copy()
            mcap = mascara_legenda(fr, s["cap"])
            if s.get("capfull"):
                cx0, cy0, cx1, cy1 = s["cap"]
                mcap[cy0:cy1, cx0:cx1] = 255
            hdr = mascara_legenda(fr, (0, 0, W, 108), 150)
            cv2.circle(hdr, (51, 60), 33, 255, -1)
            base = cv2.inpaint(base, mcap | hdr, 6, cv2.INPAINT_TELEA)
            warp = cv2.warpPerspective(tv, M, (W, H), flags=cv2.INTER_LINEAR)
            m = cv2.warpPerspective(np.full((th, tw), 255, np.uint8), M, (W, H))
            m = cv2.GaussianBlur(m, (3, 3), 0).astype(np.float32)[..., None] / 255
            # look de tela filmada: leve desfoque, brilho do reflexo original
            warp = cv2.GaussianBlur(warp, (3, 3), 0).astype(np.float32)
            lum = cv2.GaussianBlur(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (0, 0), 25).astype(np.float32)
            warp = warp * 0.92 + (lum[..., None] - lum.mean()) * 0.15
            out = base * (1 - m) + np.clip(warp, 0, 255) * m
            out = out.astype(np.uint8)
            out = desenhar_ui(out, k, (i - a) / max(1, b - a))
            if preview:
                cv2.imwrite(saida.replace(".mp4", f"_{k}.png"), out)
            else:
                proc.stdin.write(out.tobytes())
        print("story", k, "ok")
    if proc:
        proc.stdin.close()
        proc.wait()


_cache = {}


def desenhar_ui(out, k, prog):
    if k not in _cache:
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        f = ImageFont.truetype(os.path.join(AQUI, "../../template/fonts/BarlowCondensed-ExtraBold.ttf"), 46)
        fm = ImageFont.truetype(os.path.join(AQUI, "../../template/fonts/BarlowCondensed-ExtraBold.ttf"), 26)
        txt = LEGENDAS[k]
        # quebra em 2 linhas se for comprida
        linhas = [txt]
        if f.getlength(txt) > 430:
            p = txt.split()
            meio = len(p) // 2 + 1
            linhas = [" ".join(p[:meio]), " ".join(p[meio:])]
        y = CAP_Y[k] - (len(linhas) - 1) * 26
        for j, l in enumerate(linhas):
            l2 = l + ("" if j < len(linhas) - 1 else " ")
            wl = f.getlength(l2) + (40 if j == len(linhas) - 1 else 0)
            x = W / 2 - wl / 2
            d.text((x + 2, y + 2), l2, font=f, fill=(0, 0, 0, 90), anchor="lm")
            d.text((x, y), l2, font=f, fill="white", anchor="lm")
            if j == len(linhas) - 1:
                desenha_coracao(d, x + f.getlength(l2) + 18, y - 2, 17)
            y += 52
        # cabeçalho do story (o original foi apagado)
        sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sombra)
        ds.rectangle((0, 0, W, 110), fill=(0, 0, 0, 0))
        g = Image.linear_gradient("L").resize((W, 120)).point(lambda v: int((255 - v) * 0.35))
        topo = Image.new("RGBA", (W, 120), (0, 0, 0, 255)); topo.putalpha(g)
        lay.alpha_composite(topo, (0, 0))
        d = ImageDraw.Draw(lay)
        for j in range(6):
            xs = 12 + j * SEG
            d.rounded_rectangle((xs, 10, xs + SEG - 6, 14), 2,
                                fill=(255, 255, 255, 255) if j < k else (255, 255, 255, 110))
        ic = Image.open(os.path.join(AQUI, "../../template/capa_assets/icone_meups.png")).convert("RGBA").resize((58, 58))
        mc = Image.new("L", (58, 58), 0); ImageDraw.Draw(mc).ellipse((0, 0, 57, 57), fill=255)
        ic.putalpha(Image.composite(ic.getchannel("A"), mc, mc) if False else mc)
        lay.alpha_composite(ic, (22, 31))
        fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 21)
        fr_ = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21)
        fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
        d.text((103, 46), "Seu story", font=fb, fill="white", anchor="lm")
        d.text((103 + fb.getlength("Seu story") + 14, 46), TEMPOS[k], font=fr_, fill=(255, 255, 255, 200), anchor="lm")
        d.text((103, 75), "♫  MEUPS · Vice City Nights  ›", font=fs, fill="white", anchor="lm")
        d.line((670, 46, 697, 73), fill="white", width=3); d.line((697, 46, 670, 73), fill="white", width=3)
        _cache[k] = lay
    im = Image.fromarray(out[:, :, ::-1]).convert("RGBA")
    im.alpha_composite(_cache[k])
    d = ImageDraw.Draw(im)
    x0 = 12 + k * SEG
    d.rounded_rectangle((x0, 10, x0 + (SEG - 6) * prog, 14), 2, fill=(255, 255, 255, 255))
    return np.asarray(im.convert("RGB"))[:, :, ::-1].copy()


def desenha_coracao(d, cx, cy, r):
    cor = (237, 28, 36, 255)
    d.ellipse((cx - r, cy - r * 0.9, cx, cy + r * 0.1), fill=cor)
    d.ellipse((cx, cy - r * 0.9, cx + r, cy + r * 0.1), fill=cor)
    d.polygon([(cx - r * 0.98, cy - 0.25 * r), (cx + r * 0.98, cy - 0.25 * r), (cx, cy + r)], fill=cor)


if __name__ == "__main__":
    main()

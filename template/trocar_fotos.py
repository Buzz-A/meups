#!/usr/bin/env python3
"""Troca fotos/objetos de um vídeo por imagens, acompanhando o movimento (tracking).

Feito para memes de desenho (ex.: Pica-Pau "Adeus parentes"): cada "slot" é uma
área retangular num quadro de referência em que a foto está parada. O script
segue essa área quadro a quadro (ECC com homografia) para frente e para trás,
então a imagem nova acompanha a foto quando ela é puxada, gira ou é jogada.

Modo "cor": em vez de ECC, segue uma mancha de cor (ex.: página laranja lisa,
sem textura para o ECC).

Uso: python3 trocar_fotos.py entrada.mp4 slots.json saida.mp4
slots.json: [{"img": "capa.png", "rect": [x0,y0,x1,y1], "ref": 4.6,
              "ini": 4.1, "fim": 5.65, "modo": "ecc"|"cor"}]
"""
import json
import subprocess
import sys

import cv2
import numpy as np


USAR_ROTACAO = False  # busca por rotação: experimental, gera falsos positivos em desenho


def ler_frames(caminho):
    cap = cv2.VideoCapture(caminho)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    return frames, fps


def estilizar(img_bgr, w, h):
    """Deixa a capa com cara de desenho/foto antiga: cores mais chapadas,
    menos saturação, leve desfoque para casar com a resolução do desenho."""
    # cobre a área (corte central) em 2x para filtrar com qualidade
    W, H = w * 2, h * 2
    ih, iw = img_bgr.shape[:2]
    s = max(W / iw, H / ih)
    r = cv2.resize(img_bgr, (int(iw * s + 1), int(ih * s + 1)), interpolation=cv2.INTER_AREA)
    y = (r.shape[0] - H) // 2
    x = (r.shape[1] - W) // 2
    r = r[y:y + H, x:x + W]
    r = cv2.bilateralFilter(r, 9, 60, 9)
    r = cv2.bilateralFilter(r, 9, 50, 9)
    hsv = cv2.cvtColor(r, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] *= 0.82
    hsv[..., 2] = hsv[..., 2] * 0.92 + 6
    r = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)
    # contorno escuro fino, como a moldura das fotos do desenho
    cv2.rectangle(r, (0, 0), (W - 1, H - 1), (35, 30, 30), 6)
    # cantoneiras do álbum (triângulos escuros nos cantos)
    c = int(min(W, H) * 0.16)
    cor = (40, 32, 34)
    for pts in ([(0, 0), (c, 0), (0, c)], [(W, 0), (W - c, 0), (W, c)],
                [(0, H), (c, H), (0, H - c)], [(W, H), (W - c, H), (W, H - c)]):
        cv2.fillConvexPoly(r, np.array(pts, np.int32), cor)
    r = cv2.resize(r, (w, h), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(r, (0, 0), 0.6)


def track_ecc(frames, rect, i_ref, i_ini, i_fim):
    x0, y0, x1, y1 = rect
    m = 10  # inclui a moldura laranja para dar textura ao tracking
    tx0, ty0 = max(0, x0 - m), max(0, y0 - m)
    tpl = cv2.cvtColor(frames[i_ref], cv2.COLOR_BGR2GRAY)[ty0:y1 + m, tx0:x1 + m].astype(np.float32)
    tpl = cv2.GaussianBlur(tpl, (0, 0), 1.2)
    base = np.array([[1, 0, tx0], [0, 1, ty0], [0, 0, 1]], np.float32)
    quads = {}
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5)
    # cantos da foto em coordenadas do template
    cantos = np.array([[x0 - tx0, y0 - ty0], [x1 - tx0, y0 - ty0],
                       [x1 - tx0, y1 - ty0], [x0 - tx0, y1 - ty0]], np.float32).reshape(-1, 1, 2)
    for passo, alvo in ((1, i_fim), (-1, i_ini)):
        H = base.copy()
        i = i_ref
        while (i <= alvo) if passo > 0 else (i >= alvo):
            img = cv2.GaussianBlur(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.2)
            try:
                cc, H = cv2.findTransformECC(tpl, img, H, cv2.MOTION_HOMOGRAPHY, crit, None, 5)
            except cv2.error:
                cc = 0
            if cc < 0.55:
                break
            quads[i] = cv2.perspectiveTransform(cantos, H).reshape(4, 2)
            i += passo
    return quads


def _quad_ok(q, area_ref):
    if q is None or not np.all(np.isfinite(q)):
        return False
    if not cv2.isContourConvex(q.astype(np.float32).reshape(-1, 1, 2)):
        return False
    a = cv2.contourArea(q.astype(np.float32))
    return 0.35 * area_ref < a < 2.2 * area_ref


def track_misto(frames, rect, i_ref, i_ini, i_fim):
    """ECC a partir do quadro anterior; quando falha (foto puxada/jogada rápido),
    procura a foto com SIFT + RANSAC usando o quadro de referência como modelo."""
    x0, y0, x1, y1 = rect
    m = 10
    tx0, ty0 = max(0, x0 - m), max(0, y0 - m)
    g_ref = cv2.cvtColor(frames[i_ref], cv2.COLOR_BGR2GRAY)
    tpl8 = g_ref[ty0:y1 + m, tx0:x1 + m]
    tpl = cv2.GaussianBlur(tpl8.astype(np.float32), (0, 0), 1.2)
    cantos = np.array([[x0 - tx0, y0 - ty0], [x1 - tx0, y0 - ty0],
                       [x1 - tx0, y1 - ty0], [x0 - tx0, y1 - ty0]], np.float32).reshape(-1, 1, 2)
    area_ref = (x1 - x0) * (y1 - y0)
    sift = cv2.SIFT_create(nfeatures=3000, contrastThreshold=0.01)
    kt, dt = sift.detectAndCompute(tpl8, None)
    bf = cv2.BFMatcher()
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 80, 1e-5)

    def por_sift(i):
        kf, df = sift.detectAndCompute(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY), None)
        if df is None or dt is None or len(kf) < 8:
            return None
        ms = [a for a, b in (p for p in bf.knnMatch(dt, df, k=2) if len(p) == 2) if a.distance < 0.8 * b.distance]
        if len(ms) < 10:
            return None
        src = np.float32([kt[a.queryIdx].pt for a in ms]).reshape(-1, 1, 2)
        dst = np.float32([kf[a.trainIdx].pt for a in ms]).reshape(-1, 1, 2)
        A, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=5.0)
        if A is None or inl.sum() < 10:
            return None
        return np.vstack([A, [0, 0, 1]]).astype(np.float32)

    def refinar(i, H):
        img = cv2.GaussianBlur(cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 1.2)
        # fotos de desenho são rígidas e planas: afim (gira/escala/move) é mais estável
        # que homografia quando a foto é puxada rápido
        # pirâmide (1/4 → 1/2 → 1) para aguentar movimentos grandes entre quadros
        A = H[:2].copy().astype(np.float32)
        cc = 0
        for esc in (0.25, 0.5, 1.0):
            S = np.array([[esc, 0, 0], [0, esc, 0], [0, 0, 1]], np.float32)
            Si = np.linalg.inv(S)
            As = (S @ np.vstack([A, [0, 0, 1]]) @ Si)[:2].astype(np.float32)
            t = cv2.resize(tpl, None, fx=esc, fy=esc, interpolation=cv2.INTER_AREA) if esc < 1 else tpl
            im = cv2.resize(img, None, fx=esc, fy=esc, interpolation=cv2.INTER_AREA) if esc < 1 else img
            try:
                cc, As = cv2.findTransformECC(t, im, As, cv2.MOTION_AFFINE, crit, None, 3 if esc < 1 else 5)
            except cv2.error:
                if esc == 1.0:
                    return 0, H
                continue
            A = (Si @ np.vstack([As, [0, 0, 1]]) @ S)[:2].astype(np.float32)
        return cc, np.vstack([A, [0, 0, 1]]).astype(np.float32)

    th, tw = tpl8.shape
    PAD = max(th, tw)

    def por_rotacao(i, H_ult):
        """Procura o template girado (-40°..40°) perto da última posição, com o
        quadro aumentado em volta (a foto pode estar saindo pela borda)."""
        g = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        g = cv2.copyMakeBorder(g, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT, value=0)
        cx, cy = (H_ult @ np.array([tw / 2, th / 2, 1], np.float32))[:2] + PAD
        ang0 = np.degrees(np.arctan2(H_ult[1, 0], H_ult[0, 0]))
        r = int(PAD * 0.9)
        X0, Y0 = int(max(0, cx - r - tw)), int(max(0, cy - r - th))
        reg = g[Y0:int(cy + r + th), X0:int(cx + r + tw)]
        melhor = (-1, None)
        for d in range(-40, 41, 5):
            ang = ang0 + d
            M = cv2.getRotationMatrix2D((tw / 2, th / 2), -ang, 1.0)
            cos, sin = abs(M[0, 0]), abs(M[0, 1])
            nw, nh = int(th * sin + tw * cos), int(th * cos + tw * sin)
            M[0, 2] += nw / 2 - tw / 2
            M[1, 2] += nh / 2 - th / 2
            rot = cv2.warpAffine(tpl8, M, (nw, nh))
            msk = cv2.warpAffine(np.full_like(tpl8, 255), M, (nw, nh))
            if reg.shape[0] < nh or reg.shape[1] < nw:
                continue
            res = cv2.matchTemplate(reg, rot, cv2.TM_CCORR_NORMED, mask=msk)
            _, v, _, loc = cv2.minMaxLoc(res)
            if v > melhor[0]:
                # template -> imagem: rotaciona no centro e desloca
                Mi = np.vstack([M, [0, 0, 1]]).astype(np.float32)
                T = np.array([[1, 0, X0 + loc[0] - PAD], [0, 1, Y0 + loc[1] - PAD], [0, 0, 1]], np.float32)
                melhor = (v, T @ Mi)
        return melhor

    quads = {}
    base = np.array([[1, 0, tx0], [0, 1, ty0], [0, 0, 1]], np.float32)
    for passo, alvo in ((1, i_fim), (-1, i_ini)):
        hist = [base.copy()]  # últimas homografias boas, para prever o movimento
        perdidos = 0
        saiu = False  # a foto já se moveu da posição de referência?
        i = i_ref if passo > 0 else i_ref - 1
        while (i <= alvo) if passo > 0 else (i >= alvo):
            H = None
            pred = hist[-1]
            if len(hist) >= 2:  # velocidade constante: H_t+1 = H_t · H_t-1⁻¹ · H_t
                pred = (hist[-1] @ np.linalg.inv(hist[-2]) @ hist[-1]).astype(np.float32)
            for chute, limite in ((hist[-1], 0.6), (pred, 0.45)):
                cc, Hc = refinar(i, chute)
                if cc >= limite:
                    H = Hc
                    break
            if H is None:
                Hs = por_sift(i)
                if Hs is not None:
                    # depois que a foto começou a sair, um resultado "de volta à posição
                    # original" é a moldura vazia do álbum, não a foto: descarta
                    perto_ref = (np.abs(Hs[:2, 2] - base[:2, 2]).max() < 12
                                 and abs(np.degrees(np.arctan2(Hs[1, 0], Hs[0, 0]))) < 3)
                    if not (saiu and perto_ref):
                        H = Hs
            usado_sift = H is not None
            if H is None and passo > 0 and USAR_ROTACAO:
                v, Hr = por_rotacao(i, hist[-1])
                if Hr is not None and v > 0.93:
                    cc, Hc = refinar(i, Hr)
                    H = Hc if cc >= 0.4 else Hr
            usado_pred = False
            if H is None and passo > 0 and len(hist) >= 2 and perdidos < 8:
                H, usado_pred = pred, True  # segue a trajetória por alguns quadros (foto saindo de cena)
            if H is None:
                break
            q = cv2.perspectiveTransform(cantos, H).reshape(4, 2)
            if not _quad_ok(q, area_ref) and not usado_pred:
                break
            quads[i] = q
            if (np.abs(H[:2, 2] - base[:2, 2]).max() > 20
                    or abs(np.degrees(np.arctan2(H[1, 0], H[0, 0]))) > 5):
                saiu = True
            hist = (hist + [H])[-3:]
            perdidos = perdidos + 1 if usado_pred else 0
            i += passo
    return quads


def ordenar(q):
    s = q.sum(1)
    d = np.diff(q, axis=1).ravel()
    return np.array([q[np.argmin(s)], q[np.argmin(d)], q[np.argmax(s)], q[np.argmax(d)]], np.float32)


def track_cor(frames, rect, i_ini, i_fim):
    """Segue a maior mancha laranja perto da posição anterior."""
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    area_ref = (x1 - x0) * (y1 - y0)
    quads = {}
    for i in range(i_ini, i_fim + 1):
        hsv = cv2.cvtColor(frames[i], cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (8, 120, 150), (28, 255, 255))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        melhor = None
        for c in cnts:
            a = cv2.contourArea(c)
            if a < area_ref * 0.3 or a > area_ref * 2.2:
                continue
            M = cv2.moments(c)
            px, py = M["m10"] / M["m00"], M["m01"] / M["m00"]
            dist = np.hypot(px - cx, py - cy)
            if dist < 220 and (melhor is None or dist < melhor[0]):
                melhor = (dist, c, px, py)
        if melhor is None:
            continue
        _, c, cx, cy = melhor
        hull = cv2.convexHull(c)
        ap = cv2.approxPolyDP(hull, 0.04 * cv2.arcLength(hull, True), True)
        if len(ap) == 4:
            q = ordenar(ap.reshape(4, 2).astype(np.float32))
        else:
            q = ordenar(cv2.boxPoints(cv2.minAreaRect(c)).astype(np.float32))
        # recua um pouco para dentro da borda escura da página
        centro = q.mean(0)
        quads[i] = centro + (q - centro) * 0.94
    return quads


def suavizar(quads, k=2):
    idx = sorted(quads)
    out = {}
    for i in idx:
        viz = [quads[j] for j in range(i - k, i + k + 1) if j in quads]
        out[i] = np.mean(viz, 0)
    return out


def main():
    entrada, slots_json, saida = sys.argv[1:4]
    frames, fps = ler_frames(entrada)
    with open(slots_json, encoding="utf-8") as f:
        slots = json.load(f)
    camadas = []  # (quads, imagem estilizada)
    for s in slots:
        x0, y0, x1, y1 = s["rect"]
        w, h = x1 - x0, y1 - y0
        img = estilizar(cv2.imread(s["img"]), w, h)
        i_ini, i_fim = int(round(s["ini"] * fps)), min(len(frames) - 1, int(round(s["fim"] * fps)))
        if s.get("modo") == "cor":
            q = track_cor(frames, s["rect"], i_ini, i_fim)
        else:
            q = track_misto(frames, s["rect"], int(round(s["ref"] * fps)), i_ini, i_fim)
        q = suavizar(q, 1)
        print(f'{s["img"]}: {len(q)} quadros seguidos de {i_fim - i_ini + 1}', file=sys.stderr)
        camadas.append((q, img, i_ini, i_fim))

    h0, w0 = frames[0].shape[:2]
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-s", f"{w0}x{h0}", "-r", str(fps), "-i", "pipe:0", "-i", entrada,
                             "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "14",
                             "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "copy", saida],
                            stdin=subprocess.PIPE)
    for i, fr in enumerate(frames):
        out = fr.astype(np.float32)
        for q, img, i_ini, i_fim in camadas:
            if i not in q:
                continue
            h, w = img.shape[:2]
            src = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
            M = cv2.getPerspectiveTransform(src, q[i].astype(np.float32))
            warped = cv2.warpPerspective(img, M, (w0, h0), flags=cv2.INTER_LINEAR)
            alpha = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (w0, h0))
            alpha = cv2.GaussianBlur(alpha, (0, 0), 0.9).astype(np.float32) / 255
            # entra/sai suave (4 quadros) nas pontas do trecho seguido
            idx = sorted(q)
            fade = 1.0
            if idx[0] > i_ini + 1:  # tracking começou depois do corte: entra suave
                fade = min(fade, (i - idx[0] + 1) / 4)
            if idx[-1] < i_fim - 1:  # tracking perdeu a foto antes do fim: sai suave
                fade = min(fade, (idx[-1] - i + 1) / 2)
            # não pinta por cima da mão/luva branca do personagem
            hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
            luva = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255)).astype(np.float32) / 255
            luva = cv2.GaussianBlur(luva, (0, 0), 1.2)
            a = (alpha * fade * (1 - luva))[..., None]
            out = out * (1 - a) + warped.astype(np.float32) * a
        proc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    main()

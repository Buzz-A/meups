"""Detecta rostos (YuNet) em cada trecho do vídeo do estalo e salva faces.json."""
import cv2, json, subprocess, sys, numpy as np
src, modelo, saida = sys.argv[1:4]
TRECHOS = json.load(open(sys.argv[4]))
W, H = 1920, 1080
det = cv2.FaceDetectorYN.create(modelo, "", (960, 540), 0.6, 0.3, 50)
res = {}
for nome, (ini, fim) in TRECHOS.items():
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(ini), "-t", str(fim - ini), "-i", src,
                          "-vf", "fps=30,scale=960:540", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    faces = []
    while True:
        b = p.stdout.read(960 * 540 * 3)
        if len(b) < 960 * 540 * 3: break
        f = np.frombuffer(b, np.uint8).reshape(540, 960, 3)
        _, d = det.detect(f)
        faces.append([] if d is None else [[float(v) * 2 for v in r[:4]] + [float(r[14])] for r in d])
    res[nome] = faces
    n = sum(1 for f in faces if f)
    print(nome, len(faces), "frames, com rosto:", n)
json.dump(res, open(saida, "w"))

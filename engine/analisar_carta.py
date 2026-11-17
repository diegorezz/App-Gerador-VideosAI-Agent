"""
ANALISADOR DE ARCANO — motor agnostico de carta
Extrai tudo que o renderer precisa, sem hardcode por carta:
  - geometria da carta (bbox, proporcao)
  - paleta dominante
  - mapa de profundidade (paralaxe 3D)
  - pontos focais (rosto / figura / objeto central) por tom de pele e saliencia
  - elemento narrativo (fogo / agua / luz / terra / ar)
  - linha do horizonte e regiao de rotulo
Saida: profile JSON consumido pelo renderer generico.
"""
import json
import os
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter, label, find_objects

CARD_W, CARD_H = 1100, 2100


def carregar(caminho):
    im = Image.open(caminho)
    if im.mode != "RGB":
        im = im.convert("RGB")
    return im


def bbox_carta(im):
    a = np.asarray(im, np.float32)
    lum = gaussian_filter(a.mean(axis=2), 3)
    m = lum > 35
    colf, rowf = m.mean(axis=0), m.mean(axis=1)
    xs = np.where(colf > 0.5)[0]
    ys = np.where(rowf > 0.5)[0]
    if len(xs) == 0 or len(ys) == 0:
        return 0, 0, im.width, im.height
    return int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1


def paleta(card, k=8):
    sm = card.resize((120, 230), Image.LANCZOS)
    arr = np.asarray(sm, np.uint8).reshape(-1, 3).astype(np.float32)
    # k-means simples
    rng = np.random.default_rng(3)
    cent = arr[rng.choice(len(arr), k, replace=False)]
    for _ in range(18):
        d = ((arr[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            sel = arr[lab == j]
            if len(sel):
                cent[j] = sel.mean(0)
    counts = np.bincount(lab, minlength=k)
    order = counts.argsort()[::-1]
    out = []
    for j in order:
        c = cent[j]
        out.append({
            "rgb": [int(v) for v in c],
            "hex": "#%02x%02x%02x" % tuple(int(v) for v in c),
            "peso": round(float(counts[j] / counts.sum()), 4),
        })
    return out


def mapa_profundidade(card, sal):
    """profundidade pseudo-3D: saturacao + tinta + posicao vertical + saliencia"""
    arr = np.asarray(card, np.float32) / 255.0
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 0.01, (mx - mn) / np.maximum(mx, 1e-3), 0)
    h, w = sat.shape
    yy = np.linspace(0, 1, h)[:, None]

    d = gaussian_filter(sat * 1.10, 24)
    d += gaussian_filter((1.0 - mx) * 0.50, 28)          # tinta escura = traco/figura
    d += (yy ** 1.55) * 0.40                              # chao avanca
    d -= ((1 - yy) ** 3) * 0.28                           # ceu recua
    d += gaussian_filter(sal, 40) * 1.9                   # figura principal avanca
    d = gaussian_filter(d, 20)
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)
    return (d ** 0.85).astype(np.float32)


def detectar_pele(card):
    """mascara de tom de pele destas gravuras (distingue pele de fundo creme)"""
    a = np.asarray(card, np.float32) / 255.0
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = a.max(2)
    mn = a.min(2)
    sat = np.where(mx > 0.01, (mx - mn) / np.maximum(mx, 1e-3), 0)
    m = ((sat > 0.30) & (sat < 0.62)
         & (r > 0.60) & (r < 0.95)
         & (g > 0.38) & (g < 0.70)
         & (b > 0.22) & (b < 0.52)
         & ((r - b) > 0.22) & ((r - b) < 0.56)
         & ((g - b) > 0.10) & ((g - b) < 0.30))
    return gaussian_filter(m.astype(np.float32), 6)


def pontos_focais(card, pele):
    """Rosto: maior blob de pele com forma/posicao plausiveis de rosto.
    Gravuras nao respondem a Haar cascade; a regra geometrica e mais estavel."""
    h, w = pele.shape
    card_area = float(h * w)
    lbl, n = label(pele > 0.40)
    if not n:
        return []
    sizes = np.bincount(lbl.ravel())
    sizes[0] = 0
    best, bestscore = None, 0.0
    for i, sl in enumerate(find_objects(lbl)):
        if sl is None:
            continue
        area = int(sizes[i + 1])
        frac = area / card_area
        if not (0.0025 < frac < 0.030):      # tamanho plausivel de rosto
            continue
        bw = sl[1].stop - sl[1].start
        bh = sl[0].stop - sl[0].start
        if bw < 14 or bh < 14:
            continue
        compact = area / float(bw * bh)
        asp = bw / float(bh)
        if compact < 0.45 or not (0.55 < asp < 1.65):
            continue
        cy = (sl[0].start + sl[0].stop) / 2.0 / h
        cx = (sl[1].start + sl[1].stop) / 2.0 / w
        if not (0.09 < cy < 0.42) or abs(cx - 0.5) > 0.19:
            continue
        score = (compact ** 1.5
                 * (1.0 / (1.0 + abs(asp - 1.0) * 2.2))
                 * (1.0 / (1.0 + abs(cx - 0.5) * 3.0))
                 * (1.0 / (1.0 + abs(cy - 0.22) * 2.0))
                 * (frac ** 0.35))
        if score > bestscore:
            bestscore = score
            best = {"tipo": "rosto", "x": round(cx, 4), "y": round(cy, 4),
                    "area": area, "compacidade": round(compact, 3),
                    "aspecto": round(asp, 3), "score": round(score, 4)}
    return [best] if best else []


def elemento_narrativo(pal):
    """decide o efeito elemental a partir da paleta dominante"""
    quente = frio = ouro = escuro = 0.0
    for c in pal:
        r, g, b = c["rgb"]
        p = c["peso"]
        if r > 170 and g > 125 and b < 110 and (r - b) > 80:
            ouro += p
        elif r > 120 and r - b > 60:
            quente += p
        elif b > 90 and b - r > 20:
            frio += p
        if max(r, g, b) < 70:
            escuro += p
    scores = {"fogo": quente + ouro * 0.55, "agua": frio * 1.15,
              "luz": ouro * 1.35, "terra": escuro * 1.0}
    elem = max(scores, key=scores.get)
    return elem, {k: round(v, 3) for k, v in scores.items()}


def geometria(card):
    """horizonte, faixa de rotulo e regiao de ceu"""
    a = np.asarray(card, np.float32)
    lum = a.mean(axis=2)
    h, w = lum.shape
    # faixa de rotulo inferior: linha escura horizontal perto da base
    rowdark = (lum < 90).mean(axis=1)
    label_y = None
    for y in range(int(h * 0.90), int(h * 0.99)):
        if rowdark[y] > 0.45:
            label_y = y / h
            break
    return {
        "label_y": round(label_y if label_y else 0.955, 4),
        "ceu_y": 0.10,
        "piso_y": 0.86,
    }


def analisar(caminho, debug_png=None):
    im = carregar(caminho)
    x0, y0, x1, y1 = bbox_carta(im)
    card = im.crop((x0, y0, x1, y1))
    card_big = card.resize((CARD_W, CARD_H), Image.LANCZOS)
    card_big = card_big.filter(ImageFilter.UnsharpMask(radius=2, percent=55, threshold=3))

    pal = paleta(card_big)
    pele = detectar_pele(card_big)
    # saliencia = bordas + pele
    lum = np.asarray(card_big, np.float32).mean(axis=2) / 255.0
    gy, gx = np.gradient(gaussian_filter(lum, 1.2))
    bordas = np.clip(np.hypot(gx, gy) * 3.0, 0, 1)
    sal = np.clip(gaussian_filter(bordas, 6) * 0.7 + pele * 1.3, 0, 1)

    prof = mapa_profundidade(card_big, sal)
    focos = pontos_focais(card_big, pele)
    elem, escores = elemento_narrativo(pal)
    geo = geometria(card_big)

    # ponto focal principal (rosto se existir, senao centro de massa da saliencia)
    if focos:
        fx, fy = focos[0]["x"], focos[0]["y"]
    else:
        ys, xs = np.where(sal > np.percentile(sal, 92))
        fx, fy = float(xs.mean() / CARD_W), float(ys.mean() / CARD_H)

    perfil = {
        "arquivo": os.path.basename(caminho),
        "carta_px": [CARD_W, CARD_H],
        "proporcao": round(CARD_W / CARD_H, 4),
        "paleta": pal,
        "elemento": elem,
        "elemento_scores": escores,
        "foco_principal": {"x": round(fx, 4), "y": round(fy, 4)},
        "focos": focos,
        "geometria": geo,
        "profundidade_media": round(float(prof.mean()), 4),
    }

    if debug_png:
        base = card_big.resize((330, 630), Image.LANCZOS).convert("RGB")
        arr = np.asarray(base, np.float32).copy()
        # overlay de calor da saliencia
        s_small = np.asarray(Image.fromarray(np.ascontiguousarray(sal, np.float32), "F")
                             .resize((330, 630), Image.BILINEAR), np.float32)
        arr[..., 0] += s_small * 110
        arr[..., 1] -= s_small * 30
        # cruzeta no foco
        fx_px, fy_px = int(fx * 330), int(fy * 630)
        for dx in range(-16, 17):
            if 0 <= fx_px + dx < 330 and 0 <= fy_px < 630:
                arr[fy_px, fx_px + dx] = [80, 255, 160]
        for dy in range(-16, 17):
            if 0 <= fy_px + dy < 630 and 0 <= fx_px < 330:
                arr[fy_px + dy, fx_px] = [80, 255, 160]
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(debug_png)

    return perfil, card_big, prof


if __name__ == "__main__":
    entrada = sys.argv[1] if len(sys.argv) > 1 else "arcanos_test"
    saida_dir = "engine/perfis"
    os.makedirs(saida_dir, exist_ok=True)
    os.makedirs("engine/assets", exist_ok=True)

    if os.path.isdir(entrada):
        alvos = sorted(
            os.path.join(entrada, f) for f in os.listdir(entrada)
            if f.lower().endswith((".tif", ".tiff", ".png", ".jpg"))
            and "preview" not in f
        )
    else:
        alvos = [entrada]

    for caminho in alvos:
        nome = os.path.splitext(os.path.basename(caminho))[0]
        dbg = f"engine/assets/debug_{nome}.png"
        perfil, card_big, prof = analisar(caminho, dbg)
        card_big.save(f"engine/assets/card_{nome}.png")
        Image.fromarray((prof * 255).astype(np.uint8)).save(f"engine/assets/depth_{nome}.png")
        with open(f"{saida_dir}/{nome}.json", "w", encoding="utf-8") as f:
            json.dump(perfil, f, ensure_ascii=False, indent=2)
        print(f"{nome}: elemento={perfil['elemento']:6s} "
              f"foco=({perfil['foco_principal']['x']:.2f},{perfil['foco_principal']['y']:.2f}) "
              f"rostos={len(perfil['focos'])} label_y={perfil['geometria']['label_y']}")

    print("\nperfis salvos em", saida_dir)

"""
MOTOR "JORNADA PELA CARTA"  (estilo mysticmayhem.ai)
=====================================================

O que o vídeo modelo faz (e o motor antigo não fazia):
  1. A carta é o primeiro quadro.
  2. A câmera MERGULHA num detalhe da carta e ela vira OUTRA CENA (anjo -> mar -> montanha -> planeta).
  3. Cada cena nasce dos elementos da própria carta e a câmera atravessa uma para a outra
     (zoom através, clarão de luz, vórtice...).
  4. No fim, volta à carta (loop).

Como o motor reproduz isso:
  ROTEIRO    -> Gemini (visão) lê a SUA carta e escreve as cenas. Sem chave: usa regiões reais da carta.
  KEYFRAMES  -> Gemini Image cria cada cena no estilo da carta. Sem chave: recortes reais da carta.
  ANIMAÇÃO   -> Veo 3.1 recebe (quadro inicial + quadro final) e cria a transição (o "morph").
                Sem Veo: transições locais (zoom através, luz, vórtice, whip-pan) — rascunho.
  MONTAGEM   -> FFmpeg junta tudo. O último quadro é a carta, então o vídeo fecha em loop SEM
                precisar do "reverse" (que espelhava o vídeo e deixava tudo repetido).

Tudo aqui é independente do Streamlit: a interface só chama as funções públicas no final do arquivo.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import random
import re
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

W, H, FPS = 720, 1280, 24

TRANSICOES = ("zoom_through", "luz_branca", "vortice", "whip_pan")

MODELOS_TEXTO_PADRAO = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
MODELOS_IMAGEM_PADRAO = ["gemini-2.5-flash-image", "gemini-3.1-flash-image-preview"]
MODELO_VEO_PADRAO = "veo-3.1-fast-generate-preview"

# Valores APROXIMADOS (US$/segundo de vídeo) só para estimar o custo na tela. Confira a página de preços do Google.
PRECO_VEO_POR_SEG = {"lite": 0.05, "fast": 0.10, "standard": 0.40}
PRECO_IMAGEM = 0.04


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades
# ──────────────────────────────────────────────────────────────────────────────
def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _p(barra, valor: int):
    try:
        if barra is not None:
            barra.progress(max(0, min(100, int(valor))))
    except Exception:
        pass


def _s(status, msg: str):
    try:
        if status is not None:
            status.info(msg)
    except Exception:
        pass


def estimar_custo_usd(n_cenas: int, seg_por_clip: int, modelo_veo: str, usar_veo: bool, usar_gemini_imagens: bool) -> float:
    custo = 0.0
    if usar_gemini_imagens:
        custo += n_cenas * PRECO_IMAGEM
    if usar_veo:
        chave = "standard"
        m = (modelo_veo or "").lower()
        if "lite" in m:
            chave = "lite"
        elif "fast" in m:
            chave = "fast"
        custo += (n_cenas + 1) * seg_por_clip * PRECO_VEO_POR_SEG[chave]
    return round(custo, 2)


def _cover(img: Image.Image, w: int, h: int, resample=Image.LANCZOS) -> Image.Image:
    """Redimensiona preenchendo w×h (corta o excesso no centro)."""
    img = img.convert("RGB")
    sw, sh = img.size
    s = max(w / sw, h / sh)
    nw, nh = max(w, round(sw * s)), max(h, round(sh * s))
    img = img.resize((nw, nh), resample)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return img.crop((x0, y0, x0 + w, y0 + h))


def _ease_in(x: float, p: float = 2.2) -> float:
    return max(0.0, min(1.0, x)) ** p


def _ease_out(x: float, p: float = 2.2) -> float:
    return 1.0 - (1.0 - max(0.0, min(1.0, x))) ** p


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _seed_da_carta(img_bytes: bytes, nome: str) -> int:
    return int(hashlib.md5(img_bytes[:200000] + nome.encode("utf-8", "ignore")).hexdigest()[:8], 16)


# ──────────────────────────────────────────────────────────────────────────────
# Escritor de vídeo (FFmpeg) — agora guarda o log de erro em vez de engoli-lo
# ──────────────────────────────────────────────────────────────────────────────
class _Escritor:
    def __init__(self, caminho: Path, fps: int = FPS):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.log_path = Path(str(self.caminho) + ".log")
        self._log = open(self.log_path, "wb")
        cmd = [
            _ffmpeg(), "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            str(self.caminho),
        ]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self._log)

    def escrever(self, frame: Image.Image):
        if frame.size != (W, H) or frame.mode != "RGB":
            frame = frame.convert("RGB").resize((W, H), Image.BILINEAR)
        try:
            self._proc.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError) as e:
            raise RuntimeError(f"FFmpeg encerrou durante a escrita: {self._ler_log()}") from e

    def _ler_log(self) -> str:
        try:
            self._log.flush()
            return self.log_path.read_text(errors="ignore")[-800:]
        except Exception:
            return ""

    def fechar(self) -> bool:
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        rc = self._proc.wait()
        self._log.close()
        return rc == 0 and self.caminho.exists()


# ──────────────────────────────────────────────────────────────────────────────
# Câmera / efeitos básicos (PIL + numpy)
# ──────────────────────────────────────────────────────────────────────────────
def _vista(src: Image.Image, escala: float, fx: float = 0.5, fy: float = 0.5, dx: float = 0.0, dy: float = 0.0) -> Image.Image:
    """Janela W×H de `src` com zoom `escala` ancorado no ponto focal (fx, fy) (0..1). dx/dy = pan em fração."""
    sw, sh = src.size
    escala = max(1.0, escala)
    w, h = sw / escala, sh / escala
    x0 = fx * sw - fx * w + dx * sw
    y0 = fy * sh - fy * h + dy * sh
    x0 = min(max(x0, 0.0), sw - w)
    y0 = min(max(y0, 0.0), sh - h)
    return src.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))


def _zoom_blur(src: Image.Image, escala: float, fx: float, fy: float, quantidade: float, k: int = 6) -> Image.Image:
    """Desfoque radial (sensação de velocidade ao atravessar a cena)."""
    if quantidade <= 0.004:
        return _vista(src, escala, fx, fy)
    acc = None
    for i in range(k):
        s = escala * (1.0 + quantidade * (i / (k - 1)))
        a = np.asarray(_vista(src, s, fx, fy), dtype=np.float32)
        acc = a if acc is None else acc + a
    return Image.fromarray((acc / k).astype(np.uint8))


@lru_cache(maxsize=16)
def _mapa_radial(fx: float, fy: float, sigma: float) -> np.ndarray:
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    d2 = ((xs / W - fx) ** 2) * (W / H) ** 2 + (ys / H - fy) ** 2
    return np.exp(-d2 / (2 * sigma * sigma)).astype(np.float32)[..., None]


def _luz(img: Image.Image, intensidade: float, fx: float = 0.5, fy: float = 0.45, cor=(255, 240, 205)) -> Image.Image:
    """Clarão dourado: brilho radial + véu de exposição."""
    if intensidade <= 0.004:
        return img
    a = np.asarray(img, dtype=np.float32)
    glow = _mapa_radial(round(fx, 2), round(fy, 2), 0.30)
    c = np.array(cor, dtype=np.float32)
    veu = min(1.0, intensidade) ** 1.6
    a = a * (1 - 0.65 * veu) + c * (0.65 * veu)
    a = a + glow * c * min(1.0, intensidade) * 0.95
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _swirl(img: Image.Image, forca: float, zoom: float) -> Image.Image:
    """Torção em espiral (vórtice) — escala reduzida para ser rápido."""
    from scipy.ndimage import map_coordinates

    sw, sh = W // 2, H // 2
    pequeno = np.asarray(img.resize((sw, sh), Image.BILINEAR), dtype=np.float32)
    ys, xs = np.mgrid[0:sh, 0:sw].astype(np.float32)
    x = (xs - sw / 2) / (sw / 2)
    y = (ys - sh / 2) / (sw / 2)
    r = np.sqrt(x * x + y * y) + 1e-6
    ang = np.arctan2(y, x) + forca * np.exp(-r * 1.8)
    rr = r / max(1.0, zoom)
    sx = np.cos(ang) * rr * (sw / 2) + sw / 2
    sy = np.sin(ang) * rr * (sw / 2) + sh / 2
    saida = np.empty_like(pequeno)
    for c in range(3):
        saida[..., c] = map_coordinates(pequeno[..., c], [sy, sx], order=1, mode="reflect")
    return Image.fromarray(np.clip(saida, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)


def _tinta_vortice(img: Image.Image, t: float) -> Image.Image:
    """Escurece as bordas e esquenta o centro (buraco do vórtice)."""
    a = np.asarray(img, dtype=np.float32)
    glow = _mapa_radial(0.5, 0.5, 0.16)
    escuro = 1 - 0.55 * t * (1 - glow)
    a = a * escuro + glow * np.array([255, 214, 140], np.float32) * 0.55 * t
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ──────────────────────────────────────────────────────────────────────────────
# Transições locais: cada uma recebe duas imagens (src A, src B) e devolve `n` quadros
# ──────────────────────────────────────────────────────────────────────────────
def _quadros_zoom_through(A, B, n, fa, fb):
    for i in range(n):
        p = i / max(1, n - 1)
        # A: mergulha no foco
        qa = _ease_in(p / 0.55)
        va = _zoom_blur(A, 1.12 + 2.6 * qa, fa[0], fa[1], 0.55 * qa)
        va = _luz(va, 0.85 * qa ** 1.5, fa[0], fa[1])
        # B: sai de um zoom alto até 1.0
        qb = _ease_out((p - 0.45) / 0.55)
        vb = _zoom_blur(B, 2.7 - 1.7 * qb, fb[0], fb[1], 0.55 * (1 - qb))
        vb = _luz(vb, 0.85 * (1 - qb) ** 1.5, fb[0], fb[1])
        if p < 0.45:
            yield va
        elif p > 0.58:
            yield vb
        else:
            yield Image.blend(va, vb, (p - 0.45) / 0.13)


def _quadros_luz_branca(A, B, n, fa, fb):
    for i in range(n):
        p = i / max(1, n - 1)
        if p < 0.5:
            q = _ease_in(p / 0.5, 1.8)
            v = _vista(A, 1.12 + 0.55 * q, fa[0], fa[1])
            yield _luz(v, 0.15 + 1.35 * q, fa[0], fa[1])
        else:
            q = _ease_out((p - 0.5) / 0.5, 1.8)
            v = _vista(B, 1.45 - 0.45 * q, fb[0], fb[1])
            yield _luz(v, 1.5 * (1 - q), fb[0], fb[1])


def _quadros_vortice(A, B, n, fa, fb):
    for i in range(n):
        p = i / max(1, n - 1)
        if p < 0.5:
            q = _ease_in(p / 0.5, 1.7)
            v = _swirl(_vista(A, 1.12, 0.5, 0.5), 9.0 * q, 1.0 + 2.4 * q)
            v = _tinta_vortice(v, q)
            yield _luz(v, 0.9 * q ** 3, 0.5, 0.5)
        else:
            q = _ease_out((p - 0.5) / 0.5, 1.7)
            v = _swirl(_vista(B, 1.0, 0.5, 0.5), 9.0 * (1 - q), 1.0 + 2.4 * (1 - q))
            v = _tinta_vortice(v, 1 - q)
            yield _luz(v, 0.9 * (1 - q) ** 3, 0.5, 0.5)


def _quadros_whip_pan(A, B, n, fa, fb, eixo="x", sinal=1):
    a = np.asarray(_vista(A, 1.12, fa[0], fa[1]), dtype=np.float32)
    b = np.asarray(_vista(B, 1.0, 0.5, 0.5), dtype=np.float32)
    tam = W if eixo == "x" else H
    tela = np.concatenate([a, b], axis=1 if eixo == "x" else 0)
    for i in range(n):
        p = i / max(1, n - 1)
        pos = _smooth(p) * tam
        if sinal < 0:
            tela_u = np.concatenate([b, a], axis=1 if eixo == "x" else 0)
            base = tam - pos
        else:
            tela_u = tela
            base = pos
        k = 28
        borr = math.sin(math.pi * p) * tam * 0.10
        acc = np.zeros((H, W, 3), np.float32)
        for j in range(k):
            off = int(round(base + (j / (k - 1) - 0.5) * borr))
            off = max(0, min(tam, off))
            if eixo == "x":
                acc += tela_u[:, off:off + W]
            else:
                acc += tela_u[off:off + H, :]
        yield Image.fromarray((acc / k).astype(np.uint8))


def _fazer_clipe_local(
    A: Image.Image, B: Image.Image, tipo: str, seg: float, saida: Path, rng: random.Random
) -> bool:
    """Clipe local A -> B: um respiro (câmera entrando devagar em A) + a transição."""
    total = max(24, int(round(seg * FPS)))
    frac_respiro = {"zoom_through": 0.30, "luz_branca": 0.30, "vortice": 0.25, "whip_pan": 0.35}.get(tipo, 0.3)
    n_resp = int(total * frac_respiro)
    n_tr = total - n_resp
    fa = (min(0.7, max(0.3, 0.5 + rng.uniform(-0.15, 0.15))), min(0.65, max(0.3, 0.42 + rng.uniform(-0.12, 0.12))))
    fb = (0.5, 0.45)

    esc = _Escritor(saida)
    try:
        for i in range(n_resp):  # respiro: câmera avança devagar em A
            p = i / max(1, n_resp - 1)
            esc.escrever(_vista(A, 1.0 + 0.12 * _smooth(p), fa[0], fa[1]))
        if tipo == "luz_branca":
            gen = _quadros_luz_branca(A, B, n_tr, fa, fb)
        elif tipo == "vortice":
            gen = _quadros_vortice(A, B, n_tr, fa, fb)
        elif tipo == "whip_pan":
            gen = _quadros_whip_pan(A, B, n_tr, fa, fb, eixo=rng.choice(["x", "y"]), sinal=rng.choice([1, -1]))
        else:
            gen = _quadros_zoom_through(A, B, n_tr, fa, fb)
        for fr in gen:
            esc.escrever(fr)
    finally:
        ok = esc.fechar()
    return ok


# ──────────────────────────────────────────────────────────────────────────────
# Keyframes locais: regiões REAIS da carta (sem IA, sem custo, diferentes em cada carta)
# ──────────────────────────────────────────────────────────────────────────────
def _regioes_de_interesse(carta: Image.Image, n: int) -> list[tuple[float, float, float, float]]:
    """Escolhe n janelas 9:16 (fração 0..1 da carta) com mais detalhe/cor, sem se sobrepor muito."""
    gw, gh = 180, 320
    pequeno = carta.convert("RGB").resize((gw, gh), Image.BILINEAR)
    g = np.asarray(pequeno.convert("L"), dtype=np.float32)
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    borda = gx + gy
    sat = np.asarray(pequeno.convert("HSV"), dtype=np.float32)[..., 1] / 255.0
    mapa = borda / (borda.max() + 1e-6) + 0.35 * sat
    # ignora a moldura da carta
    mx, my = int(gw * 0.05), int(gh * 0.04)
    mapa[:my, :] = 0
    mapa[-my:, :] = 0
    mapa[:, :mx] = 0
    mapa[:, -mx:] = 0
    integral = np.pad(mapa, ((1, 0), (1, 0))).cumsum(0).cumsum(1)

    def soma(x0, y0, x1, y1):
        return integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]

    candidatos = []
    for frac_w in (0.42, 0.56, 0.72):
        ww = int(gw * frac_w)
        hh = int(ww * 16 / 9)
        if hh > gh:
            hh = gh
            ww = int(hh * 9 / 16)
        passo = max(4, ww // 8)
        for y0 in range(0, gh - hh + 1, passo):
            for x0 in range(0, gw - ww + 1, passo):
                dens = soma(x0, y0, x0 + ww, y0 + hh) / (ww * hh)
                candidatos.append((dens * (0.9 + 0.25 * (1 - frac_w)), x0, y0, ww, hh))
    candidatos.sort(reverse=True)

    def iou(a, b):
        ax0, ay0, aw, ah = a
        bx0, by0, bw, bh = b
        ix = max(0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
        iy = max(0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
        inter = ix * iy
        return inter / (aw * ah + bw * bh - inter + 1e-6)

    escolhidas = []
    for _, x0, y0, ww, hh in candidatos:
        box = (x0, y0, ww, hh)
        if all(iou(box, e) < 0.18 for e in escolhidas):
            escolhidas.append(box)
        if len(escolhidas) >= n:
            break
    while len(escolhidas) < n:  # cartas muito lisas: completa com janelas centrais
        escolhidas.append((int(gw * 0.2), int(gh * (0.1 + 0.2 * len(escolhidas))), int(gw * 0.6), int(gw * 0.6 * 16 / 9)))
    return [(x0 / gw, y0 / gh, (x0 + ww) / gw, min(1.0, (y0 + hh) / gh)) for x0, y0, ww, hh in escolhidas]


def _keyframe_de_regiao(carta: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    cw, ch = carta.size
    x0, y0, x1, y1 = box
    rec = carta.convert("RGB").crop((int(x0 * cw), int(y0 * ch), int(x1 * cw), int(y1 * ch)))
    k = _cover(rec, int(W * 1.35), int(H * 1.35), Image.LANCZOS)
    return k.filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=3))


def _carta_para_keyframe(carta: Image.Image) -> Image.Image:
    return _cover(carta, int(W * 1.35), int(H * 1.35), Image.LANCZOS)


# ──────────────────────────────────────────────────────────────────────────────
# ROTEIRO (storyboard)
# ──────────────────────────────────────────────────────────────────────────────
def _escolher_transicoes(n: int, rng: random.Random) -> list[str]:
    """n transições variadas, sem repetir em sequência; a última volta à carta com vórtice (como no modelo)."""
    saida: list[str] = []
    pool = ["zoom_through", "luz_branca", "whip_pan", "zoom_through", "vortice"]
    for i in range(n):
        if i == n - 1:
            saida.append("vortice")
            continue
        opcoes = [t for t in pool if not saida or t != saida[-1]]
        saida.append(rng.choice(opcoes))
    return saida


def roteiro_local(plano: dict, n_cenas: int, rng: random.Random) -> dict:
    cam = plano.get("camadas_z_space", {}) or {}
    rotulos = [
        cam.get("plano_medio") or "Figura central",
        cam.get("primeiro_plano") or "Primeiro plano",
        cam.get("plano_fundo") or "Cenário",
        plano.get("astro_revelacao_ceu") or "Céu / astro regente",
        "Símbolo da carta",
    ]
    cenas = [{"titulo": rotulos[i % len(rotulos)], "prompt_imagem": ""} for i in range(n_cenas)]
    tipos = _escolher_transicoes(n_cenas + 1, rng)
    moves = {
        "zoom_through": "The camera dives forward into the focal point and passes through it into the next scene.",
        "luz_branca": "A burst of golden light floods the frame and the next scene emerges from the glow.",
        "vortice": "The image spirals into a swirling vortex and opens onto the next scene.",
        "whip_pan": "A fast whip pan sweeps the camera sideways into the next scene.",
    }
    trans = [{"tipo": t, "movimento": moves[t]} for t in tipos]
    return {"cenas": cenas, "transicoes": trans, "origem": "local"}


_SYSTEM_ROTEIRO = """You are a storyboard director for short vertical (9:16) animated tarot "journeys" in the style of the
Instagram account mysticmayhem.ai. You will receive ONE tarot card image. The video starts on the card and the camera
dives into it, travelling through a chain of DIFFERENT scenes that are born from the symbols INSIDE THIS SPECIFIC CARD
(never generic scenery), then returns to the card.

Typical arc (use it as a guide, adapting to the card): (1) intimate close-up of the main figure or its key attribute doing
something dramatic; (2) the surrounding world/environment of the card; (3) a grand landscape or elemental force that
appears in the card; (4) a cosmic or symbolic element (sun, moon, planet, star, divine light) with energy effects.

Return ONLY valid JSON, no markdown:
{
 "cenas": [ {"titulo": "<short title in Portuguese>", "prompt_imagem": "<English, 1-3 sentences: a full-bleed vertical illustration of this scene in the same ink/woodcut style as the card; describe subject, camera angle, light>"} ],
 "transicoes": [ {"tipo": "zoom_through|luz_branca|vortice|whip_pan", "movimento": "<English, 1-2 sentences: how the camera moves from the previous image into the next one; reference real objects in both images>"} ]
}
Rules: exactly N scenes in "cenas" and exactly N+1 items in "transicoes" (card -> scene 1, scene 1 -> scene 2, ..., last scene -> card).
The last transition returns to the original card. Prompts must contain no text, letters, borders or UI."""


def roteiro_gemini(client, types, img_bytes: bytes, plano: dict, n_cenas: int, instrucao: str, modelos: list[str]) -> dict | None:
    nome = plano.get("arcano_nome", "tarot card")
    pedido = f"N = {n_cenas}. Card: {nome}. Extra direction from the user (may be empty): {instrucao or 'none'}"
    for modelo in modelos:
        try:
            resp = client.models.generate_content(
                model=modelo,
                contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/png"), pedido],
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_ROTEIRO,
                    response_mime_type="application/json",
                    temperature=0.9,
                ),
            )
            txt = re.sub(r"^```(?:json)?|```$", "", (resp.text or "").strip(), flags=re.M).strip()
            dados = json.loads(txt)
            cenas = dados.get("cenas") or []
            trans = dados.get("transicoes") or []
            if len(cenas) < 1 or len(trans) < 1:
                continue
            cenas = cenas[:n_cenas]
            while len(cenas) < n_cenas:
                cenas.append(dict(cenas[-1]))
            trans = trans[: n_cenas + 1]
            while len(trans) < n_cenas + 1:
                trans.append({"tipo": "zoom_through", "movimento": "The camera dives into the next scene."})
            for t in trans:
                if t.get("tipo") not in TRANSICOES:
                    t["tipo"] = "zoom_through"
            trans[-1]["tipo"] = trans[-1]["tipo"] if trans[-1]["tipo"] in TRANSICOES else "vortice"
            return {"cenas": cenas, "transicoes": trans, "origem": f"gemini:{modelo}"}
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────────────────────────────────────
# KEYFRAMES com Gemini Image (usa a carta como referência de estilo)
# ──────────────────────────────────────────────────────────────────────────────
def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def keyframe_gemini(client, types, carta_bytes: bytes, anterior: Image.Image | None, prompt_cena: str, modelos: list[str]) -> Image.Image | None:
    instr = (
        "The FIRST attached image is a tarot card: use it ONLY as the art-style and character-design reference "
        "(same ink linework, crosshatching, flat vintage palette, printed-paper texture; same look for any figure or object "
        "that also appears in the card). "
        + ("The SECOND attached image is the previous scene of the same journey: keep palette and lighting continuous. " if anterior else "")
        + "Now paint a brand-new full-bleed VERTICAL 9:16 illustration of this scene: "
        + prompt_cena
        + " RULES: no card border, no frame, no title, no letters or text of any kind, no UI, no watermark."
    )
    partes = [types.Part.from_bytes(data=carta_bytes, mime_type="image/png")]
    if anterior is not None:
        partes.append(types.Part.from_bytes(data=_png_bytes(anterior), mime_type="image/png"))
    partes.append(instr)

    for modelo in modelos:
        for com_aspecto in (True, False):
            try:
                kwargs = {"response_modalities": ["IMAGE"]}
                if com_aspecto:
                    kwargs["image_config"] = types.ImageConfig(aspect_ratio="9:16")
                resp = client.models.generate_content(
                    model=modelo, contents=partes, config=types.GenerateContentConfig(**kwargs)
                )
                for cand in (resp.candidates or []):
                    for part in (cand.content.parts or []):
                        dados = getattr(part, "inline_data", None)
                        if dados is not None and getattr(dados, "data", None):
                            img = Image.open(io.BytesIO(dados.data)).convert("RGB")
                            return _cover(img, int(W * 1.35), int(H * 1.35), Image.LANCZOS)
            except Exception:
                continue
    return None


# ──────────────────────────────────────────────────────────────────────────────
# VEO 3.1: quadro inicial + quadro final => transição (morph) feita por IA
# ──────────────────────────────────────────────────────────────────────────────
_ESTILO_VEO = (
    "Keep the hand-inked vintage tarot woodcut illustration look: bold black linework, crosshatching, flat vintage colours. "
    "One continuous smooth camera move, no cuts. Do not add any text, captions, UI or watermark."
)


def _prompt_veo(movimento: str, titulo_de: str, titulo_para: str) -> str:
    return f"{movimento} The scene transforms from \"{titulo_de}\" into \"{titulo_para}\". {_ESTILO_VEO}"


def _normalizar_clipe(origem: Path, destino: Path, ritmo: float) -> bool:
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setpts=PTS/{max(0.5, ritmo):.3f},fps={FPS}"
    r = subprocess.run(
        [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(origem), "-vf", vf, "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(destino)],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and destino.exists()


def listar_modelos_veo(api_key: str) -> list[str]:
    """Nomes de modelos Veo realmente disponíveis para a chave (evita errar o ID do modelo)."""
    from google import genai
    client = genai.Client(api_key=api_key.strip())
    nomes = []
    for m in client.models.list():
        n = getattr(m, "name", "").replace("models/", "")
        if "veo" in n.lower():
            nomes.append(n)
    return sorted(set(nomes))


def _submeter_veo(client, types, modelo: str, prompt: str, ini: Image.Image, fim: Image.Image, seg: int, resolucao: str):
    cfg = dict(aspect_ratio="9:16", last_frame=types.Image(image_bytes=_png_bytes(_cover(fim, W, H)), mime_type="image/png"))
    if resolucao:
        cfg["resolution"] = resolucao
    tentativas = [seg] + ([8] if seg != 8 else [])
    ultimo = None
    for dur in tentativas:
        try:
            return client.models.generate_videos(
                model=modelo,
                prompt=prompt,
                image=types.Image(image_bytes=_png_bytes(_cover(ini, W, H)), mime_type="image/png"),
                config=types.GenerateVideosConfig(duration_seconds=dur, **cfg),
            )
        except Exception as e:
            ultimo = e
            msg = str(e).lower()
            if "duration" not in msg:       # só repete se o erro for de duração
                break
    raise ultimo


def animar_com_veo(client, types, pares: list[dict], modelo: str, seg: int, resolucao: str,
                   pasta: Path, ritmo: float, barra=None, status=None, base_pct=40, faixa_pct=45) -> dict[int, Path]:
    """pares: [{'i':int,'ini':PIL,'fim':PIL,'prompt':str}]. Envia TODOS de uma vez e aguarda juntos.
    Devolve {i: caminho_do_clipe} só para os que deram certo (o resto cai no motor local)."""
    ops: dict[int, object] = {}
    erros: dict[int, str] = {}
    for n, par in enumerate(pares):
        _s(status, f"🎬 Enviando transição {n + 1}/{len(pares)} ao Veo...")
        for tentativa in range(3):
            try:
                ops[par["i"]] = _submeter_veo(client, types, modelo, par["prompt"], par["ini"], par["fim"], seg, resolucao)
                break
            except Exception as e:
                erros[par["i"]] = str(e)[:300]
                if "429" in str(e) or "resource" in str(e).lower():
                    time.sleep(20 * (tentativa + 1))
                else:
                    break

    prontos: dict[int, Path] = {}
    pendentes = dict(ops)
    t0 = time.time()
    while pendentes and time.time() - t0 < 60 * 12:
        for i in list(pendentes):
            try:
                op = client.operations.get(pendentes[i])
                pendentes[i] = op
                if not op.done:
                    continue
                del pendentes[i]
                resp = getattr(op, "response", None)
                vids = getattr(resp, "generated_videos", None) if resp else None
                if not vids:
                    erros[i] = f"Veo não devolveu vídeo ({getattr(op, 'error', '') or 'bloqueio de conteúdo?'})"
                    continue
                bruto = pasta / f"veo_bruto_{i}.mp4"
                client.files.download(file=vids[0].video)
                vids[0].video.save(str(bruto))
                dest = pasta / f"clipe_{i}.mp4"
                if _normalizar_clipe(bruto, dest, ritmo):
                    prontos[i] = dest
                else:
                    erros[i] = "FFmpeg não conseguiu padronizar o clipe do Veo"
            except Exception as e:
                erros[i] = str(e)[:300]
                pendentes.pop(i, None)
        feitos = len(ops) - len(pendentes)
        _p(barra, base_pct + faixa_pct * (feitos / max(1, len(ops))))
        _s(status, f"⏳ Veo renderizando na nuvem: {feitos}/{len(ops)} transições prontas...")
        if pendentes:
            time.sleep(8)
    for i in pendentes:
        erros[i] = "tempo esgotado esperando o Veo"
    animar_com_veo.ultimos_erros = erros  # para o app exibir
    return prontos


animar_com_veo.ultimos_erros = {}


# ──────────────────────────────────────────────────────────────────────────────
# API PÚBLICA — usada pelo app.py
# ──────────────────────────────────────────────────────────────────────────────
def preparar_jornada(
    img_bytes: bytes, plano: dict, *, nome: str = "carta", api_key: str = "", n_cenas: int = 3,
    instrucao: str = "", usar_gemini_roteiro: bool = True, usar_gemini_imagens: bool = True,
    modelos_texto: list[str] | None = None, modelos_imagem: list[str] | None = None,
    barra=None, status=None,
) -> dict:
    """Etapa barata: escreve o roteiro e cria os keyframes (cenas). Mostre ao usuário ANTES de gastar com o Veo."""
    carta = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    seed = _seed_da_carta(img_bytes, nome)
    rng = random.Random(seed)
    n_cenas = max(1, min(6, int(n_cenas)))
    client = types = None
    if api_key and len(api_key.strip()) > 10:
        try:
            from google import genai
            from google.genai import types as _types
            client, types = genai.Client(api_key=api_key.strip()), _types
        except Exception:
            client = types = None

    avisos: list[str] = []
    _p(barra, 5)
    _s(status, "📝 Escrevendo o roteiro de cenas a partir da sua carta...")
    roteiro = None
    if client and usar_gemini_roteiro:
        roteiro = roteiro_gemini(client, types, img_bytes, plano, n_cenas, instrucao, modelos_texto or MODELOS_TEXTO_PADRAO)
        if roteiro is None:
            avisos.append("Gemini não conseguiu escrever o roteiro; usei o roteiro local.")
    if roteiro is None:
        roteiro = roteiro_local(plano, n_cenas, rng)

    regioes = _regioes_de_interesse(carta, n_cenas)
    keyframes: list[Image.Image] = [_carta_para_keyframe(carta)]
    origens = ["carta"]
    anterior: Image.Image | None = keyframes[0]
    for i, cena in enumerate(roteiro["cenas"]):
        _p(barra, 10 + 25 * (i / max(1, n_cenas)))
        _s(status, f"🎨 Criando a cena {i + 1}/{n_cenas}: {cena.get('titulo', '')}")
        kf = None
        if client and usar_gemini_imagens and cena.get("prompt_imagem"):
            kf = keyframe_gemini(client, types, img_bytes, anterior, cena["prompt_imagem"], modelos_imagem or MODELOS_IMAGEM_PADRAO)
            if kf is None:
                avisos.append(f"Cena {i + 1}: a IA de imagem falhou; usei um recorte real da carta.")
        if kf is None:
            kf = _keyframe_de_regiao(carta, regioes[i])
            origens.append("recorte")
        else:
            origens.append("ia")
        keyframes.append(kf)
        anterior = kf
    keyframes.append(_carta_para_keyframe(carta))  # volta à carta => loop perfeito
    origens.append("carta")
    _p(barra, 38)
    return {"roteiro": roteiro, "keyframes": keyframes, "origens": origens, "avisos": avisos, "seed": seed}


def animar_jornada(
    jornada: dict, saida_raw: Path, *, api_key: str = "", usar_veo: bool = False,
    modelo_veo: str = MODELO_VEO_PADRAO, seg_por_clip: int = 6, resolucao: str = "720p",
    ritmo: float = 1.0, pasta_temp: Path | None = None, barra=None, status=None,
) -> dict:
    """Etapa cara: anima cada par de keyframes (Veo ou local) e monta o vídeo final. Retorna um relatório."""
    pasta = Path(pasta_temp or "./workspace_temp")
    pasta.mkdir(parents=True, exist_ok=True)
    kfs: list[Image.Image] = jornada["keyframes"]
    trans: list[dict] = jornada["roteiro"]["transicoes"]
    cenas: list[dict] = jornada["roteiro"]["cenas"]
    n_clips = len(kfs) - 1
    rng = random.Random(jornada.get("seed", 1))
    titulos = ["a carta"] + [c.get("titulo", "cena") for c in cenas] + ["a carta"]
    relatorio = {"ok": False, "clipes": [], "erros": {}}
    if not (api_key and len(api_key.strip()) > 10):
        usar_veo = False

    clipes: dict[int, Path] = {}
    origem_clipe: dict[int, str] = {}

    if usar_veo:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key.strip())
        pares = []
        for i in range(n_clips):
            t = trans[min(i, len(trans) - 1)]
            pares.append({"i": i, "ini": kfs[i], "fim": kfs[i + 1],
                          "prompt": _prompt_veo(t.get("movimento", ""), titulos[i], titulos[i + 1])})
        feitos = animar_com_veo(client, types, pares, modelo_veo, seg_por_clip, resolucao, pasta, ritmo, barra, status)
        for i, p in feitos.items():
            clipes[i] = p
            origem_clipe[i] = "veo"
        relatorio["erros"] = dict(animar_com_veo.ultimos_erros)

    for i in range(n_clips):
        if i in clipes:
            continue
        t = trans[min(i, len(trans) - 1)]
        _p(barra, 86 + 8 * (i / max(1, n_clips)))
        _s(status, f"🎞️ Animando transição {i + 1}/{n_clips} no motor local ({t.get('tipo', 'zoom_through')})...")
        destino = pasta / f"clipe_{i}.mp4"
        tipo = t.get("tipo") if t.get("tipo") in TRANSICOES else "zoom_through"
        if _fazer_clipe_local(kfs[i], kfs[i + 1], tipo, max(3.0, seg_por_clip * 0.75), destino, rng):
            clipes[i] = destino
            origem_clipe[i] = "local"
        else:
            relatorio["erros"][i] = relatorio["erros"].get(i, "") + " | falha no clipe local"

    ordem = [clipes[i] for i in range(n_clips) if i in clipes]
    if not ordem:
        return relatorio

    lista = pasta / "concat_jornada.txt"
    with open(lista, "w", encoding="utf-8") as f:
        for c in ordem:
            caminho = c.resolve().as_posix().replace("'", "'\\''")
            f.write(f"file '{caminho}'\n")
    _s(status, "🧵 Montando o vídeo final...")
    r = subprocess.run(
        [_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(saida_raw)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        relatorio["erros"]["montagem"] = r.stderr[-600:]
    relatorio["ok"] = saida_raw.exists() and r.returncode == 0
    relatorio["clipes"] = [origem_clipe.get(i, "falhou") for i in range(n_clips)]
    _p(barra, 96)
    return relatorio

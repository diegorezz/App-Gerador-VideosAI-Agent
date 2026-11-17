"""
AI VIDEO AGENT v6 — MOTOR CINEMATOGRAFICO GENERICO
===================================================
Nucleo do motor: recebe o perfil de um arcano (analisar_carta.py) e produz
um video 9:16 de 20s. Nenhuma coordenada fixa por carta.

Principio de projeto
--------------------
O video modelo do Drive NAO e geracao de video por IA: e composicao
cinematografica em camadas (profundidade, camera, luz, particulas).
Aqui a carta e um objeto 3D dentro de uma cena, com camera em perspectiva,
paralaxe real por camada, sombra projetada e efeito elemental dirigido pela
paleta do arcano.

Modulos
-------
  camadas()      -> decompoe a carta em N planos de profundidade
  warp_layer()   -> projecao em perspectiva de cada plano (numba)
  Elemento       -> fogo / agua / luz / terra / ar
  render_frame() -> timeline de 20s
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import gaussian_filter
from numba import njit, prange

# ---------------------------------------------------------------------------
# PALETA E CONSTANTES
# ---------------------------------------------------------------------------
GOLD = np.array([1.00, 0.83, 0.42], np.float32)
AMBER = np.array([1.00, 0.72, 0.28], np.float32)
CRIMSON = np.array([0.78, 0.16, 0.13], np.float32)

FONT_CANDIDATOS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
]


def fonte(tam):
    for p in FONT_CANDIDATOS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, tam)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------
def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(t, t0, t1, v0, v1, ease=True):
    if t <= t0:
        return v0
    if t >= t1:
        return v1
    x = (t - t0) / (t1 - t0)
    if ease:
        x = x * x * (3 - 2 * x)
    return v0 + (v1 - v0) * x


def ease_io(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def ease_out(x, p=3):
    x = np.clip(x, 0, 1)
    return 1 - (1 - x) ** p


def resize_f(a, size):
    return np.asarray(
        Image.fromarray(np.ascontiguousarray(a, np.float32), "F").resize(size, Image.BILINEAR),
        np.float32,
    )


def _fbm(h, w, base, octs, seed, persist=0.5):
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for i in range(octs):
        cells = max(2, int(base * 2 ** i))
        g = rng.random((cells + 2, cells + 1), dtype=np.float32)
        a = np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC), np.float32)
        a = (a - a.min()) / (a.max() - a.min() + 1e-6)
        acc += amp * a
        tot += amp
        amp *= persist
    return acc / tot


# ---------------------------------------------------------------------------
# GEOMETRIA / CAMADAS
# ---------------------------------------------------------------------------
def camadas(card: np.ndarray, depth: np.ndarray, n: int = 3):
    """Decompoe a carta em n planos (fundo -> figura -> primeiro plano).

    Cada plano e uma copia da carta com alpha suave na sua faixa de
    profundidade. O plano mais proximo e ampliado na projecao e cobre os
    buracos deixados pelo plano de tras — composicao sem furos.
    """
    h, w = depth.shape
    cortes = np.linspace(0.18, 0.86, n + 1)
    planos = []
    for i in range(n):
        lo, hi = cortes[i], cortes[i + 1]
        if i == 0:
            a = smoothstep(hi, lo, depth)           # tudo abaixo de hi
        elif i == n - 1:
            a = smoothstep(lo, hi, depth)           # tudo acima de lo
        else:
            a = smoothstep(lo, lo + 0.10, depth) * smoothstep(hi, hi - 0.10, depth)
        a = gaussian_filter(a.astype(np.float32), 3.0)
        a = np.clip(a, 0, 1)
        # preenche cor sob as areas transparentes (evita halo nas bordas)
        cheio = card.copy()
        for c in range(3):
            cheio[..., c] = gaussian_filter(card[..., c], 9)
        rgb = card * a[..., None] + cheio * (1 - a[..., None])
        z = (i + 0.5) / n - 0.5                     # -0.5 (fundo) .. +0.5 (frente)
        planos.append({"rgb": rgb.astype(np.float32), "alpha": a, "z": z})
    return planos


# ---------------------------------------------------------------------------
# PROJECAO (numba)
# ---------------------------------------------------------------------------
@njit(parallel=True, fastmath=True)
def warp_layer(rgb, alpha, out_rgb, out_a, cx, cy, s, rot, par_x, par_y, haze, phase, zk):
    ch, cw = alpha.shape
    cosr = math.cos(rot)
    sinr = math.sin(rot)
    hw = out_rgb.shape[1] * 0.5
    hh = out_rgb.shape[0] * 0.5
    for Y in prange(out_rgb.shape[0]):
        dy = Y - hh
        for X in range(out_rgb.shape[1]):
            dx = X - hw
            rx = dx * cosr + dy * sinr
            ry = -dx * sinr + dy * cosr
            u = cx + rx / s + par_x
            v = cy + ry / s + par_y
            if haze > 0.0:
                wq = v / ch
                if wq > 0.55:
                    k = (wq - 0.55) / 0.45
                    u += haze * math.sin(v * 0.075 + phase) * k * k * 1.6
            if u < 0.0 or u > cw - 1.001 or v < 0.0 or v > ch - 1.001:
                out_a[Y, X] = 0.0
                out_rgb[Y, X, 0] = 0.0
                out_rgb[Y, X, 1] = 0.0
                out_rgb[Y, X, 2] = 0.0
                continue
            x0 = int(u)
            y0 = int(v)
            fx = u - x0
            fy = v - y0
            x1 = x0 + 1
            y1 = y0 + 1
            w00 = (1.0 - fx) * (1.0 - fy)
            w10 = fx * (1.0 - fy)
            w01 = (1.0 - fx) * fy
            w11 = fx * fy
            out_rgb[Y, X, 0] = (rgb[y0, x0, 0] * w00 + rgb[y0, x1, 0] * w10
                                + rgb[y1, x0, 0] * w01 + rgb[y1, x1, 0] * w11)
            out_rgb[Y, X, 1] = (rgb[y0, x0, 1] * w00 + rgb[y0, x1, 1] * w10
                                + rgb[y1, x0, 1] * w01 + rgb[y1, x1, 1] * w11)
            out_rgb[Y, X, 2] = (rgb[y0, x0, 2] * w00 + rgb[y0, x1, 2] * w10
                                + rgb[y1, x0, 2] * w01 + rgb[y1, x1, 2] * w11)
            out_a[Y, X] = (alpha[y0, x0] * w00 + alpha[y0, x1] * w10
                           + alpha[y1, x0] * w01 + alpha[y1, x1] * w11)


@njit(parallel=True, fastmath=True)
def warp_full(rgb, alpha, depth, out_rgb, out_a, cx, cy, s, rot, par_x, par_y, haze, phase):
    """Warp monolitico com paralaxe por pixel (mapa de profundidade).
    Preserva a integridade da gravura; o 3D vem da paralaxe, nao da separacao em planos."""
    ch, cw = depth.shape
    cosr = math.cos(rot)
    sinr = math.sin(rot)
    hw = out_rgb.shape[1] * 0.5
    hh = out_rgb.shape[0] * 0.5
    for Y in prange(out_rgb.shape[0]):
        dy = Y - hh
        for X in range(out_rgb.shape[1]):
            dx = X - hw
            rx = dx * cosr + dy * sinr
            ry = -dx * sinr + dy * cosr
            u = cx + rx / s
            v = cy + ry / s
            d = 0.0
            vi = int(v)
            ui = int(u)
            if vi >= 0 and vi < ch and ui >= 0 and ui < cw:
                d = depth[vi, ui] - 0.5
            u += d * par_x
            v += d * par_y
            if haze > 0.0:
                wq = v / ch
                if wq > 0.55:
                    k = (wq - 0.55) / 0.45
                    u += haze * math.sin(v * 0.075 + phase) * k * k * 1.6
            if u < 0.0 or u > cw - 1.001 or v < 0.0 or v > ch - 1.001:
                out_a[Y, X] = 0.0
                out_rgb[Y, X, 0] = 0.0
                out_rgb[Y, X, 1] = 0.0
                out_rgb[Y, X, 2] = 0.0
                continue
            x0 = int(u)
            y0 = int(v)
            fx = u - x0
            fy = v - y0
            x1 = x0 + 1
            y1 = y0 + 1
            w00 = (1.0 - fx) * (1.0 - fy)
            w10 = fx * (1.0 - fy)
            w01 = (1.0 - fx) * fy
            w11 = fx * fy
            out_rgb[Y, X, 0] = (rgb[y0, x0, 0] * w00 + rgb[y0, x1, 0] * w10
                                + rgb[y1, x0, 0] * w01 + rgb[y1, x1, 0] * w11)
            out_rgb[Y, X, 1] = (rgb[y0, x0, 1] * w00 + rgb[y0, x1, 1] * w10
                                + rgb[y1, x0, 1] * w01 + rgb[y1, x1, 1] * w11)
            out_rgb[Y, X, 2] = (rgb[y0, x0, 2] * w00 + rgb[y0, x1, 2] * w10
                                + rgb[y1, x0, 2] * w01 + rgb[y1, x1, 2] * w11)
            out_a[Y, X] = (alpha[y0, x0] * w00 + alpha[y0, x1] * w10
                           + alpha[y1, x0] * w01 + alpha[y1, x1] * w11)


@njit(parallel=True, fastmath=True)
def splat(img, xs, ys, sizes, intens, cr, cg, cb):
    h, w = img.shape[0], img.shape[1]
    n = xs.shape[0]
    for i in prange(n):
        cx = xs[i]
        cy = ys[i]
        r = sizes[i]
        if cx < -4 or cy < -4 or cx > w + 4 or cy > h + 4:
            continue
        rad = int(r) + 1
        amp = intens[i]
        for yy in range(-rad, rad + 1):
            py = int(cy) + yy
            if py < 0 or py >= h:
                continue
            for xx in range(-rad, rad + 1):
                px = int(cx) + xx
                if px < 0 or px >= w:
                    continue
                dist2 = (xx * xx + yy * yy) / (r * r + 1e-3)
                gg = math.exp(-dist2 * 2.2) * amp
                img[py, px, 0] += gg * cr
                img[py, px, 1] += gg * cg
                img[py, px, 2] += gg * cb


# ---------------------------------------------------------------------------
# EFEITOS ELEMENTAIS
# ---------------------------------------------------------------------------
ELEMENTOS = {
    "fogo": {"base": (0.24, 0.012, 0.004), "meio": (0.98, 0.30, 0.03),
             "nucleo": (1.00, 0.78, 0.32), "particula": (1.0, 0.55, 0.18)},
    "agua": {"base": (0.02, 0.10, 0.24), "meio": (0.10, 0.52, 0.72),
             "nucleo": (0.62, 0.92, 0.98), "particula": (0.55, 0.85, 1.0)},
    "luz":  {"base": (0.26, 0.17, 0.02), "meio": (0.95, 0.68, 0.18),
             "nucleo": (1.00, 0.93, 0.62), "particula": (1.0, 0.88, 0.55)},
    "terra": {"base": (0.12, 0.07, 0.02), "meio": (0.62, 0.40, 0.14),
              "nucleo": (0.95, 0.80, 0.50), "particula": (0.85, 0.68, 0.35)},
    "ar":   {"base": (0.10, 0.14, 0.18), "meio": (0.55, 0.72, 0.78),
             "nucleo": (0.92, 0.97, 1.00), "particula": (0.80, 0.92, 0.98)},
}


class Ruido:
    """bancos de ruido animado, dimensionados para o tamanho da carta"""

    def __init__(self, cw, ch, seed=7):
        self.cw, self.ch = cw, ch
        self.fino = np.ascontiguousarray(_fbm(ch * 3, cw, 17, 3, seed + 5, 0.55), np.float32)
        self.corpo = np.ascontiguousarray(_fbm(ch * 3, cw, 7, 4, seed + 11, 0.62), np.float32)
        self.lento = np.ascontiguousarray(_fbm(ch * 3, cw, 4, 5, seed + 23), np.float32)
        d = gaussian_filter(_fbm(ch, cw, 5, 4, seed + 31, 0.58), 3.0)
        self.diss = np.ascontiguousarray((d - d.min()) / (d.max() - d.min() + 1e-6), np.float32)

    def fatia(self, banco, off_y, off_x=0):
        h = banco.shape[0]
        oy = int(off_y) % max(1, h - self.ch - 1)
        ox = int(off_x) % max(1, banco.shape[1] - self.cw - 1)
        return banco[oy:oy + self.ch, ox:ox + self.cw]


class Elemento:
    """aplica o efeito elemental do arcano sobre a textura da carta"""

    def __init__(self, nome, ruido: Ruido, ancora=0.80):
        self.nome = nome if nome in ELEMENTOS else "fogo"
        self.c = ELEMENTOS[self.nome]
        self.r = ruido
        self.ancora = ancora        # linha y da carta onde o efeito nasce

    def aplicar(self, rgb, t, amt):
        if amt <= 0.004:
            return rgb
        a = min(amt, 1.0)
        ch, cw = rgb.shape[:2]
        ynorm = np.linspace(0, 1, ch, dtype=np.float32)[:, None]

        if self.nome == "fogo":
            campo = (0.30 * self.r.fatia(self.r.fino, -t * 520.0, 9)
                     + 0.46 * self.r.fatia(self.r.corpo, -t * 300.0, 3)
                     + 0.24 * self.r.fatia(self.r.lento, -t * 120.0, 17))
            topo = self.ancora - 0.10 - 0.34 * a
            perfil = smoothstep(topo, topo + 0.16, ynorm) ** 1.25
            limiar = 0.50 - 0.09 * a
        elif self.nome == "agua":
            dy = self.r.fatia(self.r.corpo, t * 120.0, 5)
            dx = self.r.fatia(self.r.fino, t * 90.0, 11)
            onda = 0.5 + 0.5 * np.sin(ynorm * 34.0 + dy * 7.0 + t * 2.4)
            campo = 0.45 * dy + 0.30 * dx + 0.25 * onda
            topo = 0.30
            perfil = smoothstep(topo, self.ancora, ynorm) ** 0.6
            limiar = 0.52 - 0.07 * a
        elif self.nome == "luz":
            # halo dourado emergindo da base, com raios suaves — nao cobre o quadro
            d = self.r.fatia(self.r.corpo, -t * 60.0, 3)
            yy = np.linspace(0, 1, ch, dtype=np.float32)[:, None]
            xx = np.linspace(0, 1, cw, dtype=np.float32)[None, :]
            rad = np.hypot((xx - 0.5) * 0.85, (yy - self.ancora) * 1.25)
            halo = np.clip(1.0 - rad * 1.35, 0, 1) ** 1.4
            raios = 0.5 + 0.5 * np.sin(np.arctan2(yy - self.ancora, xx - 0.5) * 13.0 + t * 0.9)
            campo = 0.45 * d + 0.55 * halo
            perfil = (halo ** 0.85) * (0.72 + 0.28 * raios)
            limiar = 0.58 - 0.06 * a
        elif self.nome == "terra":
            campo = (0.45 * self.r.fatia(self.r.corpo, -t * 40.0, 13)
                     + 0.35 * self.r.fatia(self.r.lento, -t * 25.0, 21)
                     + 0.20 * self.r.fatia(self.r.fino, -t * 70.0, 5))
            perfil = smoothstep(0.08, self.ancora, ynorm) ** 0.9
            limiar = 0.62 - 0.07 * a
        else:  # ar
            campo = (0.5 * self.r.fatia(self.r.corpo, -t * 200.0, 7)
                     + 0.5 * self.r.fatia(self.r.fino, -t * 300.0, 19))
            swirl = 0.5 + 0.5 * np.sin(ynorm * 22.0 + t * 3.1)
            campo = campo * (0.7 + 0.3 * swirl)
            perfil = np.ones((ch, 1), np.float32) * 0.9
            limiar = 0.55 - 0.08 * a

        w = np.clip((campo - limiar) / 0.20, 0, 1)
        w = np.clip(w * 1.35, 0, 1) * perfil * a
        w = gaussian_filter(w, 0.7)

        c0 = np.array(self.c["base"], np.float32)
        c1 = np.array(self.c["meio"], np.float32)
        c2 = np.array(self.c["nucleo"], np.float32)
        k1 = smoothstep(0.02, 0.40, w)[..., None]
        k2 = smoothstep(0.62, 0.97, w)[..., None]
        col = c0 + (c1 - c0) * k1
        col = col + (c2 - col) * k2 * 0.85

        teto = 0.82 if self.nome == "luz" else 1.0
        al = np.clip(w * 2.3, 0, 1)[..., None] * teto
        out = rgb * (1 - al) + col * al
        brilho = gaussian_filter(np.clip(w, 0, 1), 18)[..., None]
        ganho = 0.32 if self.nome == "luz" else 0.45
        out = out + brilho * c1 * (ganho + 0.22 * a)
        return np.clip(out, 0, 1.9)


# ---------------------------------------------------------------------------
# CENA
# ---------------------------------------------------------------------------
class Cena:
    """ambiente de fundo: gradiente, montanhas, neblina, sol, estrelas"""

    def __init__(self, W, H, paleta_rgb, seed=3):
        self.W, self.H = W, H
        self.YY = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.XX = np.linspace(0, 1, W, dtype=np.float32)[None, :]

        # cor de ceu derivada da paleta da carta (tom mais escuro e frio)
        escura = min(paleta_rgb, key=lambda c: sum(c))
        clara = max(paleta_rgb, key=lambda c: sum(c))
        ceu = np.array(escura, np.float32) / 255.0 * 0.32
        chao = np.array(escura, np.float32) / 255.0 * 0.12
        self.grad = np.ascontiguousarray(
            np.broadcast_to(self.YY[..., None] * chao + (1 - self.YY[..., None]) * ceu,
                            (H, W, 3)), np.float32)

        self.mtn_far = self._montanha(0.60, 0.045, 1.1, seed, ceu * 1.9 + 0.02, 16)
        self.mtn_near = self._montanha(0.74, 0.055, 0.8, seed + 6, ceu * 1.1 + 0.01, 12)

        n = gaussian_filter(_fbm(H // 2, W // 2, 3, 4, seed + 40), 8)
        n = np.clip((n - 0.35) * 2.0, 0, 1)
        self.fog = np.stack([resize_f(n, (W, H))] * 3, -1) * (ceu * 3.0 + 0.03)

        vx = (self.XX - 0.5) * 2
        vy = (self.YY - 0.5) * 2
        self.vign = np.clip(1.0 - 0.72 * np.clip((vx ** 2 * 0.85 + vy ** 2 * 0.62) - 0.22, 0, 3), 0, 1)[..., None].astype(np.float32)
        self.grain = [np.random.default_rng(100 + i).standard_normal((H, W)).astype(np.float32) * 0.018 for i in range(6)]

        rng = np.random.default_rng(seed + 8)
        n_st = 190
        self.st = {
            "x": rng.random(n_st).astype(np.float32),
            "y": rng.random(n_st).astype(np.float32),
            "sz": (0.5 + rng.random(n_st) ** 2.4 * 2.2).astype(np.float32),
            "ph": (rng.random(n_st) * 6.283).astype(np.float32),
        }
        n_p = 240
        self.pt = {
            "x": rng.random(n_p).astype(np.float32),
            "y": rng.random(n_p).astype(np.float32),
            "spd": (0.04 + rng.random(n_p) ** 2 * 0.30).astype(np.float32),
            "sz": (0.6 + rng.random(n_p) ** 3 * 2.4).astype(np.float32),
            "ph": (rng.random(n_p) * 6.283).astype(np.float32),
            "drift": (rng.random(n_p) - 0.5).astype(np.float32),
        }
        # nebulosa / coroa estática
        self.jit = resize_f(_fbm(W // 4, H // 4, 6, 3, seed + 57), (W, H))

    def _montanha(self, y_base, amp, freq, seed, cor, soft):
        rng = np.random.default_rng(seed)
        xs = np.linspace(0, 1, self.W, dtype=np.float32)
        y = np.full(self.W, y_base, np.float32)
        a, f = amp, freq
        for _ in range(5):
            ph = rng.random() * 6.283
            y += a * np.sin(2 * math.pi * f * xs + ph)
            a *= 0.55
            f *= 2.1
        m = gaussian_filter((self.YY > y[None, :]).astype(np.float32), (soft, 1.2))
        return (m[..., None] * np.clip(np.array(cor, np.float32), 0, 1)).astype(np.float32)

    def fundo(self, t, dissolve, cel, cor_luz):
        bg = self.grad.copy()
        bg += self.fog * (0.55 + 0.45 * math.sin(t * 0.5))
        esc = max(dissolve, cel)

        if dissolve > 0.004:
            gx, gy = 0.46, 0.97
            dg = np.hypot((self.XX - gx) * 0.60, (self.YY - gy) * 1.55)
            bg += (np.exp(-(dg / 0.30) ** 2 * 2.3) * dissolve)[..., None] * cor_luz * 0.34
            bg += (np.exp(-(dg / 0.85) ** 2 * 1.5) * dissolve)[..., None] * cor_luz * 0.22

        bg += self.mtn_far * (0.55 * (0.4 + esc))
        bg += self.mtn_near * (0.85 * (0.3 + 0.7 * esc))
        if esc > 0.01:
            bg += self.mtn_near * cor_luz * esc * 0.55
            bg *= (1 + 0.10 * esc)

        st = t if cel > 0.003 else None
        if st is not None:
            tw = 0.55 + 0.45 * np.sin(t * 3.1 + self.st["ph"])
            amp = (cel * 0.55 * tw * (0.5 + 0.5 * np.clip(self.st["y"] * 1.4, 0, 1))).astype(np.float32)
            bg = np.ascontiguousarray(bg, np.float32)
            splat(bg, (self.st["x"] * self.W).astype(np.float32),
                  (self.st["y"] * self.H * 0.72).astype(np.float32),
                  self.st["sz"], amp, 1.0, 0.94, 0.82)

        if cel > 0.003:
            rise = ease_out(np.clip((t - 8.2) / 2.6, 0, 1))
            scx, scy = 0.5, 0.68 - 0.20 * rise
            rr = 0.150 + 0.032 * rise
            dd = np.hypot(self.XX - scx, (self.YY - scy) * self.H / self.W)
            tex = resize_f(gaussian_filter(self.jit, 2.0), (self.W, self.H))
            tex = 0.62 + 0.62 * tex
            disco = smoothstep(rr, rr * 0.82, dd) * tex
            limbo = smoothstep(rr * 0.82, rr * 0.42, dd)
            nucleo = disco * (0.52 + 0.40 * limbo)
            halo = np.exp(-(dd / (rr * 2.6)) ** 2 * 2.0)
            halo2 = np.exp(-(dd / (rr * 6.2)) ** 2 * 1.5)
            bg += nucleo[..., None] * cor_luz * 1.35 * cel
            bg += halo[..., None] * cor_luz * 0.62 * cel
            bg += halo2[..., None] * cor_luz * 0.34 * cel
            anel = np.exp(-((dd - rr * 1.04) / (rr * 0.07)) ** 2) * cel * 0.55
            bg += anel[..., None] * cor_luz * 1.5
            # coroa irregular
            ang = np.arctan2((self.YY - scy) * self.H / self.W, self.XX - scx)
            spikes = np.clip((0.45 + 0.55 * np.sin(ang * 11.0 + t * 1.1)
                              * np.sin(ang * 5.0 - t * 0.8 + 1.1)
                              * np.sin(ang * 19.0 + t * 1.9)) * (0.35 + 1.15 * self.jit), 0, 2.2)
            prot = np.exp(-((dd - rr * (1.02 + 0.10 * spikes)) / (rr * 0.10)) ** 2) * spikes
            bg += (prot * cel * 0.45)[..., None] * cor_luz * 1.2
        return bg

    def particulas(self, img, t, amt, cor):
        if amt <= 0.004:
            return img
        p = self.pt
        y = (p["y"] - t * p["spd"]) % 1.0
        x = (p["x"] + 0.03 * np.sin(t * 0.8 + p["ph"]) + p["drift"] * 0.05 * t) % 1.0
        fade = np.clip(1.0 - np.abs(y - 0.55) * 1.2, 0, 1) ** 1.3
        tw = 0.45 + 0.55 * np.abs(np.sin(t * 2.6 + p["ph"]))
        inten = (amt * fade * tw * 1.5).astype(np.float32)
        out = np.ascontiguousarray(img, np.float32)
        splat(out, (x * self.W).astype(np.float32), ((1.0 - y) * self.H).astype(np.float32),
              p["sz"], inten, float(cor[0]), float(cor[1]), float(cor[2]))
        return out


# ---------------------------------------------------------------------------
# ROTEIRO (timeline de 20s)
# ---------------------------------------------------------------------------
@dataclass
class Roteiro:
    """curvas de controle do video. Altere aqui para mudar o ritmo."""
    dur: float = 20.0
    t_push: tuple = (1.8, 4.2)     # push-in no foco
    t_elem: tuple = (4.1, 6.0)     # efeito elemental entra
    t_dis: tuple = (7.2, 9.0)      # dissolucao
    t_cel: tuple = (8.2, 10.2)     # revelacao celestial
    t_volta: tuple = (11.4, 14.2)  # retorno da carta
    t_fim: float = 14.2
    zoom_foco: float = 1.95
    zoom_elem: float = 1.36
    zoom_fora: float = 0.58

    def curvas(self, t):
        c = {}
        c["elemento"] = (ramp(t, self.t_elem[0], self.t_elem[1], 0, 1.0)
                         * (1 - ramp(t, 6.6, 8.0, 0, 0.55))
                         * (1 - ramp(t, 8.4, 10.2, 0, 1.0)))
        c["brilho"] = ramp(t, self.t_elem[0] - 0.1, self.t_elem[1] + 0.4, 0, 0.55) * (1 - ramp(t, 9.0, 10.4, 0, 0.9))
        c["tinta"] = ramp(t, 1.6, 3.4, 0, 0.9) * (1 - ramp(t, 9.2, 11.0, 0, 0.9))
        c["celestial"] = ramp(t, self.t_cel[0], self.t_cel[1], 0, 1.0) * (1 - ramp(t, 12.0, 13.6, 0, 1.0))
        c["dissolve"] = ramp(t, self.t_dis[0], self.t_dis[1], 0, 1.02) * (1 - ramp(t, 11.2, 12.6, 0, 1.0))
        c["vanish"] = ramp(t, 8.6, 9.6, 0, 1.0) * (1 - ramp(t, 11.3, 12.3, 0, 1.0))
        c["rim"] = ramp(t, 11.4, 13.0, 0, 1.0) * (1 - ramp(t, 13.6, 15.4, 0, 1.0))
        c["fade_in"] = ramp(t, 0.0, 1.1, 0, 1.0)
        c["fade_out"] = ramp(t, self.dur - 1.3, self.dur, 0, 1.0)
        c["shake"] = ramp(t, 4.4, 5.6, 0, 1.0) * (1 - ramp(t, 6.4, 7.2, 0, 1.0))
        c["particulas"] = ramp(t, 0.6, 2.2, 0, 0.55) + ramp(t, 4.2, 6.4, 0, 0.55) * (1 - ramp(t, 15, 18, 0, 0.4))
        c["estrelas"] = ramp(t, 8.6, 10.4, 0, 1.0) * (1 - ramp(t, 12.0, 13.6, 0, 0.75))
        c["bloom"] = 0.07 + 0.11 * c["elemento"] + 0.07 * c["brilho"] + 0.12 * c["celestial"]
        c["flash"] = (ramp(t, 4.15, 4.55, 0, 0.22) * (1 - ramp(t, 4.55, 5.2, 0, 1))
                      + ramp(t, 12.95, 13.4, 0, 0.40) * (1 - ramp(t, 13.4, 14.4, 0, 1)))
        return c


def camera(t, rt: Roteiro, card_w, card_h, s_full, foco):
    """retorna cx, cy, s, rot, par_x, par_y em px da carta"""
    fx = foco["x"] * card_w
    fy = foco["y"] * card_h
    cx, cy, s, rot = card_w * 0.5, card_h * 0.5, s_full * 0.96, 0.0
    px = py = 0.0

    if t < 1.8:
        k = ease_out(t / 1.8)
        s = s_full * (0.925 + 0.035 * k)
        rot = math.radians(-0.5 + 0.5 * k)
        px, py = 7 * math.sin(t * 1.1), 5 * math.cos(t * 0.9)
    elif t < rt.t_push[1]:
        k = ease_io((t - 1.8) / (rt.t_push[1] - 1.8))
        cx = card_w * 0.5 + (fx - card_w * 0.5) * k
        cy = card_h * 0.5 + (fy - card_h * 0.5) * k
        s = s_full * (0.96 + (rt.zoom_foco - 0.96) * k)
        rot = math.radians(-0.2 + 1.7 * k)
        px, py = 24 * k, 16 * k
    elif t < 6.9:
        k = ease_io((t - rt.t_push[1]) / (6.9 - rt.t_push[1]))
        cx = card_w * (fx / card_w) + (card_w * 0.44 - fx) * k
        cy = card_h * (fy / card_h) + (card_h * 0.72 - fy) * k
        s = s_full * (rt.zoom_foco + (rt.zoom_elem - rt.zoom_foco) * k)
        rot = math.radians(1.5 - 2.1 * k)
        px, py = 24 - 10 * k, 16 + 26 * k
    elif t < 9.4:
        k = ease_io((t - 6.9) / 2.5)
        cx = card_w * (0.44 + (0.50 - 0.44) * k)
        cy = card_h * (0.72 + (0.55 - 0.72) * k)
        s = s_full * (rt.zoom_elem + (rt.zoom_fora - rt.zoom_elem) * k)
        rot = math.radians(-0.6 + 1.0 * k)
        px, py = 14 + 46 * k, 42 + 76 * k
    elif t < 11.4:
        k = (t - 9.4) / 2.0
        ke = ease_io(k)
        cx = card_w * 0.5
        cy = card_h * (0.55 - 0.05 * ke)
        s = s_full * (rt.zoom_fora + 0.07 * ke)
        rot = math.radians(0.4 - 0.4 * ke)
        px, py = 60 - 26 * ke, 118 - 44 * ke
    elif t < rt.t_volta[1]:
        k = ease_io((t - rt.t_volta[0]) / (rt.t_volta[1] - rt.t_volta[0]))
        cx = card_w * 0.5
        cy = card_h * (0.50 + 0.02 * math.sin(k * math.pi))
        s = s_full * (0.56 + (0.92 - 0.56) * k)
        rot = 0.0
        px, py = 34 * (1 - k), 74 * (1 - k)
    else:
        k = ease_io((t - rt.t_fim) / (rt.dur - rt.t_fim))
        cx, cy = card_w * 0.5, card_h * (0.478 + 0.006 * k)
        s = s_full * (0.92 + 0.030 * k)
        rot = 0.0
        px, py = 5 * math.sin(t * 0.7), 3 * math.cos(t * 0.6)
    return cx, cy, s, rot, px, py


# ---------------------------------------------------------------------------
# RENDERIZADOR
# ---------------------------------------------------------------------------
class MotorV6:
    """motor completo: carta + perfil -> frames -> mp4"""

    def __init__(self, card_img: Image.Image, depth: np.ndarray, perfil: dict,
                 W=720, H=1280, fps=30, roteiro: Roteiro | None = None):
        self.W, self.H, self.fps = W, H, fps
        self.rt = roteiro or Roteiro()
        self.perfil = perfil
        self.nome = perfil.get("nome_arcano") or perfil.get("arquivo", "ARCANO")

        # normaliza a carta para uma altura de trabalho
        card_h = 1069
        card_w = int(round(card_h * card_img.width / card_img.height))
        self.card_w, self.card_h = card_w, card_h
        card = np.asarray(card_img.resize((card_w, card_h), Image.LANCZOS), np.float32) / 255.0
        self.card = card

        dep = np.asarray(Image.fromarray(np.ascontiguousarray(depth, np.float32), "F")
                         .resize((card_w, card_h), Image.BILINEAR), np.float32)
        self.depth = (dep - dep.min()) / (dep.max() - dep.min() + 1e-6)

        lum = card @ np.array([0.299, 0.587, 0.114], np.float32)
        gy, gx = np.gradient(gaussian_filter(lum, 1.2))
        self.edge = gaussian_filter(np.clip(np.hypot(gx, gy) * 3.2, 0, 1), 1.0).astype(np.float32)

        self.planos = camadas(card, self.depth, n=3)
        self.ruido = Ruido(card_w, card_h)
        self.elem = Elemento(perfil.get("elemento", "fogo"), self.ruido,
                             ancora=perfil.get("geometria", {}).get("piso_y", 0.86))

        pal = [c["rgb"] for c in perfil.get("paleta", [])[:6]] or [[200, 160, 110]]
        self.cena = Cena(W, H, pal, seed=hash(self.nome) % 1000)
        self.s_full = 1.12
        self.cor_luz = np.array(ELEMENTOS[self.elem.nome]["meio"], np.float32)

        # graos de poeira na superficie da carta
        rng = np.random.default_rng(31)
        n = 150
        self.dust = {"x": rng.random(n).astype(np.float32), "y": rng.random(n).astype(np.float32),
                     "sz": (0.7 + rng.random(n) ** 2 * 2.4).astype(np.float32),
                     "ph": (rng.random(n) * 6.283).astype(np.float32),
                     "v": (0.010 + rng.random(n) * 0.05).astype(np.float32)}

    # -- superficie da carta ------------------------------------------------
    def _superficie(self, t, c):
        rgb = self.card.copy()
        rgb = (rgb - 0.5) * (1.09 + 0.12 * max(c["elemento"], c["celestial"] * 0.6)) + 0.5
        rgb *= np.array([1.03, 1.0, 0.97], np.float32)

        if t < 3.2:
            sk = math.exp(-((t - 1.5) / 0.85) ** 2) * 0.22
            if sk > 0.004:
                sweep = np.clip(1.0 - np.abs(
                    np.linspace(0, 1, self.card_w)[None, :] * 0.6
                    + np.linspace(0, 1, self.card_h)[:, None] * 0.8
                    - (0.15 + t * 0.55)) * 2.6, 0, 1)
                rgb = rgb + sweep[..., None] * GOLD * sk

        if c["tinta"] > 0.003:
            pulse = 0.85 + 0.15 * math.sin(t * 2.4)
            rgb = rgb + self.edge[..., None] * AMBER * c["tinta"] * 0.55 * pulse

        if c["brilho"] > 0.003:
            yy = np.linspace(0, 1, self.card_h, dtype=np.float32)[:, None]
            xx = np.linspace(0, 1, self.card_w, dtype=np.float32)[None, :]
            r = np.hypot((xx - 0.5) * 0.62, (yy - 0.86))
            g = np.exp(-(r / 0.62) ** 2 * 2.6) * c["brilho"] * (0.45 if self.elem.nome == "luz" else 1.0)
            rgb = rgb + g[..., None] * GOLD * 0.42

        rgb = self.elem.aplicar(rgb, t, c["elemento"])

        if c["celestial"] > 0.003:
            rgb = rgb * (1 - 0.35 * c["celestial"]) + 0.02 * c["celestial"]

        if c["rim"] > 0.004:
            rgb = rgb + np.clip(self.edge * 2.2, 0, 1)[..., None] * GOLD * (0.42 * c["rim"])
            rgb = rgb + 0.018 * c["rim"]

        # poeira
        amt = 0.9 * max(c["tinta"], c["elemento"], c["celestial"]) + 0.25 * c["fade_in"]
        if amt > 0.004:
            d = self.dust
            y = (d["y"] - t * d["v"]) % 1.0
            x = (d["x"] + 0.02 * np.sin(t * 1.1 + d["ph"])) % 1.0
            tw = 0.35 + 0.65 * np.abs(np.sin(t * 2.1 + d["ph"]))
            rgb = np.ascontiguousarray(rgb, np.float32)
            splat(rgb, (x * self.card_w).astype(np.float32), (y * self.card_h).astype(np.float32),
                  d["sz"], (amt * tw * 0.85).astype(np.float32), 1.0, 0.82, 0.48)
        return np.clip(rgb, 0, 2.0)

    def _alpha_carta(self, c):
        if c["dissolve"] <= 0.002:
            return np.ones((self.card_h, self.card_w), np.float32)
        a = np.clip(1.0 - c["dissolve"] * (1.25 - 0.55 * self.ruido.diss), 0, 1)
        return (a ** 0.85).astype(np.float32)

    # -- frame --------------------------------------------------------------
    def render_frame(self, t):
        c = self.rt.curvas(t)
        rgb = self._superficie(t, c)
        alfa = self._alpha_carta(c)
        cx, cy, s, rot, px, py = camera(t, self.rt, self.card_w, self.card_h, self.s_full,
                                        self.perfil.get("foco_principal", {"x": 0.5, "y": 0.35}))

        fg = np.zeros((self.H, self.W, 3), np.float32)
        fa = np.zeros((self.H, self.W), np.float32)
        haze = 2.2 * c["elemento"] if self.elem.nome == "fogo" else 0.0

        # sombra projetada (a carta e um objeto fisico sobre o cenario)
        off = 10 + 6 * math.sin(t * 0.6)
        sombra_a = np.zeros((self.H, self.W), np.float32)
        sr = np.zeros((self.H, self.W, 3), np.float32)
        warp_full(np.ascontiguousarray(self.card * 0.03, np.float32),
                  np.ascontiguousarray(alfa, np.float32), self.depth,
                  sr, sombra_a, cx + off, cy + off * 0.6, s * 1.004, rot, px, py, 0.0, 0.0)
        sombra_a = gaussian_filter(sombra_a, 9) * 0.55 * (1.0 - c["vanish"])

        warp_full(np.ascontiguousarray(rgb, np.float32), np.ascontiguousarray(alfa, np.float32),
                  self.depth, fg, fa, cx, cy, s, rot, px, py, haze, t * 9.0)

        if c["vanish"] > 0.002:
            fa *= (1 - 0.97 * c["vanish"])

        bg = self.cena.fundo(t, c["dissolve"], c["celestial"], self.cor_luz)
        bg = bg * (1 - sombra_a[..., None] * 0.8)
        out = fg * fa[..., None] + bg * (1 - fa[..., None])

        out = self.cena.particulas(out, t, c["particulas"], ELEMENTOS[self.elem.nome]["particula"])
        if c["celestial"] > 0.01:
            out = self.cena.particulas(out, t + 3.0, c["celestial"] * 0.5,
                                       ELEMENTOS[self.elem.nome]["particula"])

        out = self._bloom(out, c["bloom"])
        out = out + c["flash"] * 0.9
        out = out + self.cena.vign * 0 - (1 - self.cena.vign) * out * 0.0   # noop seguro
        out = out * self.cena.vign
        out = out + self.cena.grain[int(t * 12) % 6][..., None]
        out = out * c["fade_in"] * (1 - c["fade_out"])
        u8 = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
        return self._legenda(u8, t, c)

    def _bloom(self, img, amount):
        if amount <= 0.01:
            return img
        small = np.asarray(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
                           .resize((self.W // 4, self.H // 4), Image.BILINEAR), np.float32) / 255.0
        bright = np.stack([gaussian_filter(np.clip(small[..., i] - 0.62, 0, 1) * 2.2, 5)
                           for i in range(3)], -1)
        up = np.stack([resize_f(bright[..., i], (self.W, self.H)) for i in range(3)], -1)
        return img + up * amount

    def _legenda(self, u8, t, c):
        a = ramp(t, 15.6, 16.8, 0, 1) * (1 - ramp(t, 18.4, 19.6, 0, 1))
        if a <= 0.01:
            return u8
        im = Image.fromarray(u8).convert("RGBA")
        layer = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        f1, f2 = fonte(30), fonte(15)

        def spaced(draw, xy, text, fnt, fill, track):
            x, y = xy
            tot = sum(draw.textlength(ch, font=fnt) + track for ch in text) - track
            x -= tot / 2
            for ch in text:
                draw.text((x, y), ch, font=fnt, fill=fill)
                x += draw.textlength(ch, font=fnt) + track

        nome = (self.perfil.get("nome_arcano") or "").upper() or "ARCANO"
        sub = self.perfil.get("subtitulo") or "ARCANO"
        yb = self.H * 0.955
        spaced(d, (self.W / 2, yb), nome, f1, (255, 231, 178, int(252 * a)), 10)
        spaced(d, (self.W / 2, yb + 42), sub, f2, (233, 203, 150, int(210 * a)), 4.2)
        d.line([(self.W / 2 - 74, yb - 12), (self.W / 2 + 74, yb - 12)],
               fill=(214, 178, 116, int(120 * a)), width=1)
        im = Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(10)))
        im = Image.alpha_composite(im, layer)
        return np.asarray(im.convert("RGB"))

    # -- saida --------------------------------------------------------------
    def render_video(self, saida="video.mp4", n_frames=None, log=print):
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        total = n_frames or int(self.rt.dur * self.fps)
        cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{self.W}x{self.H}", "-r", str(self.fps), "-i", "-", "-an",
               "-c:v", "libx264", "-preset", "medium", "-crf", "19",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", saida]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        for i in range(total):
            p.stdin.write(self.render_frame(i / self.fps).tobytes())
            if i % 60 == 0:
                log(f"  frame {i}/{total}")
        p.stdin.close()
        p.wait()
        return saida


def carregar_perfil(caminho_img, base_perfis="engine/perfis"):
    """carrega perfil json do arcano; se nao existir, analisa na hora"""
    nome = os.path.splitext(os.path.basename(caminho_img))[0]
    j = os.path.join(base_perfis, nome + ".json")
    if os.path.exists(j):
        with open(j, encoding="utf-8") as f:
            return json.load(f)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from analisar_carta import analisar
    perfil, _, _ = analisar(caminho_img)
    return perfil

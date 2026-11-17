"""
AI VIDEO AGENT v6 — Audio Engine
Trilha sonora 100% sintetizada e sincronizada com a timeline de 20s.

Regra de projeto: nenhum asset externo. Tudo nasce de numpy/scipy, o que
mantem o app gratuito, offline e deterministico no Streamlit Cloud.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 32000

# paleta sonora por elemento — o arcano escolhe o clima
TONALIDADES = {
    "fogo":  {"drone": [55.00, 82.41, 110.00, 164.81], "acorde": [146.83, 220.00, 293.66, 440.00],
              "sino": [587.33, 880.00, 1174.66], "textura": "fogo"},
    "agua":  {"drone": [49.00, 73.42, 98.00, 146.83], "acorde": [130.81, 196.00, 261.63, 392.00],
              "sino": [523.25, 783.99, 1046.50], "textura": "agua"},
    "luz":   {"drone": [65.41, 98.00, 130.81, 196.00], "acorde": [174.61, 261.63, 349.23, 523.25],
              "sino": [698.46, 1046.50, 1396.91], "textura": "luz"},
    "terra": {"drone": [43.65, 65.41, 87.31, 130.81], "acorde": [116.54, 174.61, 233.08, 349.23],
              "sino": [466.16, 698.46, 932.33], "textura": "terra"},
    "ar":    {"drone": [58.27, 87.31, 116.54, 174.61], "acorde": [155.56, 233.08, 311.13, 466.16],
              "sino": [622.25, 932.33, 1244.51], "textura": "ar"},
}


def _lp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), btype="low", output="sos"), x).astype(np.float32)


def _hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), btype="high", output="sos"), x).astype(np.float32)


def _bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo / (SR / 2), hi / (SR / 2)], btype="band", output="sos"), x).astype(np.float32)


class Trilha:
    """gera o WAV de 20s casado com as curvas do roteiro"""

    def __init__(self, elemento="fogo", dur=20.0, seed=11):
        self.dur = dur
        self.n = int(SR * dur)
        self.t = np.arange(self.n) / SR
        self.rng = np.random.default_rng(seed)
        self.el = elemento if elemento in TONALIDADES else "fogo"
        self.cfg = TONALIDADES[self.el]
        self.L = np.zeros(self.n, np.float32)
        self.R = np.zeros(self.n, np.float32)

    # -- utilidades ---------------------------------------------------------
    def _curva(self, points):
        xs = np.array([p[0] for p in points], np.float32)
        ys = np.array([p[1] for p in points], np.float32)
        return np.interp(self.t, xs, ys).astype(np.float32)

    def _add(self, sig, pan=0.0, gain=1.0):
        l = np.sqrt(0.5 * (1 - pan))
        r = np.sqrt(0.5 * (1 + pan))
        m = min(len(sig), self.n)
        self.L[:m] += sig[:m] * gain * l
        self.R[:m] += sig[:m] * gain * r

    def _reverb(self, x, decay=2.6, mix=0.35, size=0.35):
        n_ir = int(SR * decay)
        tt = np.arange(n_ir) / SR
        ir = self.rng.standard_normal(n_ir) * np.exp(-tt / (decay * size))
        ir = _lp(ir, 5000)
        ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        wet = fftconvolve(x, ir, mode="full")[: self.n].astype(np.float32)
        return (1 - mix) * x + mix * wet

    def _whoosh(self, t0, t1, lo, hi, gain=1.0, up=True):
        n = int((t1 - t0) * SR)
        if n <= 0:
            return None
        nz = self.rng.standard_normal(n).astype(np.float32)
        x = np.linspace(0, 1, n)
        a = _bp(nz, lo, hi)
        b = _bp(nz, lo * 2.2, min(hi * 2.4, SR / 2 - 100))
        k = x if up else 1 - x
        out = (a * (1 - k) + b * k) * np.sin(np.pi * x) ** 1.6 * gain
        buf = np.zeros(self.n, np.float32)
        i0 = int(t0 * SR)
        m = min(n, self.n - i0)
        if m > 0:
            buf[i0:i0 + m] = out[:m]
        return buf

    def _sino(self, freq, t0, gain=1.0, dur=3.0, pan=0.0):
        n = int(dur * SR)
        if n <= 0:
            return
        tt = np.arange(n) / SR
        s = np.zeros(n, np.float32)
        for k, (r, a) in enumerate([(1.0, 1.0), (2.01, 0.55), (2.98, 0.28),
                                    (4.05, 0.18), (5.42, 0.10), (6.8, 0.06)]):
            s += a * np.sin(2 * np.pi * freq * r * tt) * np.exp(-tt * (2.2 + 1.5 * k))
        s *= np.minimum(1, tt / 0.004) * gain
        buf = np.zeros(self.n, np.float32)
        i0 = int(t0 * SR)
        m = min(n, self.n - i0)
        if m > 0:
            buf[i0:i0 + m] = s[:m]
        self._add(self._reverb(buf, 4.0, 0.55, 0.55), pan)

    # -- camadas ------------------------------------------------------------
    def _drone(self):
        amp = self._curva([(0, 0), (0.6, 0.35), (2.0, 0.5), (4.2, 0.62), (6.8, 0.75),
                           (9.0, 0.85), (11.6, 0.78), (14.4, 0.58), (18.6, 0.45), (self.dur, 0)])
        d = np.zeros(self.n, np.float32)
        for f in self.cfg["drone"]:
            drift = 1 + 0.0016 * np.sin(2 * np.pi * 0.07 * self.t + f)
            d += np.sin(2 * np.pi * f * self.t * drift + self.rng.random() * 6.28)
        self._add(self._reverb(_lp(d, 700) * amp * 0.10, 3.2, 0.45), 0.0)

    def _pulso(self):
        p = np.zeros(self.n, np.float32)
        for k, tt in enumerate([0.9, 2.1, 3.3, 4.35, 5.5, 6.6, 7.7, 8.8]):
            i = int(tt * SR)
            ln = int(0.55 * SR)
            if i + ln >= self.n:
                break
            e = np.exp(-np.linspace(0, 7, ln))
            sw = np.sin(2 * np.pi * (58 - 18 * np.linspace(0, 1, ln)) * np.linspace(0, 0.55, ln))
            p[i:i + ln] += (sw * e * (0.9 - 0.05 * k)).astype(np.float32)
        self._add(self._reverb(_lp(p, 180), 2.0, 0.25), 0.0, 0.5)

    def _textura(self):
        """rugido/estalo (fogo), agua, vento ou terra conforme o elemento"""
        if self.el == "fogo":
            amp = self._curva([(0, 0), (4.0, 0), (4.6, 0.55), (6.0, 1.0), (6.8, 0.8),
                               (8.0, 0.35), (9.2, 0.08), (10.2, 0), (self.dur, 0)])
            nz = self.rng.standard_normal(self.n).astype(np.float32)
            roar = _lp(nz, 900) * 0.55 + _bp(nz, 120, 500) * 0.75
            crack = np.zeros(self.n, np.float32)
            idx = self.rng.integers(int(4.2 * SR), int(9.6 * SR), 320)
            for i, a_ in zip(idx, self.rng.random(320) ** 2.2):
                ln = int(SR * (0.002 + self.rng.random() * 0.012))
                if i + ln >= self.n:
                    continue
                crack[i:i + ln] += self.rng.standard_normal(ln).astype(np.float32) * np.exp(-np.linspace(0, 6, ln)) * (0.9 * a_)
            self._add(self._reverb(((roar * 0.55 + _hp(crack, 900) * 0.55) * amp) * 0.85, 1.4, 0.28), -0.1)
            # boom de ignicao
            i = int(4.25 * SR)
            ln = int(1.6 * SR)
            e = np.exp(-np.linspace(0, 5.5, ln))
            boom = np.sin(2 * np.pi * (52 - 26 * np.linspace(0, 1, ln)) * np.linspace(0, 1.6, ln)) * e
            buf = np.zeros(self.n, np.float32)
            if i + ln < self.n:
                buf[i:i + ln] = boom.astype(np.float32)
            self._add(self._reverb(_lp(buf, 140), 2.6, 0.3), 0.0, 0.6)
        elif self.el == "agua":
            amp = self._curva([(0, 0), (3.8, 0), (4.6, 0.7), (6.4, 1.0), (8.4, 0.5),
                               (10.0, 0.12), (self.dur, 0)])
            nz = self.rng.standard_normal(self.n).astype(np.float32)
            mar = _bp(nz, 90, 700) * 0.8 + _lp(nz, 300) * 0.4
            swell = 0.6 + 0.4 * np.sin(2 * np.pi * 0.22 * self.t)
            self._add(self._reverb((mar * swell * amp) * 0.7, 2.2, 0.35), 0.0)
        elif self.el == "ar":
            amp = self._curva([(0, 0), (3.6, 0), (4.8, 0.8), (6.6, 1.0), (9.0, 0.4),
                               (10.5, 0.1), (self.dur, 0)])
            nz = self.rng.standard_normal(self.n).astype(np.float32)
            vento = _bp(nz, 300, 2200) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.15 * self.t))
            self._add(self._reverb(vento * amp * 0.55, 2.4, 0.4), 0.1)
        else:  # terra / luz
            amp = self._curva([(0, 0), (3.8, 0), (4.6, 0.6), (6.2, 1.0), (8.6, 0.45),
                               (10.0, 0.1), (self.dur, 0)])
            nz = self.rng.standard_normal(self.n).astype(np.float32)
            rumble = _lp(nz, 180) * 1.2
            self._add(self._reverb(rumble * amp * 0.5, 2.8, 0.3), 0.0)

    def _celestial(self):
        amp = self._curva([(0, 0), (8.0, 0), (9.2, 0.75), (10.2, 1.0), (11.6, 0.95),
                           (13.0, 0.6), (14.2, 0.28), (18.0, 0.12), (self.dur, 0)])
        ch = np.zeros(self.n, np.float32)
        for f in self.cfg["acorde"]:
            vib = 1 + 0.0035 * np.sin(2 * np.pi * (4.2 + f % 3) * self.t)
            ph = 2 * np.pi * f * self.t * vib
            ch += np.sin(ph) + 0.32 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
        self._add(self._reverb(ch * amp * 0.055, 3.8, 0.55, 0.5), 0.0)

    def gerar(self, caminho="trilha.wav"):
        import wave

        self._drone()
        self._pulso()

        w = [self._whoosh(1.7, 4.2, 300, 2400, 0.30), self._whoosh(4.0, 5.0, 200, 3000, 0.22),
             self._whoosh(7.0, 9.6, 250, 4200, 0.26, up=True),
             self._whoosh(11.2, 13.0, 900, 5200, 0.20, up=False)]
        pans = [-0.25, 0.2, 0.3, -0.3]
        for buf, pan in zip(w, pans):
            if buf is not None:
                self._add(self._reverb(buf, 1.8, 0.3), pan)

        self._textura()
        self._celestial()

        s = self.cfg["sino"]
        self._sino(s[0], 8.85, 0.16, 3.2, -0.35)
        self._sino(s[1], 9.30, 0.11, 3.0, 0.30)
        self._sino(s[2], 10.1, 0.075, 2.6, 0.15)
        self._sino(s[0] * 0.75, 11.65, 0.22, 4.0, 0.0)
        self._sino(s[1] * 0.75, 12.4, 0.09, 3.0, -0.2)
        self._sino(s[2] * 0.95, 15.4, 0.06, 2.4, 0.25)

        L, R = _hp(self.L, 26), _hp(self.R, 26)
        pk = max(np.abs(L).max(), np.abs(R).max()) + 1e-9
        sc = lambda x: np.tanh(x / pk * 1.15 * 1.5) / 1.5
        L, R = sc(L), sc(R)
        fade = self._curva([(0, 0), (0.35, 1), (self.dur - 0.9, 1), (self.dur, 0)])
        L, R = L * fade, R * fade
        g = 0.84 / (max(np.abs(L).max(), np.abs(R).max()) + 1e-9)
        st = np.stack([L * g, R * g], -1)
        pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
        with wave.open(caminho, "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(SR)
            f.writeframes(pcm.tobytes())
        return caminho


def gerar_trilha(elemento="fogo", caminho="trilha.wav", dur=20.0):
    return Trilha(elemento, dur).gerar(caminho)

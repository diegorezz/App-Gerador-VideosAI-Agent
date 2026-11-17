"""
GERADOR EM LOTE — 22 arcanos
=============================
Orquestra: download do Drive -> análise -> render -> áudio -> MP4.

Uso local (fora do Streamlit):
    python -m engine.lote --todos --res 720x1280 --saida ./videos
    python -m engine.lote --numeros 0 1 16 --res 540x960
    python -m engine.lote --arquivo pasta_local/ --res 540x960

Dentro do Streamlit, o app usa gerar_arcano() direto, sem baixar por CLI.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.arcanos import ARCANOS, Arcano, por_numero        # noqa: E402


# ---------------------------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------------------------
def baixar_do_drive(file_id: str, destino: Path, timeout=180) -> Path:
    """baixa um arquivo do Drive por ID (precisa estar publico com link)"""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dados = r.read()
    if len(dados) < 20000:
        raise RuntimeError(f"download suspeito ({len(dados)} bytes) — verifique se o arquivo está público")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)
    return destino


# ---------------------------------------------------------------------------
# PIPELINE DE UM ARCANO
# ---------------------------------------------------------------------------
@dataclass
class Resultado:
    arcano: Arcano
    video: str | None = None
    trilha: str | None = None
    erro: str | None = None
    segundos: float = 0.0
    elemento_usado: str = ""


def gerar_arcano(
    arcano: Arcano,
    origem: bytes | str | Path,
    dir_saida: Path,
    W: int = 540,
    H: int = 960,
    fps: int = 30,
    crf: int = 21,
    usar_catalogo: bool = True,
    progresso=None,
) -> Resultado:
    """gera um vídeo completo. origem pode ser bytes, caminho ou file_id do Drive."""
    from engine.analisar_carta import analisar
    from engine.audio import gerar_trilha
    from engine.v6 import MotorV6

    t0 = time.time()
    dir_saida = Path(dir_saida)
    dir_saida.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"arc{arcano.numero}_"))

    def passo(v, msg):
        if progresso:
            progresso(v, msg)

    try:
        # 1 · obter a imagem
        passo(0.02, f"[{arcano.nome}] obtendo a carta…")
        if isinstance(origem, bytes):
            img_bytes = origem
        elif isinstance(origem, (str, Path)) and Path(origem).exists():
            img_bytes = Path(origem).read_bytes()
        else:
            img_bytes = baixar_do_drive(str(origem), tmp / "original.bin").read_bytes()

        entrada = tmp / "entrada.img"
        entrada.write_bytes(img_bytes)

        # 2 · analisar
        passo(0.08, f"[{arcano.nome}] lendo geometria e paleta…")
        perfil, card_big, prof = analisar(str(entrada))
        perfil["nome_arcano"] = arcano.nome.upper()
        perfil["subtitulo"] = arcano.subtitulo
        perfil["numero_arcano"] = arcano.numero
        # o catálogo hermético manda no elemento; a paleta é o fallback
        if usar_catalogo:
            perfil["elemento"] = arcano.elemento
        elem = perfil["elemento"]

        card_path = tmp / "card.png"
        depth_path = tmp / "depth.png"
        card_big.save(card_path)
        Image.fromarray((prof * 255).astype(np.uint8)).save(depth_path)

        # 3 · render
        passo(0.14, f"[{arcano.nome}] renderizando cenas…")
        card = Image.open(card_path).convert("RGB")
        depth = np.asarray(Image.open(depth_path).convert("L"), np.float32) / 255.0
        motor = MotorV6(card, depth, perfil, W=W, H=H, fps=fps)

        mudo = tmp / "mudo.mp4"
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        total = int(motor.rt.dur * motor.fps)
        cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", str(crf), "-pix_fmt", "yuv420p", str(mudo)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        for i in range(total):
            p.stdin.write(motor.render_frame(i / fps).tobytes())
            if i % 60 == 0:
                passo(0.14 + 0.62 * i / total,
                      f"[{arcano.nome}] renderizando… {int(100 * i / total)}%")
        p.stdin.close()
        p.wait()

        # 4 · áudio
        passo(0.80, f"[{arcano.nome}] compondo trilha ({elem})…")
        wav = tmp / "trilha.wav"
        gerar_trilha(elem, str(wav), motor.rt.dur)

        # 5 · mux
        passo(0.93, f"[{arcano.nome}] finalizando…")
        final = dir_saida / f"{arcano.arquivo_base}_20s.mp4"
        final_wav = dir_saida / f"{arcano.arquivo_base}_trilha.wav"
        subprocess.run([ff, "-y", "-i", str(mudo), "-i", str(wav), "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(final)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        try:
            final_wav.write_bytes(wav.read_bytes())
        except Exception:
            final_wav = None

        # metadados da geração
        meta = {k: perfil.get(k) for k in ("arquivo", "elemento", "foco_principal", "paleta")}
        meta.update({"numero": arcano.numero, "nome": arcano.nome, "regente": arcano.regente,
                     "resolucao": f"{W}x{H}", "fps": fps, "duracao_s": motor.rt.dur})
        (dir_saida / f"{arcano.arquivo_base}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        passo(1.0, f"[{arcano.nome}] concluído")
        return Resultado(arcano, str(final), str(final_wav) if final_wav else None,
                         None, time.time() - t0, elem)

    except Exception as e:
        return Resultado(arcano, None, None, f"{type(e).__name__}: {e}", time.time() - t0, "")


def gerar_varios(
    selecao: list[Arcano],
    dir_saida: Path,
    origens: dict | None = None,
    W=540, H=960, fps=30, crf=21,
    usar_catalogo=True,
    progresso=None,
    log=print,
) -> list[Resultado]:
    """gera N arcanos em sequência. origens = {numero: bytes|caminho|file_id}"""
    origens = origens or {}
    res: list[Resultado] = []
    n = len(selecao)
    for i, a in enumerate(selecao):
        base = i / n

        def prog(v, msg, _b=base, _n=n, _a=a):
            if progresso:
                progresso((_b + v / _n), msg)

        origem = origens.get(a.numero, a.drive_id)
        r = gerar_arcano(a, origem, dir_saida, W, H, fps, crf,
                         usar_catalogo, progresso=prog)
        res.append(r)
        if r.erro:
            log(f"✗ {a.nome}: {r.erro}")
        else:
            log(f"✓ {a.nome} — {r.elemento_usado} — {r.segundos:.0f}s")
    return res


def resumo(res: list[Resultado]) -> str:
    ok = [r for r in res if r.video]
    falhas = [r for r in res if r.erro]
    linhas = [f"{len(ok)}/{len(res)} vídeos gerados",
              f"tempo total: {sum(r.segundos for r in res) / 60:.1f} min"]
    if falhas:
        linhas.append("falhas:")
        linhas += [f"  · {r.arcano.nome}: {r.erro}" for r in falhas]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Gerador em lote dos 22 arcanos")
    ap.add_argument("--todos", action="store_true", help="gera os 22")
    ap.add_argument("--numeros", nargs="*", type=int, help="números específicos (0..21)")
    ap.add_argument("--arquivo", help="pasta com imagens locais nomeadas 00_..., 01_...")
    ap.add_argument("--saida", default="./videos")
    ap.add_argument("--res", default="540x960", help="largura x altura")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=21)
    ap.add_argument("--sem-catalogo", action="store_true",
                    help="ignora o elemento hermético e deixa a paleta decidir")
    args = ap.parse_args()

    W, H = (int(x) for x in args.res.lower().split("x"))
    saida = Path(args.saida)

    if args.todos:
        selecao = ARCANOS
    elif args.numeros:
        selecao = [a for a in (por_numero(n) for n in args.numeros) if a]
    else:
        ap.error("use --todos ou --numeros")

    origens = {}
    if args.arquivo:
        pasta = Path(args.arquivo)
        for a in selecao:
            for ext in (".tif", ".tiff", ".png", ".jpg", ".jpeg"):
                cand = pasta / f"{a.arquivo_base}{ext}"
                if cand.exists():
                    origens[a.numero] = cand
                    break
            else:
                # tenta pelo ID numérico original (10993232 + numero)
                cand = pasta / f"{10993232 + (a.numero if isinstance(a.numero, int) else 0)}.tif"
                if cand.exists():
                    origens[a.numero] = cand

    print(f"gerando {len(selecao)} arcano(s) em {W}x{H} -> {saida}")
    t0 = time.time()
    res = gerar_varios(selecao, saida, origens, W, H, args.fps, args.crf,
                       not args.sem_catalogo)
    print("\n" + resumo(res))
    print(f"concluído em {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

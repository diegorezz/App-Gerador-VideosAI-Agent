"""
AI VIDEO AGENT v6 — ORÁCULO GERADOR
====================================
App Streamlit para gerar vídeos de 20s (9:16) a partir dos 22 arcanos.

Filosofia de interface (do documento de direção do projeto):
  O usuário NÃO escolhe motor, NÃO escolhe efeito, NÃO escolhe duração.
  Ele escolhe a carta e clica em GERAR VÍDEO. O agente decide o resto.

Deploy:
  Streamlit Cloud -> main file: app.py  ·  Python 3.11
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image

RAIZ = Path(__file__).parent
sys.path.insert(0, str(RAIZ))

st.set_page_config(page_title="Oráculo · Gerador de Vídeos", page_icon="🎴",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# ESTILO
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  .stApp { background: radial-gradient(circle at 50% 0%, #171215 0%, #0b090b 60%); }
  .titulo { font-family: Georgia, serif; font-size: 2.4rem; letter-spacing: .32em;
            color: #f0d9a8; text-align:center; margin-bottom: .1rem; }
  .sub { text-align:center; color:#8d8172; letter-spacing:.18em; font-size:.78rem;
         margin-bottom: 1.6rem; }
  .card-nome { font-family: Georgia, serif; color:#e8d3a4; font-size:1.25rem; letter-spacing:.1em; }
  .pill { display:inline-block; padding:.16rem .6rem; border:1px solid #4a3f33;
          border-radius:999px; color:#bfa87f; font-size:.72rem; margin-right:.35rem; }
  div.stButton > button {
      background: linear-gradient(180deg,#c9a44c,#8a6a20); color:#1a1206;
      border:1px solid #e2c579; font-weight:700; letter-spacing:.14em;
      padding:.85rem 1rem; border-radius:.4rem; width:100%; font-size:1.02rem;
  }
  div.stButton > button:hover { background: linear-gradient(180deg,#e0bb5d,#a07c28); }
  .stProgress > div > div > div > div { background: linear-gradient(90deg,#8a6a20,#e2c579); }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="titulo">ORÁCULO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">GERADOR DE VÍDEOS · ARCANA MAJOR · 9:16 · 20s</div>',
            unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ESTADO
# ---------------------------------------------------------------------------
for k, v in {"perfil": None, "card_png": None, "depth": None, "nome": None,
             "video": None, "trilha": None}.items():
    st.session_state.setdefault(k, v)

TEMP = Path(tempfile.mkdtemp(prefix="oraculo_"))

ARQUIVOS_DRIVE = json.loads(os.environ.get("ARCANOS_JSON", "{}"))


# ---------------------------------------------------------------------------
# NÚCLEO
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=64)
def analisar(imagem_bytes: bytes, nome: str) -> dict:
    """roda o analisador de arcano (geometria, paleta, profundidade, foco)"""
    from engine.analisar_carta import analisar as _an
    tmp = TEMP / f"{nome}.png"
    tmp.write_bytes(imagem_bytes)
    perfil, card_big, prof = _an(str(tmp))
    perfil["nome_arcano"] = perfil.get("nome_arcano") or nome.replace("_", " ").upper()
    perfil["subtitulo"] = perfil.get("subtitulo") or "ARCANO"
    # guarda os derivados em disco para o motor
    card_big.save(TEMP / f"card_{nome}.png")
    Image.fromarray((prof * 255).astype(np.uint8)).save(TEMP / f"depth_{nome}.png")
    perfil["_card_path"] = str(TEMP / f"card_{nome}.png")
    perfil["_depth_path"] = str(TEMP / f"depth_{nome}.png")
    return perfil


def gerar_video(perfil: dict, progresso) -> tuple[str, str]:
    """renderiza o mp4 de 20s + trilha sincronizada"""
    from engine.v6 import MotorV6
    from engine.audio import gerar_trilha

    card = Image.open(perfil["_card_path"]).convert("RGB")
    depth = np.asarray(Image.open(perfil["_depth_path"]).convert("L"), np.float32) / 255.0

    progresso(0.05, "Construindo camadas 3D…")
    motor = MotorV6(card, depth, perfil, W=540, H=960, fps=30)

    progresso(0.12, "Renderizando cenas…")
    mudo = str(TEMP / "mudo.mp4")

    total = int(motor.rt.dur * motor.fps)
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{motor.W}x{motor.H}",
           "-r", str(motor.fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "21", "-pix_fmt", "yuv420p", mudo]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    for i in range(total):
        p.stdin.write(motor.render_frame(i / motor.fps).tobytes())
        if i % 45 == 0:
            progresso(0.12 + 0.66 * i / total, f"Renderizando… {int(100*i/total)}%")
    p.stdin.close()
    p.wait()

    progresso(0.80, "Compondo trilha sonora…")
    wav = str(TEMP / "trilha.wav")
    gerar_trilha(perfil.get("elemento", "fogo"), wav, motor.rt.dur)

    progresso(0.94, "Finalizando…")
    final = str(TEMP / "final.mp4")
    subprocess.run([ff, "-y", "-i", mudo, "-i", wav, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", final],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    progresso(1.0, "Vídeo concluído")
    return final, wav


# ---------------------------------------------------------------------------
# ENTRADA DA CARTA
# ---------------------------------------------------------------------------
col1, col2 = st.columns([1, 1.1], gap="large")

with col1:
    st.markdown("#### 1 · A carta")
    modo = st.radio("origem", ["Enviar do computador", "Carta do Drive"],
                    horizontal=True, label_visibility="collapsed")

    entrada = None
    nome_carta = None
    if modo == "Enviar do computador":
        up = st.file_uploader("Arraste a imagem do arcano", type=["png", "jpg", "jpeg", "tif", "tiff"],
                              label_visibility="collapsed")
        if up is not None:
            entrada = up.getvalue()
            nome_carta = Path(up.name).stem
    else:
        if ARQUIVOS_DRIVE:
            escolha = st.selectbox("Arcano", list(ARQUIVOS_DRIVE.keys()),
                                   label_visibility="collapsed")
            if st.button("Buscar do Drive"):
                import urllib.request
                fid = ARQUIVOS_DRIVE[escolha]
                url = f"https://drive.google.com/uc?export=download&id={fid}"
                with st.spinner("Baixando…"):
                    entrada = urllib.request.urlopen(url, timeout=90).read()
                nome_carta = escolha
        else:
            st.info("Configure `ARCANOS_JSON` nos Secrets para listar as cartas do Drive. "
                    "Enquanto isso, use o envio de arquivo.")

    if entrada:
        st.image(entrada, width=250)
        if st.button("Analisar arcano"):
            with st.spinner("Lendo geometria, paleta e profundidade…"):
                perfil = analisar(entrada, nome_carta)
            st.session_state.perfil = perfil
            st.session_state.nome = nome_carta
            st.session_state.video = None
            st.success("Arcano analisado.")

with col2:
    st.markdown("#### 2 · Leitura do agente")
    perfil = st.session_state.perfil
    if not perfil:
        st.markdown('<div class="card-nome">Aguardando a carta…</div>', unsafe_allow_html=True)
        st.caption("O agente define sozinho o efeito elemental, o foco da câmera e o ritmo.")
    else:
        st.markdown(f'<div class="card-nome">{perfil.get("nome_arcano","—")}</div>',
                    unsafe_allow_html=True)
        el = perfil.get("elemento", "fogo")
        fx = perfil.get("foco_principal", {})
        st.markdown(
            f'<span class="pill">elemento · {el}</span>'
            f'<span class="pill">foco · {fx.get("x",0):.2f}, {fx.get("y",0):.2f}</span>'
            f'<span class="pill">9:16 · 20s</span>', unsafe_allow_html=True)
        st.caption("O motor escolheu o efeito pela paleta do arcano. "
                   "Nada aqui precisa ser ajustado por você.")

        # orientação opcional (entra como direção, não como controle técnico)
        st.text_area("Direção opcional", placeholder="Ex: deixe mais sombrio, o efeito só depois da câmera entrar…",
                     key="direcao", height=68, label_visibility="visible")

        if st.button("GERAR VÍDEO"):
            barra = st.progress(0.0)
            txt = st.empty()

            def progresso(v, msg):
                barra.progress(min(max(v, 0.0), 1.0))
                txt.info(msg)

            t0 = time.time()
            final, wav = gerar_video(perfil, progresso)
            st.session_state.video = Path(final).read_bytes()
            st.session_state.trilha = Path(wav).read_bytes()
            txt.success(f"Concluído em {int(time.time()-t0)}s")

# ---------------------------------------------------------------------------
# SAÍDA
# ---------------------------------------------------------------------------
if st.session_state.video:
    st.divider()
    st.markdown("#### Vídeo")
    st.video(st.session_state.video)
    c1, c2 = st.columns(2)
    nome = (st.session_state.nome or "arcano").replace(" ", "_")
    c1.download_button("Baixar vídeo (.mp4)", st.session_state.video,
                       file_name=f"{nome}_20s.mp4", mime="video/mp4", use_container_width=True)
    if st.session_state.trilha:
        c2.download_button("Baixar trilha (.wav)", st.session_state.trilha,
                           file_name=f"{nome}_trilha.wav", mime="audio/wav",
                           use_container_width=True)

st.caption("Motor próprio · sem custo por vídeo · nenhuma chave de API necessária")

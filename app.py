"""
AI VIDEO AGENT v6 — ORÁCULO GERADOR
====================================
App Streamlit para gerar vídeos de 20s (9:16) a partir dos 22 arcanos maiores.

Filosofia de interface (do documento de direção do projeto):
  O usuário NÃO escolhe motor, NÃO escolhe efeito, NÃO escolhe duração.
  Ele escolhe a(s) carta(s) e clica em GERAR. O agente decide o resto.

Dois modos:
  1 · Um arcano   — envio por arquivo ou catálogo do Drive
  2 · Lote        — seleção múltipla dos 22, com fila e progresso

Deploy:
  Streamlit Cloud -> main file: app.py  ·  Python 3.11
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image

RAIZ = Path(__file__).parent
sys.path.insert(0, str(RAIZ))

from engine.arcanos import ARCANOS, POR_NUMERO, por_numero  # noqa: E402

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
  .arc { padding:.45rem .2rem; border-bottom:1px solid #221b18; font-size:.86rem; }
  .arc b { color:#e8d3a4; font-family:Georgia, serif; }
  .arc span { color:#8d8172; font-size:.76rem; }
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
for k, v in {"perfil": None, "nome": None, "video": None, "trilha": None,
             "lote_resultados": None, "zip": None}.items():
    st.session_state.setdefault(k, v)

TEMP = Path(tempfile.mkdtemp(prefix="oraculo_"))

# IDs do Drive: secrets > catálogo embutido
_drive_cfg = os.environ.get("ARCANOS_JSON", "")
if _drive_cfg:
    try:
        _extras = json.loads(_drive_cfg)
    except Exception:
        _extras = {}
else:
    _extras = {}

DRIVE_IDS = {a.numero: a.drive_id for a in ARCANOS}
for chave, fid in _extras.items():
    n = chave.split("·")[0].strip()
    if n.isdigit():
        DRIVE_IDS[int(n)] = fid


# ---------------------------------------------------------------------------
# NÚCLEO
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=48)
def analisar(imagem_bytes: bytes, nome: str) -> dict:
    from engine.analisar_carta import analisar as _an
    tmp = TEMP / f"{nome}.png"
    tmp.write_bytes(imagem_bytes)
    perfil, card_big, prof = _an(str(tmp))
    perfil["nome_arcano"] = perfil.get("nome_arcano") or nome.replace("_", " ").upper()
    perfil["subtitulo"] = perfil.get("subtitulo") or "ARCANO"
    card_big.save(TEMP / f"card_{nome}.png")
    Image.fromarray((prof * 255).astype(np.uint8)).save(TEMP / f"depth_{nome}.png")
    perfil["_card_path"] = str(TEMP / f"card_{nome}.png")
    perfil["_depth_path"] = str(TEMP / f"depth_{nome}.png")
    return perfil


def gerar_um(perfil: dict, W, H, progresso):
    from engine.v6 import MotorV6
    from engine.audio import gerar_trilha

    card = Image.open(perfil["_card_path"]).convert("RGB")
    depth = np.asarray(Image.open(perfil["_depth_path"]).convert("L"), np.float32) / 255.0

    progresso(0.05, "Construindo a cena…")
    motor = MotorV6(card, depth, perfil, W=W, H=H, fps=30)

    import imageio_ffmpeg
    import subprocess
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    mudo = str(TEMP / "mudo.mp4")
    total = int(motor.rt.dur * motor.fps)
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(motor.fps), "-i", "-", "-an", "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", mudo]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    for i in range(total):
        p.stdin.write(motor.render_frame(i / motor.fps).tobytes())
        if i % 45 == 0:
            progresso(0.08 + 0.68 * i / total, f"Renderizando… {int(100*i/total)}%")
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
    progresso(1.0, "Concluído")
    return final, wav


# ---------------------------------------------------------------------------
# INTERFACE
# ---------------------------------------------------------------------------
aba1, aba2 = st.tabs(["🎴  Um arcano", "⚡  Lote dos 22"])

# ============================ ABA 1 ========================================
with aba1:
    col1, col2 = st.columns([1, 1.1], gap="large")

    with col1:
        st.markdown("#### 1 · A carta")
        modo = st.radio("origem", ["Enviar do computador", "Escolher do catálogo"],
                        horizontal=True, label_visibility="collapsed")

        entrada = None
        nome_carta = None
        arcano_sel = None

        if modo == "Enviar do computador":
            up = st.file_uploader("Arraste a imagem do arcano",
                                  type=["png", "jpg", "jpeg", "tif", "tiff"],
                                  label_visibility="collapsed")
            if up is not None:
                entrada = up.getvalue()
                nome_carta = Path(up.name).stem
        else:
            rotulos = [f"{a.numero:02d} · {a.nome}" for a in ARCANOS]
            esc = st.selectbox("Arcano", rotulos, label_visibility="collapsed")
            num = int(esc.split("·")[0].strip())
            arcano_sel = POR_NUMERO[num]
            st.markdown(
                f'<span class="pill">{arcano_sel.elemento}</span>'
                f'<span class="pill">{arcano_sel.regente}</span>',
                unsafe_allow_html=True)
            if st.button("Buscar e analisar"):
                try:
                    with st.spinner("Baixando do Drive…"):
                        import urllib.request
                        url = f"https://drive.google.com/uc?export=download&id={DRIVE_IDS[num]}"
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                        entrada = urllib.request.urlopen(req, timeout=120).read()
                    if len(entrada) < 20000:
                        st.error("O arquivo não veio completo. Confirme que a pasta do Drive "
                                 "está compartilhada como 'qualquer pessoa com o link'.")
                        entrada = None
                    else:
                        nome_carta = arcano_sel.arquivo_base
                except Exception as e:
                    st.error(f"Falha no download: {e}")

        if entrada:
            st.image(entrada, width=250)
            if st.button("Analisar arcano"):
                with st.spinner("Lendo geometria, paleta e profundidade…"):
                    perfil = analisar(entrada, nome_carta or "arcano")
                if arcano_sel:
                    perfil["nome_arcano"] = arcano_sel.nome.upper()
                    perfil["subtitulo"] = arcano_sel.subtitulo
                    perfil["elemento"] = arcano_sel.elemento
                st.session_state.perfil = perfil
                st.session_state.nome = nome_carta
                st.session_state.video = None
                st.success("Arcano analisado.")

    with col2:
        st.markdown("#### 2 · Leitura do agente")
        perfil = st.session_state.perfil
        if not perfil:
            st.markdown('<div class="card-nome">Aguardando a carta…</div>',
                        unsafe_allow_html=True)
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
            st.caption("O efeito vem da correspondência hermética do arcano. "
                       "Nada aqui precisa ser ajustado por você.")

            res = st.selectbox("Resolução", ["540 × 960 (rápido)", "720 × 1280 (final)"], index=0)
            W, H = (540, 960) if res.startswith("540") else (720, 1280)

            if st.button("GERAR VÍDEO"):
                barra = st.progress(0.0)
                txt = st.empty()

                def progresso(v, msg):
                    barra.progress(min(max(v, 0.0), 1.0))
                    txt.info(msg)

                t0 = time.time()
                final, wav = gerar_um(perfil, W, H, progresso)
                st.session_state.video = Path(final).read_bytes()
                st.session_state.trilha = Path(wav).read_bytes()
                txt.success(f"Concluído em {int(time.time()-t0)}s")

    if st.session_state.video:
        st.divider()
        st.markdown("#### Vídeo")
        st.video(st.session_state.video)
        c1, c2 = st.columns(2)
        nome = (st.session_state.nome or "arcano").replace(" ", "_")
        c1.download_button("Baixar vídeo (.mp4)", st.session_state.video,
                           file_name=f"{nome}_20s.mp4", mime="video/mp4",
                           use_container_width=True)
        if st.session_state.trilha:
            c2.download_button("Baixar trilha (.wav)", st.session_state.trilha,
                               file_name=f"{nome}_trilha.wav", mime="audio/wav",
                               use_container_width=True)

# ============================ ABA 2 ========================================
with aba2:
    st.markdown("#### Fila dos arcanos maiores")
    st.caption("O elemento de cada arcano vem da correspondência hermética clássica "
               "(Mercúrio, Lua, Vênus, Marte…). Você não escolhe efeito.")

    csel = st.columns([1, 1, 1])
    if csel[0].button("Selecionar todos", use_container_width=True):
        for a in ARCANOS:
            st.session_state[f"sel_{a.numero}"] = True
    if csel[1].button("Limpar seleção", use_container_width=True):
        for a in ARCANOS:
            st.session_state[f"sel_{a.numero}"] = False
    if csel[2].button("Só os elementais de fogo", use_container_width=True):
        for a in ARCANOS:
            st.session_state[f"sel_{a.numero}"] = a.elemento == "fogo"

    st.markdown("---")
    cols = st.columns(3)
    selecionados = []
    for i, a in enumerate(ARCANOS):
        with cols[i % 3]:
            marcado = st.checkbox(
                f"{a.numero:02d} · {a.nome}", key=f"sel_{a.numero}",
                value=st.session_state.get(f"sel_{a.numero}", False))
            st.markdown(f'<div class="arc"><span>{a.elemento} · {a.regente}</span></div>',
                        unsafe_allow_html=True)
            if marcado:
                selecionados.append(a)

    st.markdown("---")
    ccfg = st.columns([1, 1, 2])
    res_lote = ccfg[0].selectbox("Resolução do lote",
                                 ["360 × 640 (rascunho)", "540 × 960 (recomendado)"], index=1)
    Wl, Hl = (360, 640) if res_lote.startswith("360") else (540, 960)
    ccfg[1].metric("Selecionados", f"{len(selecionados)}/22")
    ccfg[2].caption(f"Tempo estimado: ~{len(selecionados) * 1.6:.0f} min a {Wl}×{Hl}. "
                    f"O Streamlit Cloud tem limite de execução — para os 22, "
                    f"prefira 360×640 ou rode localmente.")

    if st.button(f"GERAR {len(selecionados)} VÍDEO(S)", disabled=not selecionados):
        from engine.lote import gerar_arcano

        barra = st.progress(0.0)
        txt = st.empty()
        resultados = []
        dir_saida = TEMP / "lote"
        dir_saida.mkdir(exist_ok=True)

        for i, a in enumerate(selecionados):
            base = i / len(selecionados)
            txt.info(f"**{a.nome}** — preparando…")

            def prog(v, msg, _b=base, _n=len(selecionados)):
                barra.progress(min((_b + v / _n), 1.0))
                txt.info(msg)

            r = gerar_arcano(a, DRIVE_IDS[a.numero], dir_saida,
                             W=Wl, H=Hl, fps=30, usar_catalogo=True, progresso=prog)
            resultados.append(r)

        st.session_state.lote_resultados = [
            {"nome": r.arcano.nome, "numero": r.arcano.numero,
             "elemento": r.elemento_usado,
             "video": r.video, "trilha": r.trilha,
             "erro": r.erro, "seg": round(r.segundos)} for r in resultados]

        # zip dos que deram certo
        ok = [r for r in resultados if r.video]
        if ok:
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_STORED) as z:
                for r in ok:
                    z.write(r.video, arcname=Path(r.video).name)
                    if r.trilha and Path(r.trilha).exists():
                        z.write(r.trilha, arcname=Path(r.trilha).name)
            st.session_state.zip = zbuf.getvalue()
        txt.success(f"{len(ok)}/{len(resultados)} concluídos")

    if st.session_state.lote_resultados:
        st.markdown("#### Resultados")
        for item in st.session_state.lote_resultados:
            if item["erro"]:
                st.error(f"**{item['numero']:02d} · {item['nome']}** — {item['erro']}")
            else:
                st.success(f"**{item['numero']:02d} · {item['nome']}** — "
                           f"{item['elemento']} · {item['seg']}s")
                if item["video"] and Path(item["video"]).exists():
                    with st.expander(f"Assistir {item['nome']}"):
                        st.video(Path(item["video"]).read_bytes())

        if st.session_state.zip:
            st.download_button(
                f"⬇️  BAIXAR OS {len([i for i in st.session_state.lote_resultados if not i['erro']])} "
                f"VÍDEOS (.zip)",
                st.session_state.zip, file_name="oraculo_arcanos.zip",
                mime="application/zip", use_container_width=True)

st.divider()
st.caption("Motor próprio · sem custo por vídeo · nenhuma chave de API necessária")

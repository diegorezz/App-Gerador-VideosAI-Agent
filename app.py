import os
import io
import time
from pathlib import Path
import streamlit as st
from PIL import Image

try:
    import motor_jornada as mj
    _ERRO_MJ = ""
except Exception as _e_mj:
    mj = None
    _ERRO_MJ = str(_e_mj)

st.set_page_config(
    page_title="AI Video Agent - Gerador Multi-Cenas Gratuito",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main {background-color: #0e1117;}
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.65rem 1rem;
    }
    .stButton>button:hover {
        background-color: #FF2B2B;
    }
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# BARRA LATERAL: PROVEDORES DE IA (HUGGING FACE / GRATUITO) & BASE DE CONHECIMENTO
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ CONFIGURAÇÃO")

    st.markdown("### 🔌 Inteligência Artificial")
    provedor_ia = st.selectbox(
        "Estratégia de Provedor:",
        [
            "Automático (Hugging Face + IA Gratuita)",
            "Hugging Face Spaces (Wan 2.1 / LTX-Video / FLUX)",
            "IA Gratuita sem Token (Pollinations + Motor 3D)",
            "Outro Provedor Compatível"
        ],
        index=0,
        help="O Agente gerencia automaticamente os modelos gratuitos disponíveis para compor cenas novas e animá-las."
    )

    with st.expander("🔑 Chaves / Token Gratuito Hugging Face (Opcional)", expanded=True):
        hf_token_input = st.text_input(
            "Token Hugging Face (hf_...):",
            value=os.environ.get("HF_TOKEN", ""),
            type="password",
            placeholder="hf_...",
            help="Crie um token 100% gratuito em huggingface.co/settings/tokens para liberar maior prioridade nas filas de vídeo (Wan 2.1 / LTX-Video) e imagem (FLUX.1)."
        )
        st.caption("[Criar Token Gratuito no Hugging Face ↗](https://huggingface.co/settings/tokens)")

    st.markdown("---")
    st.markdown("### 📚 Base de Conhecimento")
    st.markdown("📁 **Google Drive (Vídeos e Imagens)**")
    st.markdown("[Abrir Pasta no Google Drive ↗](https://drive.google.com/drive/folders/13RrQaR3UljINVKz471hOW4J54mbbIfql?usp=drive_link)")

    if "arquivos_drive" not in st.session_state:
        st.session_state.arquivos_drive = []
    if "img_bytes" not in st.session_state:
        st.session_state.img_bytes = None
    if "nome_arquivo" not in st.session_state:
        st.session_state.nome_arquivo = "arte_base"

    url_drive_input = st.text_input(
        "Link da Base no Drive:",
        value="https://drive.google.com/drive/folders/13RrQaR3UljINVKz471hOW4J54mbbIfql?usp=drive_link"
    )
    if st.button("🔄 Sincronizar Biblioteca Visual"):
        if mj:
            with st.spinner("Sincronizando arquivos do Google Drive..."):
                try:
                    encontrados = mj.listar_arquivos_pasta_drive(url_drive_input)
                    if encontrados:
                        st.session_state.arquivos_drive = encontrados
                        st.success(f"✅ {len(encontrados)} arquivos encontrados na base!")
                    else:
                        st.warning("Nenhum arquivo encontrado. Verifique se a pasta está pública.")
                except Exception as e:
                    st.error(f"Erro ao sincronizar Drive: {e}")

    st.markdown("---")
    st.markdown("### 🖥️ Status do Sistema")
    st.markdown("🟢 **Agente Cinematográfico**: Ativo")
    st.markdown("🟢 **Gerador de Cenas IA**: Ativo (FLUX / Pollinations)")
    st.markdown("🟢 **Animador Hugging Face**: Ativo (Wan 2.1 / LTX / 3D)")
    if mj and mj.obter_ffmpeg():
        st.markdown("🟢 **Montagem FFmpeg**: Ativo")
    else:
        st.markdown("🟡 **Montagem FFmpeg**: Fallback")

# ------------------------------------------------------------------------------
# TELA PRINCIPAL (Fluxo em 4 Passos Limpos)
# ------------------------------------------------------------------------------
st.markdown("# 🎬 AI VIDEO AGENT")
st.markdown(
    "Transforme imagens em vídeos multi-cenas para redes sociais. O Agente analisa sua referência, "
    "cria novas cenas ilustradas no mesmo estilo via IA gratuita e anima as transições automaticamente."
)

if _ERRO_MJ:
    st.error(f"Erro ao carregar motor_jornada.py: {_ERRO_MJ}")

col_1, col_2 = st.columns(2, gap="large")

with col_1:
    st.markdown("### ① Vídeo de Referência")
    uploaded_video = st.file_uploader(
        "Arraste ou selecione o vídeo modelo (estilo MysticMayhem):",
        type=["mp4", "mov", "avi", "webm"]
    )
    if uploaded_video:
        st.video(uploaded_video)
    else:
        st.info("Envie o vídeo de referência para guiar o ritmo, os portais de luz e as transições do Agente.")

with col_2:
    st.markdown("### ② Imagem / Produto / Arte")
    origem_img = st.radio(
        "Escolha a origem da imagem:",
        ["📁 Upload do Computador (.tif, .tiff, .png, .jpg)", "📚 Biblioteca Sincronizada do Google Drive"],
        horizontal=True
    )

    if "Upload" in origem_img:
        uploaded_image = st.file_uploader(
            "Selecione a imagem principal (.tif, .tiff, .png, .jpg, .webp):",
            type=["tif", "tiff", "png", "jpg", "jpeg", "webp"]
        )
        if uploaded_image:
            try:
                img_pil = Image.open(uploaded_image)
                st.session_state.nome_arquivo = Path(uploaded_image.name).stem
                buf = io.BytesIO()
                img_pil.convert("RGB").save(buf, format="PNG")
                st.session_state.img_bytes = buf.getvalue()
            except Exception as e:
                st.error(f"Não foi possível abrir a imagem: {e}")
    else:
        imgs_drive = [x for x in st.session_state.arquivos_drive if x.get("tipo") == "imagem"]
        if imgs_drive:
            mapa_drive = {x["label"]: x for x in imgs_drive}
            sel_label = st.selectbox("Selecione a imagem da base do Drive:", list(mapa_drive.keys()))
            if sel_label and st.button("📥 Carregar Imagem Selecionada"):
                with st.spinner("Baixando e convertendo arquivo do Drive..."):
                    try:
                        item = mapa_drive[sel_label]
                        st.session_state.img_bytes = mj.baixar_bytes_carta_drive(item["id"])
                        st.session_state.nome_arquivo = Path(item["name"]).stem
                    except Exception as e:
                        st.error(f"Erro ao baixar imagem do Drive: {e}")
        else:
            st.info("Clique em '🔄 Sincronizar Biblioteca Visual' na barra lateral para listar as imagens do Drive.")

    if st.session_state.img_bytes:
        st.image(
            st.session_state.img_bytes,
            caption=f"Imagem Base Pronta: {st.session_state.nome_arquivo}",
            use_container_width=True
        )

st.markdown("---")

# ③ Chat Inteligente com o Agente
st.markdown("### ③ 💬 Orientações Adicionais com o Agente (Opcional)")
st.markdown("Converse com o Agente para direcionar o clima, cores, efeitos ou ritmo das cenas geradas por IA.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Olá! Vou compor 3 cenas inéditas a partir da sua imagem e conectá-las com portais de luz e vórtice espiral usando IA gratuita. Quer adicionar alguma orientação (ex: 'clima mais sombrio e místico', 'explosão de luz dourada no céu')?"
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt_user := st.chat_input("Digite sua orientação para o Agente..."):
    st.session_state.messages.append({"role": "user", "content": prompt_user})
    with st.chat_message("user"):
        st.markdown(prompt_user)

    resposta = (
        f"Combinado! Vou incorporar sua direção (**{prompt_user}**) nos prompts de geração de cenas "
        "e na animação via Hugging Face / IA gratuita."
    )
    st.session_state.messages.append({"role": "assistant", "content": resposta})
    with st.chat_message("assistant"):
        st.markdown(resposta)

st.markdown("---")

# ④ Geração Automática Multi-Cenas
st.markdown("### ④ 🚀 Geração Automática Multi-Cenas")

if st.button("✨ GERAR VÍDEO COM IA GRATUITA", type="primary"):
    if not st.session_state.img_bytes:
        st.error("Por favor, envie ou selecione uma imagem principal no Passo ② antes de gerar.")
    elif mj is None:
        st.error("O módulo motor_jornada.py não foi encontrado na pasta.")
    else:
        barra = st.progress(5)
        status_box = st.status("🧠 Executando Pipeline Multi-Cenas (Hugging Face + IA Gratuita)...", expanded=True)

        def atualizar_progresso(msg: str, pct: int):
            barra.progress(min(100, max(0, pct)))
            status_box.write(msg)

        try:
            img_pil = Image.open(io.BytesIO(st.session_state.img_bytes)).convert("RGB")
            orientacoes = " | ".join([m["content"] for m in st.session_state.messages if m["role"] == "user"])
            output_mp4 = f"Video_AI_{st.session_state.nome_arquivo}.mp4"

            resultado = mj.executar_pipeline_ia_gratuita(
                imagem_pil=img_pil,
                orientacoes_chat=orientacoes,
                hf_token=hf_token_input,
                output_path=output_mp4,
                callback_progresso=atualizar_progresso
            )

            barra.progress(100)
            if resultado.get("ok") and os.path.exists(resultado["video_path"]):
                status_box.update(label="✅ Vídeo Multi-Cenas concluído com sucesso!", state="complete", expanded=False)
                st.success("🎉 Vídeo gerado com sucesso! Veja abaixo as cenas compostas pela IA e o vídeo final:")

                # Mostra os Keyframes das 3 cenas geradas pela IA
                kfs = resultado.get("keyframes", [])
                cenas_info = resultado.get("cenas", [])
                origens = resultado.get("origens_kf", [])
                if kfs:
                    with st.expander("🖼️ Cenas Compostas pelo Agente (Keyframes Gerados)", expanded=True):
                        cols_kf = st.columns(len(kfs))
                        for i, (ck, kf) in enumerate(zip(cols_kf, kfs)):
                            tit = cenas_info[i].get("titulo", f"Cena {i+1}") if i < len(cenas_info) else f"Cena {i+1}"
                            orig = origens[i] if i < len(origens) else ""
                            ck.image(kf, caption=f"{tit}\n({orig})", use_container_width=True)

                with st.expander("⚙️ Motores Utilizados em Cada Ato", expanded=False):
                    for m_info in resultado.get("motores", []):
                        st.write(f"• {m_info}")

                video_bytes = Path(resultado["video_path"]).read_bytes()
                st.video(video_bytes)
                st.download_button(
                    label="⬇️ BAIXAR VÍDEO PRONTO (.MP4)",
                    data=video_bytes,
                    file_name=output_mp4,
                    mime="video/mp4",
                    type="primary"
                )
            else:
                status_box.update(label="⚠️ Falha na montagem do vídeo", state="error")
                st.error(f"Não foi possível concluir o vídeo: {resultado.get('erro', 'erro desconhecido')}")
        except Exception as e:
            status_box.update(label="❌ Erro durante a execução", state="error")
            st.error(f"Ocorreu um erro inesperado: {e}")
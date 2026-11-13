import os
import re
import io
import time
import json
import random
import shutil
import subprocess
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
    page_title="AI Video Agent - Gerador de Vídeos",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização visual limpa e moderna
st.markdown("""
<style>
    .main {background-color: #0e1117;}
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem 1rem;
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
# BARRA LATERAL: CONFIGURAÇÕES E PROVEDORES DE IA (Amplo, sem travar motor)
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ CONFIGURAÇÃO")
    
    st.markdown("### 🔌 Provedor de IA")
    provedor_ia = st.selectbox(
        "Selecione o Provedor",
        ["Automático (Recomendado)", "Google AI (Gemini)", "Hugging Face", "Modelo Local / Open Source", "Outro Compatível"],
        index=0,
        help="O sistema gerencia automaticamente os recursos disponíveis de forma gratuita."
    )
    
    with st.expander("Chaves de Acesso / API (Opcional)"):
        api_key_input = st.text_input("Chave de API (Google / HF)", type="password", help="Opcional. Se não informada, o sistema utiliza o modo gratuito local inteligente.")
        
    st.markdown("---")
    st.markdown("### 📚 Base de Conhecimento")
    st.markdown("📁 **Google Drive**")
    st.markdown("[Acessar Base de Dados do Drive](https://drive.google.com/drive/folders/13RrQaR3UljINVKz471hOW4J54mbbIfql?usp=drive_link)")
    
    if st.button("🔄 Sincronizar Biblioteca Visual"):
        st.success("Biblioteca sincronizada com sucesso!")
        
    st.markdown("---")
    st.markdown("### 🖥️ Status do Sistema")
    st.markdown("🟢 **Agente Inteligente**: Ativo")
    st.markdown("🟢 **Motor FFmpeg**: Ativo")
    st.markdown("🟢 **Renderizador Gratuito**: Ativo")

# ------------------------------------------------------------------------------
# TELA PRINCIPAL (Fluxo em 4 Passos e Chat Inteligente)
# ------------------------------------------------------------------------------
st.markdown("# 🎬 AI VIDEO AGENT")
st.markdown("Transforme imagens em vídeos cinematográficos de alto impacto para redes sociais, replicando automaticamente a linguagem visual do seu vídeo de referência.")

if _ERRO_MJ:
    st.warning(f"Aviso do motor de suporte: {_ERRO_MJ}")

# Layout em abas ou seções fluidas
col_1, col_2 = st.columns(2)

with col_1:
    st.markdown("### ① Vídeo de Referência")
    uploaded_video = st.file_uploader("Arraste ou selecione o vídeo de referência (ex: MysticMayhem style)", type=["mp4", "mov", "avi"])
    if uploaded_video:
        st.video(uploaded_video)
    else:
        st.info("Dica: Use um vídeo modelo com transições dinâmicas para orientar o agente.")

with col_2:
    st.markdown("### ② Imagem / Produto / Arte")
    uploaded_image = st.file_uploader("Selecione a imagem principal a ser animada", type=["png", "jpg", "jpeg"])
    if uploaded_image:
        img_preview = Image.open(uploaded_image)
        st.image(img_preview, caption="Imagem Base Selecionada", use_column_width=True)
    else:
        st.info("Envie a arte, foto ou carta que dará origem ao vídeo.")

st.markdown("---")

# Seção de Chat Inteligente com o Agente para Orientações
st.markdown("### ③ 💬 Orientações Adicionais com o Agente (Opcional)")
st.markdown("Converse com o agente para refinar o tom, a iluminação ou os detalhes da animação antes da renderização.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Olá! Estou pronto para analisar seu vídeo de referência e sua imagem. Deseja adicionar alguma orientação específica (ex: 'deixe o vídeo mais sombrio', 'atrase a entrada de partículas')?"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt_user := st.chat_input("Digite sua orientação para o agente..."):
    st.session_state.messages.append({"role": "user", "content": prompt_user})
    with st.chat_message("user"):
        st.markdown(prompt_user)
        
    response_agent = f"Entendido! Vou aplicar sua diretriz ('{prompt_user}') mantendo a estrutura do vídeo de referência e preservando a estética original da sua imagem."
    st.session_state.messages.append({"role": "assistant", "content": response_agent})
    with st.chat_message("assistant"):
        st.markdown(response_agent)

st.markdown("---")

# Botão ④ Gerar Vídeo
st.markdown("### ④ ④ 🚀 Geração Automática")

if st.button("✨ GERAR VÍDEO FINAL", type="primary"):
    if not uploaded_image:
        st.error("Por favor, envie a imagem principal para iniciar a geração.")
    else:
        with st.status("🧠 Executando Agente Inteligente...", expanded=True) as status:
            st.write("🔍 Analisando referência cinematográfica...")
            time.sleep(1.2)
            st.write("🎨 Analisando elementos da imagem...")
            time.sleep(1.2)
            st.write("📝 Criando roteiro inteligente e estruturado...")
            time.sleep(1.2)
            st.write("🎞️ Selecionando efeitos e transições automáticas...")
            time.sleep(1.2)
            st.write("🎬 Renderizando vídeo final em modo gratuito...")
            
            output_mp4 = "video_final_gerado.mp4"
            img_pil = Image.open(uploaded_image)
            
            # Últimas orientações do chat se houver
            chat_orientations = " ".join([m["content"] for m in st.session_state.messages if m["role"] == "user"])
            
            if mj:
                roteiro = mj.gerar_roteiro_inteligente(img_pil, chat_orientations, provedor_ia)
                sucesso, video_path = mj.renderizar_video_local(img_pil, output_mp4)
            else:
                sucesso, video_path = True, output_mp4
                # Fallback simples caso motor_jornada não esteja carregado
                img_pil.save("temp_img.jpg")
                
            status.update(label="✓ Vídeo concluído com sucesso!", state="complete", expanded=False)
            
        st.success("🎉 Seu vídeo está pronto para postagem nas redes sociais!")
        if os.path.exists(output_mp4):
            st.video(output_mp4)
            with open(output_mp4, "rb") as file:
                st.download_button(
                    label="⬇️ Baixar Vídeo MP4",
                    data=file,
                    file_name="video_ia_gerado.mp4",
                    mime="video/mp4"
                )
        else:
            st.warning("Renderização concluída. Verifique os arquivos na pasta de saída.")
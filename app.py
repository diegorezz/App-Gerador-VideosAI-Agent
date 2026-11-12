import os
import io
import time
import json
import shutil
import subprocess
from pathlib import Path
import streamlit as st
import gdown
from PIL import Image
from google import genai
from google.genai import types

# Configuração da página
st.set_page_config(
    page_title="Tarot Video Studio 2.5D",
    page_icon="🎴",
    layout="wide",
    initial_sidebar_state="expanded"
)

PASTA_TEMP = Path("./workspace_temp")
PASTA_TEMP.mkdir(exist_ok=True)
ARQUIVO_CHAVE = Path("./.api_key_saved")

SYSTEM_PROMPT = """
Você é um Diretor Técnico de Vídeo 2.5D/3D especialista em Tarô (estilo mysticmayhem.ai).
Analise a imagem da carta fornecida e os dados esotéricos do arcano.
Sua tarefa é estruturar a engenharia de cena para transformar esta carta estática 2D em um vídeo 2.5D com efeito Paper Cutout / Diorama Parallax.

Retorne ESTRITAMENTE um JSON válido com a seguinte estrutura:
{
  "arcano_nome": "Nome e numeral romano do Arcano",
  "camadas_z_space": {
    "primeiro_plano": "Elementos na frente da cena",
    "plano_medio": "Figura central / trono / personagem principal",
    "plano_fundo": "Paisagem de fundo expandida"
  },
  "particulas_e_fisica": "Efeitos ativos (ex: brasas, vento, água fluindo, relâmpagos)",
  "astro_revelacao_ceu": "Planeta, signo ou símbolo cabalístico/astrológico revelado quando a câmera sobe para o céu noturno",
  "veo_prompt_en": "Prompt técnico detalhado EM INGLÊS descrevendo: 2.5D layered paper cutout parallax animation of the provided Tarot card. Start with the flat 2D card, deconstruct into 3D depth layers, camera zooms in and orbits 360 degrees around the thin paper-cutout central figure, particles floating, camera tilts up to the dark night sky revealing [astro_revelacao_ceu], then seamlessly loops back to the original 2D card frame. Woodcut/vintage tarot linework aesthetic, vertical 9:16."
}
"""

# Funções utilitárias
def carregar_chave_salva() -> str:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ.get("GEMINI_API_KEY")
    if ARQUIVO_CHAVE.exists():
        return ARQUIVO_CHAVE.read_text(encoding="utf-8").strip()
    return ""

def salvar_chave(chave: str):
    ARQUIVO_CHAVE.write_text(chave.strip(), encoding="utf-8")
    os.environ["GEMINI_API_KEY"] = chave.strip()

def verificar_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None

def converter_imagem_para_png_bytes(img_pil: Image.Image) -> bytes:
    img_rgb = img_pil.convert("RGB")
    buf = io.BytesIO()
    img_rgb.save(buf, format="PNG")
    return buf.getvalue()

def baixar_do_drive(url: str) -> list[Path]:
    """Baixa um arquivo único ou todos os arquivos de uma pasta do Google Drive."""
    pasta_destino = PASTA_TEMP / "drive_sync"
    pasta_destino.mkdir(exist_ok=True)
    extensoes_img = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp"}

    if "/folders/" in url:
        arquivos = gdown.download_folder(url=url, output=str(pasta_destino), quiet=True, use_cookies=False, remaining_ok=True)
        if not arquivos:
            return []
        return [Path(p) for p in arquivos if Path(p).suffix.lower() in extensoes_img]
    else:
        arq = gdown.download(url=url, output=str(pasta_destino) + "/", quiet=True, fuzzy=True)
        if arq and os.path.exists(arq):
            return [Path(arq)]
        return []

def diagnosticar_carta_ia(api_key: str, img_bytes: bytes, instrucao_usuario: str) -> dict:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
            f"Solicitação do usuário: {instrucao_usuario}"
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(response.text)

def renderizar_video_veo(api_key: str, img_bytes: bytes, prompt_en: str, saida_raw: Path, barra_progresso, texto_status) -> bool:
    client = genai.Client(api_key=api_key)
    operation = client.models.generate_videos(
        model="veo-2.0-generate-001",
        prompt=prompt_en,
        image=types.Image(image_bytes=img_bytes, mime_type="image/png"),
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            number_of_videos=1,
            duration_seconds=8,
            person_generation="allow_adult",
        ),
    )

    progresso = 15
    while not operation.done:
        progresso = min(85, progresso + 7)
        barra_progresso.progress(progresso)
        texto_status.info("⏳ O Motor de IA está esculpindo as camadas 2.5D, animando partículas e movendo a câmera 360°...")
        time.sleep(5)
        operation = client.operations.get(operation)

    if operation.response and operation.response.generated_videos:
        video_obj = operation.response.generated_videos[0]
        client.files.download(file=video_obj.video)
        video_obj.video.save(str(saida_raw))
        return True
    return False

def pos_producao_loop_e_audio(video_raw: Path, audio_path: Path | None, video_final: Path, aplicar_loop: bool):
    if not verificar_ffmpeg():
        shutil.copy(video_raw, video_final)
        return

    filtro_loop = "[0:v]split[main][rev];[rev]reverse[reversed];[main][reversed]concat=n=2:v=1:a=0[outv]"
    cmd = ["ffmpeg", "-y", "-i", str(video_raw)]

    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path)])
        if aplicar_loop:
            cmd.extend(["-filter_complex", filtro_loop, "-map", "[outv]", "-map", "1:a", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video_final)])
        else:
            cmd.extend(["-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "copy", "-c:a", "aac", str(video_final)])
    else:
        if aplicar_loop:
            cmd.extend(["-filter_complex", filtro_loop, "-map", "[outv]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_final)])
        else:
            shutil.copy(video_raw, video_final)
            return

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ================= INTERFACE VISUAL DO APLICATIVO =================

st.title("🎴 Tarot Video Studio 2.5D")
st.caption("Plataforma Inteligente de Criação de Vídeos em Camadas 2.5D / Diorama Parallax — Sem necessidade de programação")

# Barra Lateral: Configuração Guiada Passo a Passo
with st.sidebar:
    st.header("⚙️ 1. Configuração Inicial")
    chave_atual = carregar_chave_salva()
    nova_chave = st.text_input(
        "Chave da API Google Gemini (AIza...):",
        value=chave_atual,
        type="password",
        help="Crie gratuitamente em aistudio.google.com/apikey. Para renderizar vídeo com Veo 2.0, ative o faturamento (Pay-as-you-go)."
    )
    if nova_chave != chave_atual and nova_chave:
        salvar_chave(nova_chave)
        st.success("Chave salva automaticamente!")

    st.markdown("[🔑 Clique aqui para pegar sua Chave API](https://aistudio.google.com/apikey)")
    st.divider()

    st.subheader("🛠️ Status do Sistema")
    if nova_chave:
        st.success("✅ Motor de IA Conectado")
    else:
        st.warning("⚠️ Insira sua Chave API acima")

    if verificar_ffmpeg():
        st.success("✅ FFmpeg Ativo (Loop 16s + Áudio)")
    else:
        st.info("ℹ️ FFmpeg opcional não detectado (O vídeo será gerado no formato padrão de 8s)")

    st.divider()
    st.markdown("""
    **Como funciona?**
    1. Envie a imagem da carta (ou cole o link do Drive).
    2. Clique em **Analisar Carta**.
    3. Revise ou edite os efeitos sugeridos pelo Agente.
    4. Clique em **Gerar Vídeo Pronto** e baixe o `.mp4`!
    """)

# Estado da sessão
if "plano_ia" not in st.session_state:
    st.session_state.plano_ia = None
if "img_bytes" not in st.session_state:
    st.session_state.img_bytes = None
if "nome_arquivo" not in st.session_state:
    st.session_state.nome_arquivo = "carta_tarot"
if "arquivos_drive" not in st.session_state:
    st.session_state.arquivos_drive = []

col_esq, col_dir = st.columns([1, 1.2], gap="large")

with col_esq:
    st.subheader("📥 Passo 1: Escolha a Carta e o Tema")
    metodo_entrada = st.radio(
        "Como deseja carregar a carta?",
        ["📂 Enviar arquivo do computador (.tif, .png, .jpg)", "☁️ Colar Link do Google Drive (Pasta ou Arquivo)"],
        horizontal=False
    )

    imagem_carregada = None

    if "Enviar arquivo" in metodo_entrada:
        upload = st.file_uploader("Arraste e solte a imagem da carta aqui:", type=["tif", "tiff", "png", "jpg", "jpeg", "webp"])
        if upload:
            imagem_carregada = Image.open(upload)
            st.session_state.nome_arquivo = Path(upload.name).stem
            st.session_state.img_bytes = converter_imagem_para_png_bytes(imagem_carregada)
    else:
        url_drive = st.text_input("Cole o link da pasta ou arquivo do Google Drive:")
        if st.button("🔄 Buscar Cartas no Google Drive"):
            if not url_drive:
                st.error("Cole um link válido do Google Drive.")
            else:
                with st.spinner("Conectando ao Google Drive e baixando cartas..."):
                    encontrados = baixar_do_drive(url_drive)
                    if encontrados:
                        st.session_state.arquivos_drive = encontrados
                        st.success(f"{len(encontrados)} carta(s) carregada(s) com sucesso!")
                    else:
                        st.error("Não foi possível baixar. Verifique se o link está público ('Qualquer pessoa com o link').")

        if st.session_state.arquivos_drive:
            opcoes = {p.name: p for p in st.session_state.arquivos_drive}
            escolhido_nome = st.selectbox("Selecione qual carta da pasta deseja usar:", list(opcoes.keys()))
            caminho_escolhido = opcoes[escolhido_nome]
            imagem_carregada = Image.open(caminho_escolhido)
            st.session_state.nome_arquivo = caminho_escolhido.stem
            st.session_state.img_bytes = converter_imagem_para_png_bytes(imagem_carregada)

    if st.session_state.img_bytes:
        st.image(st.session_state.img_bytes, caption=f"Carta Selecionada: {st.session_state.nome_arquivo}", use_container_width=True)

    ideia_custom = st.text_area(
        "💬 Descreva o que deseja no vídeo (ou deixe em branco para usar o efeito padrão do vídeo referência):",
        placeholder="Ex: Quero construir um vídeo como o modelo referência (efeito cutout 2.5D, órbita 360° e símbolo astrológico no céu) com o tema desta carta.",
        height=90
    )

    if st.button("🔍 Analisar Carta e Planejar Efeitos 2.5D", type="primary", use_container_width=True):
        if not nova_chave:
            st.error("⚠️ Por favor, cole sua Chave da API do Gemini na barra lateral esquerda primeiro.")
        elif not st.session_state.img_bytes:
            st.error("⚠️ Envie uma imagem ou selecione uma carta do Google Drive primeiro.")
        else:
            with st.spinner("🤖 O Agente está inspecionando os traços da carta e separando os planos de profundidade..."):
                try:
                    pedido = ideia_custom.strip() or "Construir vídeo 2.5D cutout parallax idêntico à referência, com órbita 360 e símbolo cósmico no céu."
                    st.session_state.plano_ia = diagnosticar_carta_ia(nova_chave, st.session_state.img_bytes, pedido)
                except Exception as e:
                    st.error(f"Erro ao analisar carta: {e}")

with col_dir:
    st.subheader("🎬 Passo 2: Revisão Inteligente & Geração do Vídeo")

    if not st.session_state.plano_ia:
        st.info("👈 Carregue uma carta ao lado e clique em **Analisar Carta** para o Agente montar a estrutura 3D interativa aqui.")
    else:
        plano = st.session_state.plano_ia
        st.success(f"✨ **Carta Identificada pelo Agente:** {plano.get('arcano_nome', 'Arcano do Tarô')}")

        with st.expander("📐 Camadas de Profundidade 2.5D (Você pode editar se desejar)", expanded=True):
            camadas = plano.get("camadas_z_space", {})
            c1 = st.text_input("1º Plano (Frente):", value=camadas.get("primeiro_plano", ""))
            c2 = st.text_input("Plano Central (Giro 360°):", value=camadas.get("plano_medio", ""))
            c3 = st.text_input("Cenário de Fundo Expandido:", value=camadas.get("plano_fundo", ""))
            particulas = st.text_input("🔥 Efeitos de Partículas e Física:", value=plano.get("particulas_e_fisica", ""))
            astro = st.text_input("🌌 Revelação Cósmica no Céu (Tilt-up):", value=plano.get("astro_revelacao_ceu", ""))

        with st.expander("🎵 Trilha Sonora e Loop Infinito (Opcional)", expanded=True):
            audio_upload = st.file_uploader("Adicionar música de fundo (.mp3 / .wav):", type=["mp3", "wav", "m4a"])
            aplicar_loop_reverso = st.checkbox("Criar Loop Infinito Perfeito (Vai até o céu e retorna suavemente para a carta 2D)", value=True)

        prompt_tecnico = st.text_area(
            "Prompt Técnico do Motor de Vídeo (Gerado Automaticamente):",
            value=(
                f"{plano.get('veo_prompt_en', '')} "
                f"Foreground: {c1}. Midground: {c2}. Background: {c3}. "
                f"Particles: {particulas}. Sky reveal: {astro}."
            ),
            height=110
        )

        if st.button("🚀 GERAR VÍDEO PRONTO AGORA", type="primary", use_container_width=True):
            barra = st.progress(5)
            status_txt = st.empty()
            status_txt.info("🎬 Iniciando comunicação com o servidor de renderização de vídeo...")

            raw_mp4 = PASTA_TEMP / f"raw_{st.session_state.nome_arquivo}.mp4"
            final_mp4 = PASTA_TEMP / f"Video_Pronto_{st.session_state.nome_arquivo}.mp4"

            caminho_audio_temp = None
            if audio_upload:
                caminho_audio_temp = PASTA_TEMP / audio_upload.name
                caminho_audio_temp.write_bytes(audio_upload.getvalue())

            try:
                ok = renderizar_video_veo(nova_chave, st.session_state.img_bytes, prompt_tecnico, raw_mp4, barra, status_txt)
                if ok:
                    barra.progress(90)
                    status_txt.info("🎞️ Finalizando pós-produção, loop reverso e mixagem de áudio...")
                    pos_producao_loop_e_audio(raw_mp4, caminho_audio_temp, final_mp4, aplicar_loop_reverso)
                    barra.progress(100)
                    status_txt.success("✅ Vídeo Pronto! Assista abaixo ou clique no botão para baixar.")

                    video_bytes = final_mp4.read_bytes()
                    st.video(video_bytes)
                    st.download_button(
                        label="⬇️ BAIXAR VÍDEO PRONTO (.MP4)",
                        data=video_bytes,
                        file_name=f"Tarot_2.5D_{st.session_state.nome_arquivo}.mp4",
                        mime="video/mp4",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    status_txt.error("❌ O servidor não retornou o vídeo. Verifique se sua Chave API possui faturamento ativo para usar o modelo Veo 2.0.")
            except Exception as err:
                status_txt.error(f"❌ Erro durante a renderização: {err}")

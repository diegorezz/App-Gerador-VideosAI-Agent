import os
import io
import math
import time
import json
import random
import shutil
import subprocess
from pathlib import Path
import numpy as np
import streamlit as st
import gdown
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from google import genai
from google.genai import types

# Fallback garantido para FFmpeg mesmo se packages.txt ainda não tiver reiniciado o container
try:
    import imageio_ffmpeg
    FFMPEG_BIN = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_BIN = shutil.which("ffmpeg")

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
  "simbolo_unicode": "Caractere unicode ou símbolo astrológico (ex: ♈, ♄, ☉, ☽, ✡, ♃)",
  "cor_particula_rgb": [217, 178, 90],
  "camadas_z_space": {
    "primeiro_plano": "Elementos na frente da cena",
    "plano_medio": "Figura central / trono / personagem principal",
    "plano_fundo": "Paisagem de fundo expandida"
  },
  "particulas_e_fisica": "Efeitos ativos (ex: brasas douradas, vento místico, centelhas astrais)",
  "astro_revelacao_ceu": "Planeta, signo ou símbolo cabalístico/astrológico revelado quando a câmera sobe para o céu noturno",
  "veo_prompt_en": "2.5D layered paper cutout parallax animation of the provided Tarot card. Start with the flat 2D card, deconstruct into 3D depth layers, camera zooms in and orbits 360 degrees around the thin paper-cutout central figure, particles floating, camera tilts up to the dark night sky revealing the astrological symbol, then seamlessly loops back to the original 2D card frame. Woodcut vintage tarot aesthetic, vertical 9:16."
}
"""

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
    return FFMPEG_BIN is not None and os.path.exists(FFMPEG_BIN) or shutil.which("ffmpeg") is not None

def obter_executavel_ffmpeg() -> str:
    return shutil.which("ffmpeg") or FFMPEG_BIN or "ffmpeg"

def converter_imagem_para_png_bytes(img_pil: Image.Image) -> bytes:
    img_rgb = img_pil.convert("RGB")
    buf = io.BytesIO()
    img_rgb.save(buf, format="PNG")
    return buf.getvalue()

def baixar_do_drive(url: str) -> list[Path]:
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
    """Usa o Gemini 2.5 Flash (100% GRATUITO no Google AI Studio) para planejar o vídeo."""
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

# ==============================================================================
# MOTOR 1 (100% GRATUITO E NATIVO): RENDERIZADOR 2.5D PARALLAX & CUTOUT ENGINE
# ==============================================================================
def separar_camadas_25d(img_card: Image.Image, W: int = 720, H: int = 1280):
    """Cria as camadas de profundidade Z-space (Fundo místico, Figura Central Recortada e Moldura/1º Plano)."""
    card_resized = img_card.convert("RGBA").resize((int(W * 0.82), int(H * 0.78)), Image.Resampling.LANCZOS)
    cw, ch = card_resized.size

    # Camada 1: Fundo expandido desfocado e escurecido (cenário profundo)
    bg_layer = img_card.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    bg_layer = bg_layer.filter(ImageFilter.GaussianBlur(radius=18))
    bg_layer = ImageEnhance.Brightness(bg_layer).enhance(0.38)

    # Camada 2: Recorte Central (Sprite 2.5D estilo Paper Cutout com borda de papel/dourada)
    mask_mid = Image.new("L", (cw, ch), 0)
    draw_m = ImageDraw.Draw(mask_mid)
    draw_m.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=28, fill=255)
    mask_mid = mask_mid.filter(ImageFilter.GaussianBlur(radius=3))

    mid_cutout = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    mid_cutout.paste(card_resized, (0, 0), mask_mid)
    # Adiciona borda fina estilo papel recortado (Paper Mario / Diorama)
    draw_border = ImageDraw.Draw(mid_cutout)
    draw_border.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=28, outline=(235, 220, 185, 230), width=5)

    # Camada 3: Moldura / Base inferior e topo da carta (Primeiro plano em paralaxe)
    fg_mask = Image.new("L", (cw, ch), 255)
    draw_fg = ImageDraw.Draw(fg_mask)
    draw_fg.rounded_rectangle((int(cw*0.12), int(ch*0.14), int(cw*0.88), int(ch*0.82)), radius=20, fill=0)
    fg_mask = fg_mask.filter(ImageFilter.GaussianBlur(radius=2))

    fg_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    fg_layer.paste(card_resized, (0, 0), fg_mask)

    return card_resized, bg_layer, mid_cutout, fg_layer

def aplicar_perspectiva_3d_cutout(img_rgba: Image.Image, angulo_graus: float) -> Image.Image:
    """Simula rotação 3D no eixo Y de um recorte de papel (efeito 2.5D de espessura fina)."""
    w, h = img_rgba.size
    cos_a = math.cos(math.radians(angulo_graus))
    fator_largura = max(0.18, abs(cos_a))
    nova_w = max(4, int(w * fator_largura))
    img_rot = img_rgba.resize((nova_w, h), Image.Resampling.LANCZOS)
    if cos_a < 0:
        img_rot = img_rot.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    offset_x = (w - nova_w) // 2
    # Sombra/espessura lateral do papel recortado quando gira
    espessura = int(6 * (1.0 - fator_largura)) + 2
    if espessura > 2:
        borda_papel = Image.new("RGBA", (nova_w, h), (180, 145, 75, 190))
        canvas.paste(borda_papel, (offset_x + espessura, 2), img_rot)
    canvas.paste(img_rot, (offset_x, 0), img_rot)
    return canvas

def renderizar_video_nativo_gratuito(
    img_bytes: bytes,
    plano: dict,
    saida_raw: Path,
    barra_progresso,
    texto_status,
    duracao_s: int = 8,
    fps: int = 24
) -> bool:
    """
    Motor 2.5D Diorama Parallax 100% Gratuito (Roda direto na CPU do Streamlit Cloud via FFmpeg Pipe).
    Executa exatamente os 5 atos do vídeo referência:
    1. Carta 2D estática -> Desconstrução em camadas Z-Space
    2. Zoom-in + Órbita 3D (efeito recorte de papel girando)
    3. Partículas místicas subindo
    4. Tilt-up para o céu estrelado revelando o astro/símbolo do Arcano
    """
    W, H = 720, 1280
    total_frames = duracao_s * fps
    img_pil = Image.open(io.BytesIO(img_bytes))
    card_full, bg_layer, mid_cutout, fg_layer = separar_camadas_25d(img_pil, W, H)
    cw, ch = card_full.size

    cor_p = tuple(plano.get("cor_particula_rgb", [217, 178, 90]))
    astro_txt = plano.get("astro_revelacao_ceu", "☉")
    simbolo = plano.get("simbolo_unicode", "✦")
    arcano_titulo = plano.get("arcano_nome", "ARCANO")

    # Gera estrelas para o céu cósmico (Tilt-up)
    rng = random.Random(42)
    estrelas = [(rng.randint(20, W-20), rng.randint(20, H-20), rng.randint(1, 3), rng.random()) for _ in range(140)]
    particulas = [
        {"x": rng.uniform(80, W-80), "y": rng.uniform(100, H-50), "vy": rng.uniform(3.0, 7.5), "r": rng.randint(2, 5), "fase": rng.uniform(0, 6.28)}
        for _ in range(55)
    ]

    ffmpeg_exe = obter_executavel_ffmpeg()
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        str(saida_raw)
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for f_idx in range(total_frames):
        t = f_idx / max(1, total_frames - 1) # 0.0 -> 1.0

        # Curvas de animação por fases:
        # Fase 1 (0.00 - 0.18): Carta 2D original se separando em 3D
        # Fase 2 (0.18 - 0.68): Zoom-in + Giro orbital 2.5D (Paper Cutout) + Paralaxe
        # Fase 3 (0.68 - 1.00): Câmera sobe para o céu noturno (Tilt-up) e revela o Astro
        if t < 0.18:
            p_fase = t / 0.18
            zoom_bg = 1.0 + 0.08 * p_fase
            zoom_mid = 1.0 + 0.14 * p_fase
            zoom_fg = 1.0 + 0.25 * p_fase
            angulo_y = 0.0
            tilt_ceu = 0.0
            mix_2d = 1.0 - p_fase
        elif t < 0.68:
            p_fase = (t - 0.18) / 0.50
            zoom_bg = 1.08 + 0.12 * math.sin(p_fase * math.pi)
            zoom_mid = 1.14 + 0.22 * math.sin(p_fase * math.pi)
            zoom_fg = 1.25 + 0.45 * p_fase
            # Faz o efeito de órbita 360 graus mostrando o recorte fino 2.5D
            angulo_y = p_fase * 360.0
            tilt_ceu = 0.0
            mix_2d = 0.0
        else:
            p_fase = (t - 0.68) / 0.32
            # Suavização cúbica para subida de câmera ao céu
            ease = p_fase * p_fase * (3 - 2 * p_fase)
            zoom_bg = 1.08
            zoom_mid = 1.14
            zoom_fg = 1.70
            angulo_y = 0.0
            tilt_ceu = ease
            mix_2d = 0.0

        # 1. Desenha o Céu Cósmico e o Cenário de Fundo (com deslocamento vertical de Tilt-up)
        frame = Image.new("RGBA", (W, H), (14, 9, 24, 255))
        draw_sky = ImageDraw.Draw(frame)

        # Desenha estrelas e o Astro no topo quando a câmera sobe
        offset_y_cena = int(tilt_ceu * H * 0.88)
        for sx, sy, sr, sf in estrelas:
            brilho = int(155 + 100 * math.sin(f_idx * 0.2 + sf * 10))
            pos_y_estrela = sy - int((1.0 - tilt_ceu) * H * 0.6)
            if 0 <= pos_y_estrela < H:
                draw_sky.ellipse((sx-sr, pos_y_estrela-sr, sx+sr, pos_y_estrela+sr), fill=(brilho, brilho, 255, 255))

        # Revelação do Astro / Planeta Regente no céu noturno
        if tilt_ceu > 0.15:
            alpha_astro = int(min(1.0, (tilt_ceu - 0.15) / 0.65) * 255)
            cx_ceu, cy_ceu = W // 2, int(H * 0.36)
            # Halo místico dourado em camadas concêntricas
            for r_halo in range(160, 40, -20):
                a_h = max(10, int(alpha_astro * (1 - r_halo / 170) * 0.35))
                draw_sky.ellipse((cx_ceu - r_halo, cy_ceu - r_halo, cx_ceu + r_halo, cy_ceu + r_halo), outline=(cor_p[0], cor_p[1], cor_p[2], a_h), width=3)
            # Anel planetário (estilo Saturno/Esfera celeste)
            draw_sky.arc((cx_ceu - 170, cy_ceu - 45, cx_ceu + 170, cy_ceu + 45), start=0, end=360, fill=(217, 178, 90, alpha_astro), width=4)
            draw_sky.ellipse((cx_ceu - 68, cy_ceu - 68, cx_ceu + 68, cy_ceu + 68), fill=(33, 26, 49, alpha_astro), outline=(217, 178, 90, alpha_astro), width=4)
            # Textos da revelação cósmica
            draw_sky.text((cx_ceu, cy_ceu - 12), simbolo, fill=(255, 235, 170, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 105), astro_txt.upper(), fill=(217, 178, 90, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 138), arcano_titulo.upper(), fill=(239, 231, 214, alpha_astro), anchor="mm")

        # 2. Renderiza Fundo da Carta (Z-Back)
        bg_w, bg_h = int(W * zoom_bg), int(H * zoom_bg)
        bg_zoomed = bg_layer.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
        frame.paste(bg_zoomed, ((W - bg_w)//2, (H - bg_h)//2 + offset_y_cena))

        # 3. Renderiza Figura Central Recortada em 2.5D com Giro Orbital 3D (Z-Mid)
        mid_3d = aplicar_perspectiva_3d_cutout(mid_cutout, angulo_y)
        mw, mh = int(cw * zoom_mid), int(ch * zoom_mid)
        mid_zoomed = mid_3d.resize((mw, mh), Image.Resampling.BILINEAR)
        pos_mid_x = (W - mw) // 2 + int(math.sin(math.radians(angulo_y)) * 28)
        pos_mid_y = (H - mh) // 2 + offset_y_cena
        frame.paste(mid_zoomed, (pos_mid_x, pos_mid_y), mid_zoomed)

        # 4. Renderiza Primeiro Plano / Moldura em Paralaxe (Z-Front)
        if zoom_fg < 1.85:
            fw, fh = int(cw * zoom_fg), int(ch * zoom_fg)
            fg_zoomed = fg_layer.resize((fw, fh), Image.Resampling.BILINEAR)
            pos_fg_x = (W - fw) // 2 - int(math.sin(math.radians(angulo_y)) * 45)
            pos_fg_y = (H - fh) // 2 + int(offset_y_cena * 1.25)
            frame.paste(fg_zoomed, (pos_fg_x, pos_fg_y), fg_zoomed)

        # 5. Transição suave a partir da Carta 2D pura nos primeiros frames
        if mix_2d > 0.01:
            c2d_layer = Image.new("RGBA", (W, H), (21, 16, 31, int(255 * mix_2d)))
            c2d_layer.paste(card_full, ((W - cw)//2, (H - ch)//2), card_full)
            frame = Image.alpha_composite(frame, c2d_layer)

        # 6. Partículas Dinâmicas (Brasas / Luzes Astrais)
        draw_p = ImageDraw.Draw(frame)
        for p in particulas:
            p["y"] -= p["vy"]
            if p["y"] < 0:
                p["y"] = H
            px = int(p["x"] + math.sin(f_idx * 0.12 + p["fase"]) * 14)
            py = int(p["y"])
            r = p["r"]
            draw_p.ellipse((px-r, py-r, px+r, py+r), fill=(cor_p[0], cor_p[1], cor_p[2], 210))

        # Envia frame RGB para o pipe do FFmpeg
        proc.stdin.write(frame.convert("RGB").tobytes())

        if f_idx % 8 == 0 or f_idx == total_frames - 1:
            pct = int(10 + 75 * (f_idx / total_frames))
            barra_progresso.progress(pct)
            texto_status.info(f"🎨 [Motor 2.5D Gratuito] Renderizando quadro {f_idx+1}/{total_frames} (Paralaxe, Giro 3D e Céu Cósmico)...")

    proc.stdin.close()
    proc.wait()
    return saida_raw.exists()

# ==============================================================================
# MOTOR 2 (OPCIONAL): GOOGLE VEO 2.0 (PARA QUEM TIVER CHAVE COM BILLING)
# ==============================================================================
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
        texto_status.info("⏳ O Motor Veo 2.0 está renderizando o vídeo na nuvem...")
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

    ffmpeg_exe = obter_executavel_ffmpeg()
    filtro_loop = "[0:v]split[main][rev];[rev]reverse[reversed];[main][reversed]concat=n=2:v=1:a=0[outv]"
    cmd = [ffmpeg_exe, "-y", "-i", str(video_raw)]

    if audio_path and audio_path.exists():
        cmd.extend(["-stream_loop", "-1", "-i", str(audio_path)])
        if aplicar_loop:
            cmd.extend(["-filter_complex", filtro_loop, "-map", "[outv]", "-map", "1:a", "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(video_final)])
        else:
            cmd.extend(["-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "copy", "-c:a", "aac", str(video_final)])
    else:
        if aplicar_loop:
            cmd.extend(["-filter_complex", filtro_loop, "-map", "[outv]", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(video_final)])
        else:
            shutil.copy(video_raw, video_final)
            return

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ================= INTERFACE VISUAL DO APLICATIVO =================

st.title("🎴 Tarot Video Studio 2.5D")
st.caption("Plataforma Inteligente de Criação de Vídeos em Camadas 2.5D / Diorama Parallax — 100% Gratuito")

with st.sidebar:
    st.header("⚙️ 1. Configuração Inicial")
    chave_atual = carregar_chave_salva()
    nova_chave = st.text_input(
        "Chave Gratuita Google Gemini (AIza...):",
        value=chave_atual,
        type="password",
        help="A chave gratuita do Google AI Studio já analisa a carta sem custo! Para a geração do vídeo, use o Motor 2.5D Gratuito abaixo."
    )
    if nova_chave != chave_atual and nova_chave:
        salvar_chave(nova_chave)
        st.success("Chave salva!")

    st.markdown("[🔑 Pegar Chave Gratuita no Google AI Studio](https://aistudio.google.com/apikey)")
    st.divider()

    st.subheader("🎬 Motor de Renderização de Vídeo")
    motor_escolhido = st.radio(
        "Escolha como gerar o vídeo:",
        [
            "🆓 Motor 2.5D Diorama Parallax (100% Gratuito - Sem API Paga)",
            "💎 Google Veo 2.0 Cloud (Requer API com Faturamento)"
        ],
        index=0
    )

    st.divider()
    st.subheader("🛠️ Status do Sistema")
    if nova_chave:
        st.success("✅ Motor de IA Conectado (Gemini Free Tier)")
    else:
        st.warning("⚠️ Insira sua Chave Gratuita acima")

    if verificar_ffmpeg():
        st.success("✅ FFmpeg Ativo (Loop 16s + Áudio Habilitados)")
    else:
        st.warning("⚠️ FFmpeg não detectado")

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

    if st.button("🔍 Analisar Carta e Planejar Efeitos 2.5D (Gratuito)", type="primary", use_container_width=True):
        if not nova_chave:
            st.error("⚠️ Cole sua Chave Gratuita do Gemini na barra lateral esquerda primeiro.")
        elif not st.session_state.img_bytes:
            st.error("⚠️ Envie uma imagem ou selecione uma carta do Google Drive primeiro.")
        else:
            with st.spinner("🤖 O Agente (Gemini Flash Gratuito) está inspecionando a carta e separando as camadas..."):
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
            simbolo_uni = st.text_input("✡️ Símbolo Esotérico / Astrológico no Céu:", value=plano.get("simbolo_unicode", "✦"))

        with st.expander("🎵 Trilha Sonora e Loop Infinito (16 segundos)", expanded=True):
            audio_upload = st.file_uploader("Adicionar música de fundo (.mp3 / .wav):", type=["mp3", "wav", "m4a"])
            aplicar_loop_reverso = st.checkbox("Criar Loop Infinito Perfeito (Vai até o céu e retorna suavemente para a carta 2D)", value=True)

        plano["astro_revelacao_ceu"] = astro
        plano["simbolo_unicode"] = simbolo_uni

        prompt_tecnico = st.text_area(
            "Prompt Técnico do Motor de Vídeo:",
            value=(
                f"{plano.get('veo_prompt_en', '')} "
                f"Foreground: {c1}. Midground: {c2}. Background: {c3}. "
                f"Particles: {particulas}. Sky reveal: {astro}."
            ),
            height=95
        )

        if st.button("🚀 GERAR VÍDEO PRONTO AGORA", type="primary", use_container_width=True):
            barra = st.progress(5)
            status_txt = st.empty()

            raw_mp4 = PASTA_TEMP / f"raw_{st.session_state.nome_arquivo}.mp4"
            final_mp4 = PASTA_TEMP / f"Video_Pronto_{st.session_state.nome_arquivo}.mp4"

            caminho_audio_temp = None
            if audio_upload:
                caminho_audio_temp = PASTA_TEMP / audio_upload.name
                caminho_audio_temp.write_bytes(audio_upload.getvalue())

            try:
                if "100% Gratuito" in motor_escolhido:
                    ok = renderizar_video_nativo_gratuito(
                        st.session_state.img_bytes,
                        plano,
                        raw_mp4,
                        barra,
                        status_txt
                    )
                else:
                    ok = renderizar_video_veo(nova_chave, st.session_state.img_bytes, prompt_tecnico, raw_mp4, barra, status_txt)

                if ok:
                    barra.progress(90)
                    status_txt.info("🎞️ Finalizando pós-produção, loop reverso de 16s e mixagem de áudio via FFmpeg...")
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
                    status_txt.error("❌ Não foi possível concluir a geração do vídeo.")
            except Exception as err:
                status_txt.error(f"❌ Erro durante a renderização: {err}")

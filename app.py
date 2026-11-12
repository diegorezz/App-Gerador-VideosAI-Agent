import os
import re
import io
import math
import time
import json
import random
import shutil
import subprocess
from pathlib import Path
import requests
import numpy as np
import streamlit as st
import gdown
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from google import genai
from google.genai import types

# Fallback garantido para FFmpeg
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
    return (FFMPEG_BIN is not None and os.path.exists(FFMPEG_BIN)) or (shutil.which("ffmpeg") is not None)

def obter_executavel_ffmpeg() -> str:
    return shutil.which("ffmpeg") or FFMPEG_BIN or "ffmpeg"

def converter_imagem_para_png_bytes(img_pil: Image.Image) -> bytes:
    img_rgb = img_pil.convert("RGB")
    buf = io.BytesIO()
    img_rgb.save(buf, format="PNG")
    return buf.getvalue()

# ==============================================================================
# CONECTOR GOOGLE DRIVE ULTRA-RÁPIDO (EVITA TYPEERROR DO GDOWN E BAIXA SOB DEMANDA)
# ==============================================================================
def extrair_id_drive(url: str) -> tuple[str | None, str]:
    """Extrai o ID limpo da pasta ou do arquivo do Google Drive, ignorando ?usp=drive_link."""
    url = url.strip()
    m_folder = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if m_folder:
        return m_folder.group(1), "folder"
    m_file = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m_file:
        return m_file.group(1), "file"
    m_id = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m_id:
        return m_id.group(1), "file"
    return None, "unknown"

def listar_arquivos_pasta_drive(url: str) -> list[dict]:
    """
    Lista instantaneamente os arquivos de uma pasta pública do Drive (via embeddedfolderview)
    sem travar baixando gigabytes de uma vez e sem quebrar com ?usp=drive_link.
    Retorna lista de dicts: [{"name": nome, "id": file_id, "local_path": None}]
    """
    drive_id, tipo = extrair_id_drive(url)
    if not drive_id:
        raise ValueError("Link do Google Drive inválido. Use um link de pasta (/folders/...) ou arquivo (/file/d/...).")

    extensoes_img = (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp")

    if tipo == "file":
        return [{"name": f"Carta_Drive_{drive_id[:6]}.tif", "id": drive_id, "local_path": None}]

    # Método 1: Leitura instantânea via página pública embeddedfolderview do Google Drive
    embed_url = f"https://drive.google.com/embeddedfolderview?id={drive_id}#list"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(embed_url, headers=headers, timeout=20)

    itens = []
    if resp.status_code == 200:
        # Captura blocos de entradas de arquivo na visualização de lista do Drive
        padrao = re.compile(
            r'id="entry-([a-zA-Z0-9_-]+)".*?class="flip-entry-title">([^<]+)</div>',
            re.DOTALL
        )
        for m in padrao.finditer(resp.text):
            f_id, f_name = m.group(1), m.group(2).strip()
            if f_name.lower().endswith(extensoes_img):
                itens.append({"name": f_name, "id": f_id, "local_path": None})

    if itens:
        itens.sort(key=lambda x: x["name"])
        return itens

    # Método 2 (Fallback): gdown passando id limpo e sem argumentos conflitantes
    pasta_destino = PASTA_TEMP / "drive_sync"
    pasta_destino.mkdir(exist_ok=True)
    arquivos = gdown.download_folder(id=drive_id, output=str(pasta_destino), quiet=True, use_cookies=False)
    if arquivos:
        for p in arquivos:
            caminho = Path(p)
            if caminho.suffix.lower() in extensoes_img:
                itens.append({"name": caminho.name, "id": None, "local_path": caminho})
    return itens

def baixar_carta_individual_drive(item: dict) -> Path:
    """Baixa apenas a carta selecionada pelo usuário (muito mais rápido e sem erro de limite)."""
    if item.get("local_path") and Path(item["local_path"]).exists():
        return Path(item["local_path"])

    pasta_destino = PASTA_TEMP / "drive_sync"
    pasta_destino.mkdir(exist_ok=True)
    f_id = item["id"]
    destino_arquivo = pasta_destino / item["name"]

    if destino_arquivo.exists() and destino_arquivo.stat().st_size > 1000:
        return destino_arquivo

    # Download direto via endpoint de exportação/uc do Google Drive
    url_dl = f"https://drive.google.com/uc?id={f_id}&export=download"
    caminho = gdown.download(url=url_dl, output=str(destino_arquivo), quiet=True, fuzzy=True)
    if caminho and os.path.exists(caminho):
        return Path(caminho)

    # Fallback via requests direto
    r = requests.get(url_dl, stream=True, timeout=30)
    if r.status_code == 200:
        with open(destino_arquivo, "wb") as f:
            for chunk in r.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
        return destino_arquivo

    raise RuntimeError("Não foi possível baixar esta carta. Verifique se a pasta do Drive está pública ('Qualquer pessoa com o link').")

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
    card_resized = img_card.convert("RGBA").resize((int(W * 0.82), int(H * 0.78)), Image.Resampling.LANCZOS)
    cw, ch = card_resized.size

    bg_layer = img_card.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    bg_layer = bg_layer.filter(ImageFilter.GaussianBlur(radius=18))
    bg_layer = ImageEnhance.Brightness(bg_layer).enhance(0.38)

    mask_mid = Image.new("L", (cw, ch), 0)
    draw_m = ImageDraw.Draw(mask_mid)
    draw_m.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=28, fill=255)
    mask_mid = mask_mid.filter(ImageFilter.GaussianBlur(radius=3))

    mid_cutout = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    mid_cutout.paste(card_resized, (0, 0), mask_mid)
    draw_border = ImageDraw.Draw(mid_cutout)
    draw_border.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=28, outline=(235, 220, 185, 230), width=5)

    fg_mask = Image.new("L", (cw, ch), 255)
    draw_fg = ImageDraw.Draw(fg_mask)
    draw_fg.rounded_rectangle((int(cw*0.12), int(ch*0.14), int(cw*0.88), int(ch*0.82)), radius=20, fill=0)
    fg_mask = fg_mask.filter(ImageFilter.GaussianBlur(radius=2))

    fg_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    fg_layer.paste(card_resized, (0, 0), fg_mask)

    return card_resized, bg_layer, mid_cutout, fg_layer

def aplicar_perspectiva_3d_cutout(img_rgba: Image.Image, angulo_graus: float) -> Image.Image:
    w, h = img_rgba.size
    cos_a = math.cos(math.radians(angulo_graus))
    fator_largura = max(0.18, abs(cos_a))
    nova_w = max(4, int(w * fator_largura))
    img_rot = img_rgba.resize((nova_w, h), Image.Resampling.LANCZOS)
    if cos_a < 0:
        img_rot = img_rot.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    offset_x = (w - nova_w) // 2
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
    W, H = 720, 1280
    total_frames = duracao_s * fps
    img_pil = Image.open(io.BytesIO(img_bytes))
    card_full, bg_layer, mid_cutout, fg_layer = separar_camadas_25d(img_pil, W, H)
    cw, ch = card_full.size

    cor_p = tuple(plano.get("cor_particula_rgb", [217, 178, 90]))
    astro_txt = plano.get("astro_revelacao_ceu", "☉")
    simbolo = plano.get("simbolo_unicode", "✦")
    arcano_titulo = plano.get("arcano_nome", "ARCANO")

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
        t = f_idx / max(1, total_frames - 1)

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
            angulo_y = p_fase * 360.0
            tilt_ceu = 0.0
            mix_2d = 0.0
        else:
            p_fase = (t - 0.68) / 0.32
            ease = p_fase * p_fase * (3 - 2 * p_fase)
            zoom_bg = 1.08
            zoom_mid = 1.14
            zoom_fg = 1.70
            angulo_y = 0.0
            tilt_ceu = ease
            mix_2d = 0.0

        frame = Image.new("RGBA", (W, H), (14, 9, 24, 255))
        draw_sky = ImageDraw.Draw(frame)

        offset_y_cena = int(tilt_ceu * H * 0.88)
        for sx, sy, sr, sf in estrelas:
            brilho = int(155 + 100 * math.sin(f_idx * 0.2 + sf * 10))
            pos_y_estrela = sy - int((1.0 - tilt_ceu) * H * 0.6)
            if 0 <= pos_y_estrela < H:
                draw_sky.ellipse((sx-sr, pos_y_estrela-sr, sx+sr, pos_y_estrela+sr), fill=(brilho, brilho, 255, 255))

        if tilt_ceu > 0.15:
            alpha_astro = int(min(1.0, (tilt_ceu - 0.15) / 0.65) * 255)
            cx_ceu, cy_ceu = W // 2, int(H * 0.36)
            for r_halo in range(160, 40, -20):
                a_h = max(10, int(alpha_astro * (1 - r_halo / 170) * 0.35))
                draw_sky.ellipse((cx_ceu - r_halo, cy_ceu - r_halo, cx_ceu + r_halo, cy_ceu + r_halo), outline=(cor_p[0], cor_p[1], cor_p[2], a_h), width=3)
            draw_sky.arc((cx_ceu - 170, cy_ceu - 45, cx_ceu + 170, cy_ceu + 45), start=0, end=360, fill=(217, 178, 90, alpha_astro), width=4)
            draw_sky.ellipse((cx_ceu - 68, cy_ceu - 68, cx_ceu + 68, cy_ceu + 68), fill=(33, 26, 49, alpha_astro), outline=(217, 178, 90, alpha_astro), width=4)
            draw_sky.text((cx_ceu, cy_ceu - 12), simbolo, fill=(255, 235, 170, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 105), astro_txt.upper(), fill=(217, 178, 90, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 138), arcano_titulo.upper(), fill=(239, 231, 214, alpha_astro), anchor="mm")

        bg_w, bg_h = int(W * zoom_bg), int(H * zoom_bg)
        bg_zoomed = bg_layer.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
        frame.paste(bg_zoomed, ((W - bg_w)//2, (H - bg_h)//2 + offset_y_cena))

        mid_3d = aplicar_perspectiva_3d_cutout(mid_cutout, angulo_y)
        mw, mh = int(cw * zoom_mid), int(ch * zoom_mid)
        mid_zoomed = mid_3d.resize((mw, mh), Image.Resampling.BILINEAR)
        pos_mid_x = (W - mw) // 2 + int(math.sin(math.radians(angulo_y)) * 28)
        pos_mid_y = (H - mh) // 2 + offset_y_cena
        frame.paste(mid_zoomed, (pos_mid_x, pos_mid_y), mid_zoomed)

        if zoom_fg < 1.85:
            fw, fh = int(cw * zoom_fg), int(ch * zoom_fg)
            fg_zoomed = fg_layer.resize((fw, fh), Image.Resampling.BILINEAR)
            pos_fg_x = (W - fw) // 2 - int(math.sin(math.radians(angulo_y)) * 45)
            pos_fg_y = (H - fh) // 2 + int(offset_y_cena * 1.25)
            frame.paste(fg_zoomed, (pos_fg_x, pos_fg_y), fg_zoomed)

        if mix_2d > 0.01:
            c2d_layer = Image.new("RGBA", (W, H), (21, 16, 31, int(255 * mix_2d)))
            c2d_layer.paste(card_full, ((W - cw)//2, (H - ch)//2), card_full)
            frame = Image.alpha_composite(frame, c2d_layer)

        draw_p = ImageDraw.Draw(frame)
        for p in particulas:
            p["y"] -= p["vy"]
            if p["y"] < 0:
                p["y"] = H
            px = int(p["x"] + math.sin(f_idx * 0.12 + p["fase"]) * 14)
            py = int(p["y"])
            r = p["r"]
            draw_p.ellipse((px-r, py-r, px+r, py+r), fill=(cor_p[0], cor_p[1], cor_p[2], 210))

        proc.stdin.write(frame.convert("RGB").tobytes())

        if f_idx % 8 == 0 or f_idx == total_frames - 1:
            pct = int(10 + 75 * (f_idx / total_frames))
            barra_progresso.progress(pct)
            texto_status.info(f"🎨 [Motor 2.5D Gratuito] Renderizando quadro {f_idx+1}/{total_frames} (Paralaxe, Giro 3D e Céu Cósmico)...")

    proc.stdin.close()
    proc.wait()
    return saida_raw.exists()

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
                with st.spinner("Listando cartas da pasta do Google Drive instantaneamente..."):
                    try:
                        encontrados = listar_arquivos_pasta_drive(url_drive)
                        if encontrados:
                            st.session_state.arquivos_drive = encontrados
                            st.success(f"{len(encontrados)} carta(s) encontrada(s) na pasta!")
                        else:
                            st.error("Nenhuma imagem encontrada. Verifique se a permissão da pasta está como 'Qualquer pessoa com o link'.")
                    except Exception as err_dl:
                        st.error(f"Erro ao acessar link do Drive: {err_dl}")

        if st.session_state.arquivos_drive:
            opcoes = {item["name"]: item for item in st.session_state.arquivos_drive}
            escolhido_nome = st.selectbox("Selecione qual carta da pasta deseja usar:", list(opcoes.keys()))
            item_escolhido = opcoes[escolhido_nome]
            with st.spinner(f"Baixando e convertendo {escolhido_nome}..."):
                try:
                    caminho_escolhido = baixar_carta_individual_drive(item_escolhido)
                    imagem_carregada = Image.open(caminho_escolhido)
                    st.session_state.nome_arquivo = Path(escolhido_nome).stem
                    st.session_state.img_bytes = converter_imagem_para_png_bytes(imagem_carregada)
                except Exception as err_card:
                    st.error(f"Erro ao carregar a carta selecionada: {err_card}")

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

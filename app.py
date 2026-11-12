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
    page_title="Tarot Iniciático Studio 2.5D",
    page_icon="🕯️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# DESIGN SYSTEM: GUIA TAROT INICIÁTICO (PAPIRO ANTIGO, LUZ DE VELAS & CARMESIM)
# Paleta extraída das referências visuais:
# - Pergaminho / Papiro Antigo: #E6C696 | #DFB782 | #D1A671
# - Mogno Escuro / Sombra à Luz de Velas: #140904 | #241107 | #3B1D0E
# - Tinta de Gravura / Sépia Profundo: #3D2313 | #673F1D
# - Carmesim Hermético / Manto Alquímico: #8B261D | #A43222
# - Ouro de Candelabro / Chama: #B8863B | #E5A93C
# ==============================================================================
DESIGN_SYSTEM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600;700&family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&display=swap');

:root {
    --bg-candle-dark: #140904;
    --bg-mahogany: #220E05;
    --parchment-light: #F2DEC1;
    --parchment-mid: #E6C696;
    --parchment-aged: #D5AD7A;
    --engraving-ink: #2C1609;
    --sepia-line: #8C5E35;
    --hermetic-crimson: #8B261D;
    --candle-gold: #C8923B;
    --flame-glow: #F3B852;
}

/* Fundo Geral: Ambiência de Ritual à Luz de Velas e Madeira Antiga */
.stApp {
    background: radial-gradient(circle at 50% 12%, #2E1509 0%, #170A03 55%, #0C0401 100%) !important;
    color: var(--parchment-mid) !important;
    font-family: 'Cormorant Garamond', Georgia, serif !important;
}

/* Barra Lateral: Couro Antigo & Candelabro */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E0D05 0%, #120702 100%) !important;
    border-right: 1px solid #5A381E !important;
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.65) !important;
}

/* Tipografia Clássica Editorial ("Guia Tarot Iniciático") */
h1, h2, h3, .tarot-title {
    font-family: 'Cinzel', 'Cormorant Garamond', Georgia, serif !important;
    color: var(--parchment-light) !important;
    letter-spacing: 0.06em !important;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.75);
}

p, label, .stMarkdown, .stCaption {
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 1.08rem !important;
    color: var(--parchment-mid) !important;
}

/* Cabeçalho Ornamentado estilo Capa do Livro "Guia Tarot Iniciático" */
.iniciatico-header {
    background: linear-gradient(135deg, rgba(46, 21, 9, 0.92) 0%, rgba(26, 11, 4, 0.96) 100%);
    border: 2px solid var(--sepia-line);
    outline: 1px solid rgba(230, 198, 150, 0.25);
    outline-offset: -6px;
    border-radius: 6px;
    padding: 22px 28px;
    margin-bottom: 24px;
    text-align: center;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7), inset 0 0 40px rgba(184, 134, 59, 0.08);
}

.iniciatico-header .subtitle-top {
    font-family: 'Cinzel', serif;
    font-size: 0.85rem;
    letter-spacing: 0.28em;
    color: var(--candle-gold);
    text-transform: uppercase;
    margin-bottom: 4px;
}

.iniciatico-header h1 {
    font-size: 2.35rem !important;
    margin: 0 !important;
    color: var(--parchment-light) !important;
    font-weight: 600 !important;
}

.iniciatico-divider {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin: 10px auto;
    color: var(--candle-gold);
    font-size: 1.1rem;
}

.iniciatico-divider::before,
.iniciatico-divider::after {
    content: "";
    height: 1px;
    width: 110px;
    background: linear-gradient(90deg, transparent, var(--candle-gold), transparent);
}

.iniciatico-header .subtitle-bottom {
    font-family: 'Cormorant Garamond', serif;
    font-style: italic;
    font-size: 1.15rem;
    color: var(--parchment-aged);
    margin-top: 2px;
}

/* Botões Primários: Manto Carmesim Hermético & Borda Dourada */
.stButton > button[kind="primary"], .stDownloadButton > button {
    background: linear-gradient(180deg, #9E2E22 0%, #6E1B12 100%) !important;
    color: #F8E5C8 !important;
    border: 1px solid #D5A458 !important;
    border-radius: 4px !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    padding: 0.65rem 1.2rem !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 225, 175, 0.3) !important;
    transition: all 0.25s ease !important;
}

.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
    background: linear-gradient(180deg, #B5382A 0%, #822116 100%) !important;
    border-color: #F3C677 !important;
    box-shadow: 0 0 18px rgba(213, 164, 88, 0.45) !important;
    transform: translateY(-1px);
}

/* Botões Secundários: Pergaminho Escuro */
.stButton > button[kind="secondary"] {
    background: #281308 !important;
    color: var(--parchment-mid) !important;
    border: 1px solid var(--sepia-line) !important;
    font-family: 'Cinzel', serif !important;
}

/* Campos de Entrada, Textarea e Selectbox: Papiro Escuro com Filete Sépia */
.stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div {
    background-color: #1D0D05 !important;
    color: var(--parchment-light) !important;
    border: 1px solid #673F1D !important;
    border-radius: 4px !important;
    font-family: 'Cormorant Garamond', Georgia, serif !important;
    font-size: 1.05rem !important;
}

.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--candle-gold) !important;
    box-shadow: 0 0 8px rgba(200, 146, 59, 0.35) !important;
}

/* Expanders e Painéis: Moldura Dupla de Carta em Papiro */
div[data-testid="stExpander"] {
    background: rgba(34, 15, 6, 0.85) !important;
    border: 1px solid #673F1D !important;
    border-radius: 5px !important;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.45);
}

/* Upload Box estilo Pergaminho */
section[data-testid="stFileUploaderDropzone"] {
    background: rgba(42, 19, 8, 0.7) !important;
    border: 1px dashed #B8863B !important;
    border-radius: 6px !important;
}

/* Imagens com Moldura de Carta à Luz de Velas */
div[data-testid="stImage"] img {
    border: 2px solid #8C5E35;
    border-radius: 6px;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.75);
}
</style>
"""
st.markdown(DESIGN_SYSTEM_CSS, unsafe_allow_html=True)

PASTA_TEMP = Path("./workspace_temp")
PASTA_TEMP.mkdir(exist_ok=True)
ARQUIVO_CHAVE = Path("./.api_key_saved")

SYSTEM_PROMPT = """
Você é um Diretor Técnico de Vídeo 2.5D/3D especialista em Tarô Iniciático e Gravuras Herméticas Renascentistas.
Analise a imagem da carta fornecida e estruture a engenharia de cena para transformar esta carta estática 2D em um vídeo 2.5D com efeito Paper Cutout / Diorama Parallax, utilizando a estética de Papiro Antigo, Gravura Clássica, Carmesim Alquímico e Ouro à Luz de Velas.

Retorne ESTRITAMENTE um JSON válido com a seguinte estrutura:
{
  "arcano_nome": "Nome e numeral romano do Arcano",
  "simbolo_unicode": "Caractere unicode ou símbolo astrológico/hermético (ex: ♈, ♄, ☉, ☽, ✡, ♃, ☿)",
  "cor_particula_rgb": [228, 189, 133],
  "duracao_sugerida_segundos": 20,
  "camadas_z_space": {
    "primeiro_plano": "Elementos na frente da cena (ex: tábuas, pedras, lírios, instrumentos herméticos)",
    "plano_medio": "Figura central / arquétipo em recorte 2.5D com manto carmesim e traços de gravura",
    "plano_fundo": "Paisagem renascentista em papiro antigo expandida ao fundo"
  },
  "particulas_e_fisica": "Efeitos ativos (ex: brasas de luz de vela, poeira de ouro hermético, centelhas solares)",
  "astro_revelacao_ceu": "Planeta, esfera armilar, diagrama celestial ou signo revelado quando a câmera sobe para o céu",
  "veo_prompt_en": "2.5D layered antique parchment cutout parallax animation of the provided Tarot card. Start with the flat vintage woodcut card on aged papyrus, deconstruct into 3D depth layers, candlelight golden particles floating, camera zooms in and orbits 360 degrees around the thin parchment-cutout central figure, camera tilts up to an antique celestial diagram and armillary sphere in the sky revealing the astrological symbol, then seamlessly loops back to the original 2D card frame. Renaissance engraving aesthetic, warm candlelight shadows, vertical 9:16."
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
# CONECTOR GOOGLE DRIVE ULTRA-RÁPIDO (LISTAGEM INSTANTÂNEA + DOWNLOAD SOB DEMANDA)
# ==============================================================================
def extrair_id_drive(url: str) -> tuple[str | None, str]:
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
    drive_id, tipo = extrair_id_drive(url)
    if not drive_id:
        raise ValueError("Link do Google Drive inválido. Use um link de pasta (/folders/...) ou arquivo (/file/d/...).")

    extensoes_img = (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp")

    if tipo == "file":
        return [{"name": "Carta_Selecionada.tif", "id": drive_id, "local_path": None}]

    embed_url = f"https://drive.google.com/embeddedfolderview?id={drive_id}#list"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(embed_url, headers=headers, timeout=20)

    itens = []
    if resp.status_code == 200:
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
    if item.get("local_path") and Path(item["local_path"]).exists():
        return Path(item["local_path"])

    pasta_destino = PASTA_TEMP / "drive_sync"
    pasta_destino.mkdir(exist_ok=True)
    f_id = item["id"]
    destino_arquivo = pasta_destino / item["name"]

    if destino_arquivo.exists() and destino_arquivo.stat().st_size > 1000:
        return destino_arquivo

    url_dl = f"https://drive.google.com/uc?id={f_id}&export=download"
    caminho = gdown.download(url=url_dl, output=str(destino_arquivo), quiet=True, fuzzy=True)
    if caminho and os.path.exists(caminho):
        return Path(caminho)

    r = requests.get(url_dl, stream=True, timeout=30)
    if r.status_code == 200:
        with open(destino_arquivo, "wb") as f:
            for chunk in r.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
        return destino_arquivo

    raise RuntimeError("Não foi possível baixar esta carta. Verifique se a pasta do Drive está pública ('Qualquer pessoa com o link').")

# ==============================================================================
# SELETOR INTELIGENTE DE MODELOS GEMINI (COM FALLBACK AUTOMÁTICO)
# ==============================================================================
def diagnosticar_carta_ia(api_key: str, img_bytes: bytes, instrucao_usuario: str) -> dict:
    client = genai.Client(api_key=api_key)

    modelos_candidatos = [
        "gemini-3.0-flash",
        "gemini-3-flash-preview",
        "gemini-flash-latest",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ]

    try:
        for m in client.models.list():
            nome_m = getattr(m, "name", "").replace("models/", "")
            if "gemini" in nome_m and "flash" in nome_m and "vision" not in nome_m and "tts" not in nome_m:
                if nome_m not in modelos_candidatos:
                    modelos_candidatos.insert(1, nome_m)
    except Exception:
        pass

    ultimo_erro = None
    for modelo in modelos_candidatos:
        try:
            response = client.models.generate_content(
                model=modelo,
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
            dados = json.loads(response.text)
            dados["_modelo_usado"] = modelo
            return dados
        except Exception as e:
            ultimo_erro = e
            continue

    raise RuntimeError(f"Não foi possível conectar aos modelos Gemini desta chave. Detalhe: {ultimo_erro}")

def extrair_duracao_segundos(texto_usuario: str, padrao: int = 16) -> int:
    m = re.search(r"(\d{1,2})\s*(?:s|seg|segundos)", texto_usuario.lower())
    if m:
        val = int(m.group(1))
        return max(6, min(40, val))
    return padrao

# ==============================================================================
# MOTOR 2.5D COM ESTÉTICA DO DESIGN SYSTEM (PAPIRO ANTIGO, ESFERA ARMILAR & VELA)
# ==============================================================================
def separar_camadas_25d(img_card: Image.Image, W: int = 720, H: int = 1280):
    card_resized = img_card.convert("RGBA").resize((int(W * 0.82), int(H * 0.78)), Image.Resampling.LANCZOS)
    cw, ch = card_resized.size

    # Camada de Fundo: Ambiência quente de Papiro e Luz de Velas (#241107 / #845A35)
    bg_layer = img_card.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    bg_layer = bg_layer.filter(ImageFilter.GaussianBlur(radius=18))
    bg_layer = ImageEnhance.Brightness(bg_layer).enhance(0.36)
    # Aplica filtro sépia quente à luz de velas
    sepia_overlay = Image.new("RGB", (W, H), (46, 21, 9))
    bg_layer = Image.blend(bg_layer, sepia_overlay, alpha=0.32)

    # Camada Central: Recorte em Papiro Antigo (#E6C696) com filete duplo de gravura (#673F1D)
    mask_mid = Image.new("L", (cw, ch), 0)
    draw_m = ImageDraw.Draw(mask_mid)
    draw_m.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=22, fill=255)
    mask_mid = mask_mid.filter(ImageFilter.GaussianBlur(radius=2))

    mid_cutout = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    mid_cutout.paste(card_resized, (0, 0), mask_mid)
    draw_border = ImageDraw.Draw(mid_cutout)
    # Borda externa papiro e filete interno sépia (igual ao "Cartão em Branco à Luz de Velas.png")
    draw_border.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=22, outline=(228, 189, 133, 245), width=6)
    draw_border.rounded_rectangle((int(cw*0.095), int(ch*0.112), int(cw*0.905), int(ch*0.868)), radius=18, outline=(103, 63, 29, 220), width=2)

    # Primeiro Plano: Moldura da Carta
    fg_mask = Image.new("L", (cw, ch), 255)
    draw_fg = ImageDraw.Draw(fg_mask)
    draw_fg.rounded_rectangle((int(cw*0.12), int(ch*0.14), int(cw*0.88), int(ch*0.82)), radius=18, fill=0)
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
    espessura = int(7 * (1.0 - fator_largura)) + 2
    if espessura > 2:
        # Espessura lateral em tom de Papiro Antigo (#D5AD7A)
        borda_papiro = Image.new("RGBA", (nova_w, h), (213, 173, 122, 220))
        canvas.paste(borda_papiro, (offset_x + espessura, 2), img_rot)
    canvas.paste(img_rot, (offset_x, 0), img_rot)
    return canvas

def renderizar_video_nativo_gratuito(
    img_bytes: bytes,
    plano: dict,
    saida_raw: Path,
    barra_progresso,
    texto_status,
    duracao_s: int = 10,
    fps: int = 24
) -> bool:
    W, H = 720, 1280
    total_frames = duracao_s * fps
    img_pil = Image.open(io.BytesIO(img_bytes))
    card_full, bg_layer, mid_cutout, fg_layer = separar_camadas_25d(img_pil, W, H)
    cw, ch = card_full.size

    cor_p = (228, 189, 133) # Ouro/Pergaminho à Luz de Velas
    astro_txt = plano.get("astro_revelacao_ceu", "☉")
    simbolo = plano.get("simbolo_unicode", "✦")
    arcano_titulo = plano.get("arcano_nome", "ARCANO")

    rng = random.Random(42)
    estrelas = [(rng.randint(25, W-25), rng.randint(25, H-25), rng.randint(1, 3), rng.random()) for _ in range(130)]
    particulas = [
        {"x": rng.uniform(70, W-70), "y": rng.uniform(100, H-50), "vy": rng.uniform(2.8, 7.0), "r": rng.randint(2, 5), "fase": rng.uniform(0, 6.28)}
        for _ in range(60)
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

        # Fundo Noturno de Santuário à Luz de Velas (#170903)
        frame = Image.new("RGBA", (W, H), (23, 9, 3, 255))
        draw_sky = ImageDraw.Draw(frame)

        offset_y_cena = int(tilt_ceu * H * 0.88)
        for sx, sy, sr, sf in estrelas:
            brilho = int(150 + 100 * math.sin(f_idx * 0.2 + sf * 10))
            pos_y_estrela = sy - int((1.0 - tilt_ceu) * H * 0.6)
            if 0 <= pos_y_estrela < H:
                draw_sky.ellipse((sx-sr, pos_y_estrela-sr, sx+sr, pos_y_estrela+sr), fill=(230, 198, 150, brilho))

        # Diagrama Celestial & Esfera Armilar no Topo (Inspirado nas imagens do Design System)
        if tilt_ceu > 0.15:
            alpha_astro = int(min(1.0, (tilt_ceu - 0.15) / 0.65) * 255)
            cx_ceu, cy_ceu = W // 2, int(H * 0.36)
            # Anéis do Diagrama Celestial e Esfera Armilar
            for r_halo in [185, 145, 108]:
                draw_sky.ellipse(
                    (cx_ceu - r_halo, cy_ceu - r_halo, cx_ceu + r_halo, cy_ceu + r_halo),
                    outline=(213, 173, 122, int(alpha_astro * 0.55)),
                    width=2
                )
            # Eixos da Esfera Armilar
            draw_sky.line((cx_ceu - 210, cy_ceu, cx_ceu + 210, cy_ceu), fill=(184, 134, 59, int(alpha_astro * 0.5)), width=1)
            draw_sky.line((cx_ceu, cy_ceu - 210, cx_ceu, cy_ceu + 210), fill=(184, 134, 59, int(alpha_astro * 0.5)), width=1)
            # Anéis inclinados da Esfera Armilar
            draw_sky.arc((cx_ceu - 170, cy_ceu - 52, cx_ceu + 170, cy_ceu + 52), start=0, end=360, fill=(228, 189, 133, alpha_astro), width=3)
            draw_sky.ellipse((cx_ceu - 70, cy_ceu - 70, cx_ceu + 70, cy_ceu + 70), fill=(44, 22, 9, alpha_astro), outline=(228, 189, 133, alpha_astro), width=4)
            # Símbolo e Textos em Pergaminho Dourado
            draw_sky.text((cx_ceu, cy_ceu - 10), simbolo, fill=(248, 211, 163, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 118), astro_txt.upper(), fill=(228, 189, 133, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 150), arcano_titulo.upper(), fill=(213, 173, 122, alpha_astro), anchor="mm")

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
            c2d_layer = Image.new("RGBA", (W, H), (23, 9, 3, int(255 * mix_2d)))
            c2d_layer.paste(card_full, ((W - cw)//2, (H - ch)//2), card_full)
            frame = Image.alpha_composite(frame, c2d_layer)

        # Partículas de Luz de Velas (Tons de Ouro & Âmbar Quente)
        draw_p = ImageDraw.Draw(frame)
        for p in particulas:
            p["y"] -= p["vy"]
            if p["y"] < 0:
                p["y"] = H
            px = int(p["x"] + math.sin(f_idx * 0.12 + p["fase"]) * 14)
            py = int(p["y"])
            r = p["r"]
            draw_p.ellipse((px-r, py-r, px+r, py+r), fill=(cor_p[0], cor_p[1], cor_p[2], 215))

        proc.stdin.write(frame.convert("RGB").tobytes())

        if f_idx % 8 == 0 or f_idx == total_frames - 1:
            pct = int(10 + 75 * (f_idx / total_frames))
            barra_progresso.progress(pct)
            texto_status.info(f"🕯️ [Motor 2.5D Tarot Iniciático] Esculpindo papiro, luz de velas e esfera celestial ({f_idx+1}/{total_frames})...")

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

# ================= CABEÇALHO EDITORIAL DO DESIGN SYSTEM =================

st.markdown("""
<div class="iniciatico-header">
    <div class="subtitle-top">✦ ORÁCULO & ESTÚDIO DE ANIMAÇÃO HERMÉTICA ✦</div>
    <h1>Tarot Iniciático Studio 2.5D</h1>
    <div class="iniciatico-divider">◇</div>
    <div class="subtitle-bottom">Os 22 Arcanos Maiores em Papiro Antigo, Paralaxe 2.5D e Luz de Velas</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🕯️ 1. Santuário & Chave")
    chave_atual = carregar_chave_salva()
    nova_chave = st.text_input(
        "Chave Gratuita Google Gemini (AIza...):",
        value=chave_atual,
        type="password",
        help="A chave gratuita do Google AI Studio analisa a carta com Gemini 3.0 Flash sem custo."
    )
    if nova_chave != chave_atual and nova_chave:
        salvar_chave(nova_chave)
        st.success("Chave guardada no Santuário!")

    st.markdown("[🔑 Obter Chave Gratuita no Google AI Studio](https://aistudio.google.com/apikey)")
    st.divider()

    st.markdown("### ⚜️ Motor de Renderização")
    motor_escolhido = st.radio(
        "Selecione o Motor Alquímico:",
        [
            "🆓 Motor 2.5D Papiro & Luz de Velas (100% Gratuito)",
            "💎 Google Veo 2.0 Cloud (Requer API com Faturamento)"
        ],
        index=0
    )

    st.divider()
    st.markdown("### 📜 Status do Sistema")
    if nova_chave:
        st.success("✅ Oráculo IA Conectado (Gemini 3.0 Flash)")
    else:
        st.warning("⚠️ Insira sua Chave Gratuita acima")

    if verificar_ffmpeg():
        st.success("✅ FFmpeg Ativo (Loop + Trilha Sonora)")
    else:
        st.warning("⚠️ FFmpeg não detectado")

if "plano_ia" not in st.session_state:
    st.session_state.plano_ia = None
if "img_bytes" not in st.session_state:
    st.session_state.img_bytes = None
if "nome_arquivo" not in st.session_state:
    st.session_state.nome_arquivo = "arcano_tarot"
if "arquivos_drive" not in st.session_state:
    st.session_state.arquivos_drive = []
if "duracao_total" not in st.session_state:
    st.session_state.duracao_total = 20

col_esq, col_dir = st.columns([1, 1.2], gap="large")

with col_esq:
    st.subheader("📜 Passo 1: A Carta e o Ritual")
    metodo_entrada = st.radio(
        "Origem da lâmina do Tarô:",
        ["📂 Enviar arquivo do dispositivo (.tif, .png, .jpg)", "☁️ Colar Link do Google Drive (Pasta ou Arquivo)"],
        horizontal=False
    )

    if "Enviar arquivo" in metodo_entrada:
        upload = st.file_uploader("Deposite a imagem da carta sobre a mesa:", type=["tif", "tiff", "png", "jpg", "jpeg", "webp"])
        if upload:
            imagem_carregada = Image.open(upload)
            st.session_state.nome_arquivo = Path(upload.name).stem
            st.session_state.img_bytes = converter_imagem_para_png_bytes(imagem_carregada)
    else:
        url_drive = st.text_input("Link da pasta ou arquivo do Google Drive:")
        if st.button("🔄 Sincronizar Lâminas do Google Drive"):
            if not url_drive:
                st.error("Cole um link válido do Google Drive.")
            else:
                with st.spinner("Consultando acervo de lâminas no Google Drive..."):
                    try:
                        encontrados = listar_arquivos_pasta_drive(url_drive)
                        if encontrados:
                            st.session_state.arquivos_drive = encontrados
                            st.success(f"{len(encontrados)} lâmina(s) localizada(s)!")
                        else:
                            st.error("Nenhuma imagem encontrada. Verifique se a pasta está pública ('Qualquer pessoa com o link').")
                    except Exception as err_dl:
                        st.error(f"Erro ao acessar link do Drive: {err_dl}")

        if st.session_state.arquivos_drive:
            opcoes = {item["name"]: item for item in st.session_state.arquivos_drive}
            escolhido_nome = st.selectbox("Escolha a lâmina do Arcano:", list(opcoes.keys()))
            item_escolhido = opcoes[escolhido_nome]
            with st.spinner(f"Preparando papiro de {escolhido_nome}..."):
                try:
                    caminho_escolhido = baixar_carta_individual_drive(item_escolhido)
                    imagem_carregada = Image.open(caminho_escolhido)
                    st.session_state.nome_arquivo = Path(escolhido_nome).stem
                    st.session_state.img_bytes = converter_imagem_para_png_bytes(imagem_carregada)
                except Exception as err_card:
                    st.error(f"Erro ao carregar a carta selecionada: {err_card}")

    if st.session_state.img_bytes:
        st.image(st.session_state.img_bytes, caption=f"Lâmina Selecionada: {st.session_state.nome_arquivo}", use_container_width=True)

    ideia_custom = st.text_area(
        "✒️ Diretriz para o Vídeo (ou deixe em branco para seguir o ritual 2.5D padrão):",
        placeholder="Ex: Quero um vídeo de 20s, no estilo do vídeo referência, com atmosfera de papiro antigo e luz de velas.",
        height=90
    )

    if st.button("🔍 Analisar Arcano e Estruturar Camadas 2.5D", type="primary", use_container_width=True):
        if not nova_chave:
            st.error("⚠️ Insira sua Chave Gratuita do Gemini na barra lateral esquerda primeiro.")
        elif not st.session_state.img_bytes:
            st.error("⚠️ Selecione ou envie uma carta primeiro.")
        else:
            with st.spinner("🕯️ O Agente está decifrando o simbolismo do Arcano e mapeando os planos de profundidade..."):
                try:
                    pedido = ideia_custom.strip() or "Construir vídeo de 20s em estilo 2.5D cutout parallax com estética de papiro antigo, luz de velas, órbita 360 e diagrama celestial no céu."
                    st.session_state.duracao_total = extrair_duracao_segundos(pedido, padrao=20)
                    st.session_state.plano_ia = diagnosticar_carta_ia(nova_chave, st.session_state.img_bytes, pedido)
                except Exception as e:
                    st.error(f"Erro ao analisar carta: {e}")

with col_dir:
    st.subheader("🎬 Passo 2: Alquimia de Cena & Renderização")

    if not st.session_state.plano_ia:
        st.info("👈 Selecione uma lâmina ao lado e clique em **Analisar Arcano** para revelar os planos de profundidade e o diagrama celestial.")
    else:
        plano = st.session_state.plano_ia
        modelo_usado = plano.get("_modelo_usado", "gemini-3.0-flash")
        st.success(f"✦ **Arcano Decifrado ({modelo_usado}):** {plano.get('arcano_nome', 'Arcano Maior')}")

        with st.expander("📐 Camadas em Papiro 2.5D & Simbolismo (Editável)", expanded=True):
            camadas = plano.get("camadas_z_space", {})
            c1 = st.text_input("1º Plano (Elementos Frontais):", value=camadas.get("primeiro_plano", ""))
            c2 = st.text_input("Plano Central (Recorte 2.5D em Giro 360°):", value=camadas.get("plano_medio", ""))
            c3 = st.text_input("Plano de Fundo (Cenário Expandido):", value=camadas.get("plano_fundo", ""))
            particulas = st.text_input("🕯️ Partículas & Luz de Velas:", value=plano.get("particulas_e_fisica", ""))
            astro = st.text_input("🌌 Revelação no Diagrama Celestial (Tilt-up):", value=plano.get("astro_revelacao_ceu", ""))
            simbolo_uni = st.text_input("✡️ Glifo / Símbolo Hermético no Topo:", value=plano.get("simbolo_unicode", "✦"))

        with st.expander("⏱️ Tempo de Ritual, Música & Loop Infinito", expanded=True):
            duracao_escolhida = st.slider("Duração total do vídeo final (segundos):", min_value=8, max_value=30, value=int(st.session_state.duracao_total), step=2)
            audio_upload = st.file_uploader("Adicionar trilha sonora ritualística (.mp3 / .wav):", type=["mp3", "wav", "m4a"])
            aplicar_loop_reverso = st.checkbox("Ciclo Hermético Perfeito (Como Acima, Assim Abaixo: vai ao céu e retorna suavemente à carta 2D)", value=True)

        plano["astro_revelacao_ceu"] = astro
        plano["simbolo_unicode"] = simbolo_uni

        prompt_tecnico = st.text_area(
            "Roteiro Técnico de Renderização:",
            value=(
                f"{plano.get('veo_prompt_en', '')} "
                f"Foreground: {c1}. Midground: {c2}. Background: {c3}. "
                f"Particles: {particulas}. Sky reveal: {astro}."
            ),
            height=95
        )

        if st.button("🚀 FORJAR VÍDEO DO ARCANO AGORA", type="primary", use_container_width=True):
            barra = st.progress(5)
            status_txt = st.empty()

            raw_mp4 = PASTA_TEMP / f"raw_{st.session_state.nome_arquivo}.mp4"
            final_mp4 = PASTA_TEMP / f"Video_Pronto_{st.session_state.nome_arquivo}.mp4"

            caminho_audio_temp = None
            if audio_upload:
                caminho_audio_temp = PASTA_TEMP / audio_upload.name
                caminho_audio_temp.write_bytes(audio_upload.getvalue())

            try:
                duracao_ida = max(4, duracao_escolhida // 2) if aplicar_loop_reverso else duracao_escolhida

                if "100% Gratuito" in motor_escolhido:
                    ok = renderizar_video_nativo_gratuito(
                        st.session_state.img_bytes,
                        plano,
                        raw_mp4,
                        barra,
                        status_txt,
                        duracao_s=duracao_ida
                    )
                else:
                    ok = renderizar_video_veo(nova_chave, st.session_state.img_bytes, prompt_tecnico, raw_mp4, barra, status_txt)

                if ok:
                    barra.progress(90)
                    status_txt.info(f"🎞️ Selando ciclo reverso ({duracao_escolhida}s) e mixagem de áudio via FFmpeg...")
                    pos_producao_loop_e_audio(raw_mp4, caminho_audio_temp, final_mp4, aplicar_loop_reverso)
                    barra.progress(100)
                    status_txt.success(f"✦ Vídeo Concluído ({duracao_escolhida}s)! Assista abaixo ou baixe o arquivo final.")

                    video_bytes = final_mp4.read_bytes()
                    st.video(video_bytes)
                    st.download_button(
                        label="⬇️ BAIXAR VÍDEO DO ARCANO (.MP4)",
                        data=video_bytes,
                        file_name=f"Tarot_Iniciatico_2.5D_{st.session_state.nome_arquivo}.mp4",
                        mime="video/mp4",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    status_txt.error("❌ Não foi possível concluir a geração do vídeo.")
            except Exception as err:
                status_txt.error(f"❌ Erro durante a renderização: {err}")

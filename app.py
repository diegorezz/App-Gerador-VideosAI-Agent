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
# DESIGN SYSTEM SUAVIZADO: LEITURA LIMPA (INTER / SANS) + DETALHES CLÁSSICOS
# ==============================================================================
DESIGN_SYSTEM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Inter:wght@400;500;600&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');

:root {
    --bg-candle-dark: #160B06;
    --bg-mahogany: #221109;
    --parchment-light: #F4E6D2;
    --parchment-mid: #E5CFAF;
    --parchment-aged: #C8A97E;
    --sepia-line: #7A5230;
    --hermetic-crimson: #8B261D;
    --candle-gold: #C8923B;
}

/* Fundo Geral: Suave e confortável para leitura */
.stApp {
    background: radial-gradient(circle at 50% 10%, #2A140A 0%, #160B06 60%, #0E0603 100%) !important;
    color: var(--parchment-light) !important;
}

/* Barra Lateral */
section[data-testid="stSidebar"] {
    background: #1A0C06 !important;
    border-right: 1px solid #4A2E18 !important;
}

/* Títulos com Cinzel suave */
h1, h2, h3 {
    font-family: 'Cinzel', Georgia, serif !important;
    color: var(--parchment-light) !important;
    letter-spacing: 0.03em !important;
    font-weight: 600 !important;
}

/* Textos corridos e labels com Inter — SEM afetar spans de ícones */
p, label, li, input, textarea {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

p, label {
    font-size: 0.95rem !important;
    line-height: 1.55 !important;
    color: var(--parchment-mid) !important;
}

/* CORREÇÃO 1: Força a fonte oficial de ícones Material Symbols em todos os ícones do Streamlit (evita 'keyboard_double' e 'uploadUpload') */
span[data-testid="stIconMaterial"],
.material-symbols-rounded,
[data-testid="stSidebarCollapseButton"] span,
[data-testid="collapsedControl"] span,
button[kind="header"] span,
button[kind="headerNoPadding"] span {
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 22px !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: 'liga' !important;
    font-feature-settings: 'liga' !important;
    -webkit-font-smoothing: antialiased !important;
    max-width: 26px !important;
    overflow: hidden !important;
}

/* Oculta o ícone duplicado dentro do botão de Upload para nunca sobrepor 'uploadUpload' */
section[data-testid="stFileUploaderDropzone"] button span[data-testid="stIconMaterial"] {
    display: none !important;
}

/* CORREÇÃO 2: Remove o texto 'Press Ctrl+Enter to apply' que sobrepunha o texto digitado na caixa de diretriz */
div[data-testid="InputInstructions"] {
    display: none !important;
    visibility: hidden !important;
}

/* Dá espaçamento interno confortável na caixa de texto para não colar na barra de rolagem */
.stTextArea textarea {
    padding: 12px 16px 20px 14px !important;
    line-height: 1.5 !important;
}

/* CORREÇÃO 3: Estilo do Aviso Minimizável + Ícone '?' Transparente com Tooltip Explicativo */
.oracle-notice-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(200, 146, 59, 0.08);
    border: 1px solid rgba(200, 146, 59, 0.28);
    border-radius: 6px;
    padding: 8px 14px;
    margin-bottom: 10px;
    font-size: 0.88rem;
    color: var(--parchment-mid);
}

.oracle-help-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgba(244, 230, 210, 0.08);
    border: 1px solid rgba(244, 230, 210, 0.35);
    color: rgba(244, 230, 210, 0.75);
    font-size: 0.75rem;
    font-weight: 600;
    margin-left: 8px;
    cursor: help;
    position: relative;
    transition: all 0.2s ease;
}

.oracle-help-badge:hover {
    background: rgba(200, 146, 59, 0.25);
    color: #FFF;
    border-color: var(--candle-gold);
}

.oracle-help-badge .tooltip-box {
    visibility: hidden;
    opacity: 0;
    width: 310px;
    background-color: #1A0C06;
    color: #F4E6D2;
    text-align: left;
    border: 1px solid #7A5230;
    border-radius: 6px;
    padding: 10px 12px;
    position: absolute;
    z-index: 9999;
    bottom: 135%;
    right: 0;
    font-size: 0.8rem;
    font-weight: 400;
    line-height: 1.45;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.85);
    transition: opacity 0.2s ease;
    pointer-events: none;
}

.oracle-help-badge:hover .tooltip-box {
    visibility: visible;
    opacity: 1;
}

/* Cabeçalho Editorial Elegante e Compacto */
.iniciatico-header {
    background: linear-gradient(135deg, rgba(42, 20, 10, 0.9) 0%, rgba(24, 11, 5, 0.95) 100%);
    border: 1px solid var(--sepia-line);
    border-radius: 8px;
    padding: 16px 24px;
    margin-bottom: 20px;
    text-align: center;
}

.iniciatico-header .subtitle-top {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    color: var(--candle-gold);
    text-transform: uppercase;
    margin-bottom: 4px;
}

.iniciatico-header h1 {
    font-size: 1.85rem !important;
    margin: 0 !important;
    color: var(--parchment-light) !important;
}

.iniciatico-header .subtitle-bottom {
    font-family: 'Inter', sans-serif;
    font-size: 0.92rem;
    color: var(--parchment-aged);
    margin-top: 6px;
}

/* Botões Primários */
.stButton > button[kind="primary"], .stDownloadButton > button {
    background: linear-gradient(180deg, #9E2E22 0%, #731E15 100%) !important;
    color: #FFF6E9 !important;
    border: 1px solid #D5A458 !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.02em !important;
    padding: 0.55rem 1.1rem !important;
    transition: all 0.2s ease !important;
}

.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
    background: linear-gradient(180deg, #B5382A 0%, #872419 100%) !important;
    border-color: #F3C677 !important;
}

/* Botões Secundários (Seleção de Miniaturas) */
.stButton > button[kind="secondary"] {
    background: #26130A !important;
    color: var(--parchment-light) !important;
    border: 1px solid #5C3A20 !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}

.stButton > button[kind="secondary"]:hover {
    border-color: var(--candle-gold) !important;
    background: #331A0E !important;
}

/* Inputs e Textareas limpos */
.stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div {
    background-color: #1E0E07 !important;
    color: #F4E6D2 !important;
    border: 1px solid #5C3A20 !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.94rem !important;
}

/* Cartões de Miniatura na Galeria */
div[data-testid="stImage"] img {
    border: 1px solid #7A5230;
    border-radius: 6px;
}
</style>
"""
st.markdown(DESIGN_SYSTEM_CSS, unsafe_allow_html=True)

PASTA_TEMP = Path("./workspace_temp")
PASTA_TEMP.mkdir(exist_ok=True)

# Catálogo Esotérico Completo dos 22 Arcanos Maiores (Serve para legendar a galeria e como Oráculo Local caso a API Key falhe!)
CATALOGO_ARCANOS = [
    {"num": "0", "nome": "O Louco (Le Mat)", "simbolo": "☉", "astro": "Urano / Ar Primordial", "fg": "Cão em salto, flores do campo e cajado de peregrino", "mid": "O Viajante com trouxa às costas caminhando rumo ao abismo", "bg": "Montanhas douradas e horizonte aberto em papiro"},
    {"num": "I", "nome": "O Mago (Le Bateleur)", "simbolo": "☿", "astro": "Mercúrio", "fg": "Mesa com taça, moedas, espada e bastão alquímico", "mid": "O Mago com chapéu de lemniscata (infinito) erguendo a varinha", "bg": "Jardim hermético sob céu dourado"},
    {"num": "II", "nome": "A Sacerdotisa (La Papesse)", "simbolo": "☽", "astro": "Lua", "fg": "Livro aberto dos mistérios e dobras do manto sagrado", "mid": "A Alta Sacerdotisa coroada sentada no templo", "bg": "Colunas do templo e véu bordado"},
    {"num": "III", "nome": "A Imperatriz (L'Impératrice)", "simbolo": "♀", "astro": "Vênus", "fg": "Escudo com a águia imperial e cetro do mundo", "mid": "A Imperatriz alada em seu trono real", "bg": "Campo fértil sob luz solar dourada"},
    {"num": "IV", "nome": "O Imperador (L'Empereur)", "simbolo": "♈", "astro": "Áries / Júpiter", "fg": "Escudo da águia, cetro e pedra cúbica do trono", "mid": "O Imperador de perfil com pernas cruzadas em quatro", "bg": "Montanhas rochosas e domínio imperial"},
    {"num": "V", "nome": "O Hierofante (Le Pape)", "simbolo": "♉", "astro": "Touro", "fg": "Dois discípulos ajoelhados no primeiro plano", "mid": "O Sumo Sacerdote abençoando com a cruz tríplice", "bg": "Pilares góticos do santuário"},
    {"num": "VI", "nome": "Os Enamorados (L'Amoureux)", "simbolo": "♊", "astro": "Gêmeos", "fg": "O jovem entre os dois caminhos da virtude e da paixão", "mid": "As três figuras no plano terreno da escolha", "bg": "O Anjo Cupido irradiando luz solar no topo"},
    {"num": "VII", "nome": "O Carro (Le Chariot)", "simbolo": "♋", "astro": "Câncer", "fg": "Dois cavalos (azul e vermelho) puxando a carruagem", "mid": "O Príncipe Triunfante sob o dossel estrelado", "bg": "Campos e muralhas da cidade ao fundo"},
    {"num": "VIII", "nome": "A Justiça (La Justice)", "simbolo": "♎", "astro": "Libra", "fg": "Balança do equilíbrio perfeito e espada erguida", "mid": "A figura severa da Justiça entronizada", "bg": "Trono simétrico e véu dourado"},
    {"num": "IX", "nome": "O Eremita (L'Hermite)", "simbolo": "♍", "astro": "Virgem / Saturno", "fg": "Cajado da prudência tocando o solo pedregoso", "mid": "O Sábio Ancião erguendo a lanterna da verdade", "bg": "Deserto noturno silencioso em papiro"},
    {"num": "X", "nome": "A Roda da Fortuna (La Roue de Fortune)", "simbolo": "♃", "astro": "Júpiter", "fg": "Criaturas subindo e descendo no giro do destino", "mid": "A Grande Roda Cósmica sobre seu eixo", "bg": "A Esfinge coroada com espada no topo"},
    {"num": "XI", "nome": "A Força (La Force)", "simbolo": "♌", "astro": "Leão", "fg": "O Leão vermelho com as fauces abertas", "mid": "A Dama com chapéu do infinito dominando a fera suavemente", "bg": "Planície aberta sob o céu"},
    {"num": "XII", "nome": "O Enforcado (Le Pendu)", "simbolo": "♆", "astro": "Netuno / Água", "fg": "Raízes e gramíneas brotando na base das árvores", "mid": "O Iniciado suspenso pelo pé em meditação profunda", "bg": "Duas árvores podadas sustentando a trave"},
    {"num": "XIII", "nome": "Arcano Sem Nome / A Morte (XIII)", "simbolo": "♏", "astro": "Escorpião", "fg": "Coroas, cabeças e plantas brotando do solo", "mid": "O Ceifador com sua grande foice da transmutação", "bg": "Terra negra fértil sob o horizonte"},
    {"num": "XIV", "nome": "A Temperança (Tempérance)", "simbolo": "♐", "astro": "Sagitário", "fg": "Flores do campo e fluxo magnético entre duas ânforas", "mid": "O Anjo Alquímico transvasando a essência da vida", "bg": "Paisagem serena com aura solar"},
    {"num": "XV", "nome": "O Diabo (Le Diable)", "simbolo": "♄", "astro": "Capricórnio / Saturno", "fg": "Duas figuras acorrentadas na base do pedestal", "mid": "Baphomet / O Diabo alado com tocha sobre o altar", "bg": "Caverna escura com brasas ardentes"},
    {"num": "XVI", "nome": "A Torre (La Maison Dieu)", "simbolo": "♂", "astro": "Marte", "fg": "Duas figuras caindo entre pedras e centelhas coloridas", "mid": "A Torre de Babel com sua coroa sendo atingida", "bg": "Fogo celeste descendo do céu"},
    {"num": "XVII", "nome": "A Estrela (L'Étoile)", "simbolo": "♒", "astro": "Aquário", "fg": "Duas ânforas derramando água viva no rio e na terra", "mid": "A Jovem ajoelhada sob o firmamento", "bg": "A Grande Estrela de oito pontas e sete estrelas menores"},
    {"num": "XVIII", "nome": "A Lua (La Lune)", "simbolo": "♓", "astro": "Peixes / Lua", "fg": "O Lagostim emergindo das águas primordiais e dois cães", "mid": "Caminho sinuoso entre os dois guardiões", "bg": "Duas torres ao longe e a Lua irradiando gotas de orvalho"},
    {"num": "XIX", "nome": "O Sol (Le Soleil)", "simbolo": "☉", "astro": "Sol", "fg": "Dois gêmeos de mãos dadas no jardim murado", "mid": "Muro alquímico e gotas de ouro solar", "bg": "O Grande Sol radiante de rosto humano no céu"},
    {"num": "XX", "nome": "O Julgamento (Le Jugement)", "simbolo": "♇", "astro": "Plutão / Fogo Renovador", "fg": "Três figuras emergindo do túmulo em oração", "mid": "Ondas sonoras e nuvens celestiais", "bg": "O Anjo tocando a trombeta do despertar"},
    {"num": "XXI", "nome": "O Mundo (Le Monde)", "simbolo": "♄", "astro": "Saturno / O Cosmos", "fg": "O Touro e o Leão nos cantos inferiores da carta", "mid": "A Figura Dançante dentro da Guirlanda Oval", "bg": "O Anjo e a Águia nos cantos superiores do firmamento"},
]

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
    "primeiro_plano": "Elementos na frente da cena",
    "plano_medio": "Figura central / arquétipo em recorte 2.5D",
    "plano_fundo": "Paisagem renascentista em papiro antigo expandida ao fundo"
  },
  "particulas_e_fisica": "Efeitos ativos (ex: brasas de luz de vela, poeira de ouro hermético, centelhas solares)",
  "astro_revelacao_ceu": "Planeta, esfera armilar, diagrama celestial ou signo revelado quando a câmera sobe para o céu",
  "veo_prompt_en": "2.5D layered antique parchment cutout parallax animation of the provided Tarot card. Start with the flat vintage woodcut card on aged papyrus, deconstruct into 3D depth layers, candlelight golden particles floating, camera zooms in and orbits 360 degrees around the thin parchment-cutout central figure, camera tilts up to an antique celestial diagram and armillary sphere in the sky revealing the astrological symbol, then seamlessly loops back to the original 2D card frame. Renaissance engraving aesthetic, warm candlelight shadows, vertical 9:16."
}
"""

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
# CONECTOR GOOGLE DRIVE SEM GDOWN.FUZZY (CORRIGE O ERRO DE SELEÇÃO + MINIATURAS)
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
        return [{
            "name": "Carta_Selecionada.tif",
            "label": "Carta Individual do Drive",
            "id": drive_id,
            "thumb_url": f"https://drive.google.com/thumbnail?id={drive_id}&sz=w320",
            "arcano_idx": 0
        }]

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
                itens.append({"name": f_name, "id": f_id})

    itens.sort(key=lambda x: x["name"])

    # Associa rótulos amigáveis dos 22 Arcanos caso a pasta tenha as 22 lâminas em ordem
    for idx, item in enumerate(itens):
        item["thumb_url"] = f"https://drive.google.com/thumbnail?id={item['id']}&sz=w320"
        item["arcano_idx"] = idx if idx < len(CATALOGO_ARCANOS) else 0
        if len(itens) == 22 and idx < 22:
            arc = CATALOGO_ARCANOS[idx]
            item["label"] = f"[{arc['num']}] {arc['nome']} — ({item['name']})"
        else:
            item["label"] = item["name"]

    return itens

@st.cache_data(show_spinner=False)
def baixar_bytes_carta_drive(file_id: str, file_name: str) -> bytes:
    """
    Baixa a imagem diretamente via HTTP Session do Google Drive (sem usar o argumento 'fuzzy'
    do gdown que causava erro em algumas versões) e já retorna os bytes convertidos em PNG!
    """
    pasta_destino = PASTA_TEMP / "drive_cache"
    pasta_destino.mkdir(exist_ok=True)
    caminho_png_cache = pasta_destino / f"{file_id}.png"

    if caminho_png_cache.exists() and caminho_png_cache.stat().st_size > 1000:
        return caminho_png_cache.read_bytes()

    sess = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Tentativa 1: Download do arquivo original via Google Drive UC endpoint
    url_uc = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = sess.get(url_uc, headers=headers, stream=True, timeout=30)

    # Se o Drive pedir token de confirmação para arquivos maiores
    for k, v in resp.cookies.items():
        if k.startswith("download_warning"):
            resp = sess.get(f"{url_uc}&confirm={v}", headers=headers, stream=True, timeout=30)
            break

    raw_bytes = resp.content

    # Tentativa 2 (Fallback ultra-rápido): Se o arquivo .tif falhar ou vier HTML, pega a imagem em alta resolução renderizada pelo servidor do Drive
    try:
        img = Image.open(io.BytesIO(raw_bytes))
    except Exception:
        url_hi_res = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
        resp_thumb = sess.get(url_hi_res, headers=headers, timeout=25)
        img = Image.open(io.BytesIO(resp_thumb.content))

    png_bytes = converter_imagem_para_png_bytes(img)
    caminho_png_cache.write_bytes(png_bytes)
    return png_bytes

# ==============================================================================
# DIAGNÓSTICO IA + FALLBACK LOCAL INTELIGENTE (NUNCA TRAVA MESMO SE A CHAVE VAZAR)
# ==============================================================================
def gerar_plano_oraculo_local(arcano_idx: int, duracao_s: int = 20) -> dict:
    """Gera o plano de camadas 2.5D usando o banco de dados interno dos 22 Arcanos."""
    arc = CATALOGO_ARCANOS[arcano_idx % len(CATALOGO_ARCANOS)]
    return {
        "arcano_nome": f"Arcano {arc['num']} — {arc['nome']}",
        "simbolo_unicode": arc["simbolo"],
        "cor_particula_rgb": [228, 189, 133],
        "duracao_sugerida_segundos": duracao_s,
        "camadas_z_space": {
            "primeiro_plano": arc["fg"],
            "plano_medio": arc["mid"],
            "plano_fundo": arc["bg"]
        },
        "particulas_e_fisica": "Brasas douradas à luz de velas, poeira de papiro antigo e centelhas herméticas",
        "astro_revelacao_ceu": arc["astro"],
        "veo_prompt_en": (
            f"2.5D layered antique parchment cutout parallax animation of Tarot card {arc['nome']}. "
            f"Foreground: {arc['fg']}. Midground: {arc['mid']}. Background: {arc['bg']}. "
            f"Camera zooms in and orbits 360 degrees around the cutout figure, then tilts up to an antique celestial diagram revealing {arc['astro']}."
        ),
        "_modelo_usado": "Oráculo Interno Iniciático (100% Gratuito / Sem Chave)"
    }

def diagnosticar_carta_ia(api_key: str, img_bytes: bytes, instrucao_usuario: str, arcano_idx: int = 0) -> dict:
    # Se o usuário não colocou chave, usa direto o Oráculo Interno Gratuito
    if not api_key or len(api_key.strip()) < 10:
        return gerar_plano_oraculo_local(arcano_idx)

    client = genai.Client(api_key=api_key.strip())
    modelos_candidatos = [
        "gemini-3.0-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    ]

    try:
        for m in client.models.list():
            nome_m = getattr(m, "name", "").replace("models/", "")
            if "gemini" in nome_m and "flash" in nome_m and "vision" not in nome_m and "tts" not in nome_m:
                if nome_m not in modelos_candidatos:
                    modelos_candidatos.insert(0, nome_m)
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
            ultimo_erro = str(e)
            # Se a chave foi bloqueada por vazamento (403 leaked) ou inválida, interrompe na hora e ativa o Oráculo Local!
            if "leaked" in ultimo_erro.lower() or "403" in ultimo_erro or "api_key_invalid" in ultimo_erro.lower():
                plano_local = gerar_plano_oraculo_local(arcano_idx)
                plano_local["_aviso_chave"] = (
                    "⚠️ Sua chave da API do Google foi bloqueada pelo Google por ter aparecido publicamente "
                    "('Your API key was reported as leaked'). Mas não se preocupe: o **Oráculo Interno Gratuito** "
                    "assumiu automaticamente e já estruturou sua carta! (Para usar o Gemini novamente, crie uma chave nova em aistudio.google.com/apikey)."
                )
                return plano_local
            continue

    # Se qualquer outro erro ocorrer, também entrega o resultado via Oráculo Local para nunca travar o usuário
    plano_fallback = gerar_plano_oraculo_local(arcano_idx)
    plano_fallback["_aviso_chave"] = f"ℹ️ Usando Oráculo Interno Gratuito (Detalhe da API: {ultimo_erro})"
    return plano_fallback

def extrair_duracao_segundos(texto_usuario: str, padrao: int = 20) -> int:
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

    bg_layer = img_card.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    bg_layer = bg_layer.filter(ImageFilter.GaussianBlur(radius=18))
    bg_layer = ImageEnhance.Brightness(bg_layer).enhance(0.36)
    sepia_overlay = Image.new("RGB", (W, H), (46, 21, 9))
    bg_layer = Image.blend(bg_layer, sepia_overlay, alpha=0.32)

    mask_mid = Image.new("L", (cw, ch), 0)
    draw_m = ImageDraw.Draw(mask_mid)
    draw_m.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=22, fill=255)
    mask_mid = mask_mid.filter(ImageFilter.GaussianBlur(radius=2))

    mid_cutout = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    mid_cutout.paste(card_resized, (0, 0), mask_mid)
    draw_border = ImageDraw.Draw(mid_cutout)
    draw_border.rounded_rectangle((int(cw*0.08), int(ch*0.10), int(cw*0.92), int(ch*0.88)), radius=22, outline=(228, 189, 133, 245), width=6)
    draw_border.rounded_rectangle((int(cw*0.095), int(ch*0.112), int(cw*0.905), int(ch*0.868)), radius=18, outline=(103, 63, 29, 220), width=2)

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

    cor_p = (228, 189, 133)
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

        frame = Image.new("RGBA", (W, H), (23, 9, 3, 255))
        draw_sky = ImageDraw.Draw(frame)

        offset_y_cena = int(tilt_ceu * H * 0.88)
        for sx, sy, sr, sf in estrelas:
            brilho = int(150 + 100 * math.sin(f_idx * 0.2 + sf * 10))
            pos_y_estrela = sy - int((1.0 - tilt_ceu) * H * 0.6)
            if 0 <= pos_y_estrela < H:
                draw_sky.ellipse((sx-sr, pos_y_estrela-sr, sx+sr, pos_y_estrela+sr), fill=(230, 198, 150, brilho))

        if tilt_ceu > 0.15:
            alpha_astro = int(min(1.0, (tilt_ceu - 0.15) / 0.65) * 255)
            cx_ceu, cy_ceu = W // 2, int(H * 0.36)
            for r_halo in [185, 145, 108]:
                draw_sky.ellipse(
                    (cx_ceu - r_halo, cy_ceu - r_halo, cx_ceu + r_halo, cy_ceu + r_halo),
                    outline=(213, 173, 122, int(alpha_astro * 0.55)),
                    width=2
                )
            draw_sky.line((cx_ceu - 210, cy_ceu, cx_ceu + 210, cy_ceu), fill=(184, 134, 59, int(alpha_astro * 0.5)), width=1)
            draw_sky.line((cx_ceu, cy_ceu - 210, cx_ceu, cy_ceu + 210), fill=(184, 134, 59, int(alpha_astro * 0.5)), width=1)
            draw_sky.arc((cx_ceu - 170, cy_ceu - 52, cx_ceu + 170, cy_ceu + 52), start=0, end=360, fill=(228, 189, 133, alpha_astro), width=3)
            draw_sky.ellipse((cx_ceu - 70, cy_ceu - 70, cx_ceu + 70, cy_ceu + 70), fill=(44, 22, 9, alpha_astro), outline=(228, 189, 133, alpha_astro), width=4)
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
            texto_status.info(f"🕯️ Renderizando quadro {f_idx+1}/{total_frames} (Camadas em Papiro, Giro 3D e Esfera Armilar)...")

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

# ================= CABEÇALHO EDITORIAL SUAVIZADO =================

st.markdown("""
<div class="iniciatico-header">
    <div class="subtitle-top">✦ ORÁCULO & ESTÚDIO DE ANIMAÇÃO HERMÉTICA ✦</div>
    <h1>Tarot Iniciático Studio 2.5D</h1>
    <div class="subtitle-bottom">Os 22 Arcanos Maiores em Papiro Antigo, Paralaxe 2.5D e Luz de Velas</div>
</div>
""", unsafe_allow_html=True)

if "api_key_mem" not in st.session_state:
    st.session_state.api_key_mem = os.environ.get("GEMINI_API_KEY", "")

with st.sidebar:
    st.markdown("### 🕯️ 1. Configuração")
    nova_chave = st.text_input(
        "Chave Google Gemini (Opcional):",
        value=st.session_state.api_key_mem,
        type="password",
        placeholder="Cole sua nova chave AIza... (ou deixe vazio)",
        help="O aplicativo já possui o Oráculo Interno dos 22 Arcanos integrado! Mesmo sem chave (ou se sua chave anterior foi bloqueada), ele funciona 100% gratuito."
    )
    st.session_state.api_key_mem = nova_chave.strip()

    st.markdown("[🔑 Gerar Nova Chave no Google AI Studio](https://aistudio.google.com/apikey)")
    st.caption("💡 *Dica: Nunca cole sua chave em prints públicos ou códigos do GitHub, pois o Google bloqueia chaves expostas automaticamente.*")
    st.divider()

    st.markdown("### ⚜️ Motor de Renderização")
    motor_escolhido = st.radio(
        "Selecione o Motor:",
        [
            "🆓 Motor 2.5D Papiro & Luz de Velas (100% Gratuito)",
            "💎 Google Veo 2.0 Cloud (Requer API Paga)"
        ],
        index=0
    )

    st.divider()
    st.markdown("### 📜 Status do Sistema")
    if nova_chave:
        st.success("✅ Chave Gemini Inserida + Oráculo Interno Ativo")
    else:
        st.info("✅ Oráculo Interno Iniciático Ativo (Modo Gratuito Sem Chave)")

    if verificar_ffmpeg():
        st.success("✅ FFmpeg Ativo (Loop + Áudio)")
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
if "indice_carta_selecionada" not in st.session_state:
    st.session_state.indice_carta_selecionada = 0
if "duracao_total" not in st.session_state:
    st.session_state.duracao_total = 20

col_esq, col_dir = st.columns([1.05, 1.15], gap="large")

with col_esq:
    st.subheader("📜 Passo 1: Escolha a Carta")
    metodo_entrada = st.radio(
        "Como deseja carregar a carta?",
        ["☁️ Pasta ou Link do Google Drive (Com Galeria de Pré-visualização)", "📂 Enviar arquivo do computador (.tif, .png, .jpg)"],
        horizontal=False
    )

    if "Enviar arquivo" in metodo_entrada:
        upload = st.file_uploader("Selecione ou arraste a imagem da carta:", type=["tif", "tiff", "png", "jpg", "jpeg", "webp"])
        if upload:
            imagem_carregada = Image.open(upload)
            st.session_state.nome_arquivo = Path(upload.name).stem
            st.session_state.img_bytes = converter_imagem_para_png_bytes(imagem_carregada)
    else:
        url_drive = st.text_input(
            "Cole o link da pasta do Google Drive:",
            value="https://drive.google.com/drive/folders/1CQRc6NEsmsvmN61ANtTtnhAGJXR74h64"
        )
        if st.button("🔄 Carregar Galeria de Cartas do Drive", use_container_width=True):
            if not url_drive:
                st.error("Cole um link válido do Google Drive.")
            else:
                with st.spinner("Carregando lista e miniaturas das cartas..."):
                    try:
                        encontrados = listar_arquivos_pasta_drive(url_drive)
                        if encontrados:
                            st.session_state.arquivos_drive = encontrados
                            st.session_state.indice_carta_selecionada = 0
                            st.success(f"✅ {len(encontrados)} cartas carregadas! Veja as miniaturas abaixo ou escolha na lista.")
                        else:
                            st.error("Nenhuma imagem encontrada. Verifique se a pasta está pública ('Qualquer pessoa com o link').")
                    except Exception as err_dl:
                        st.error(f"Erro ao acessar link do Drive: {err_dl}")

        if st.session_state.arquivos_drive:
            # 1. Galeria Visual de Miniaturas (Expansível para escolher vendo a imagem!)
            with st.expander("🖼️ Galeria Visual de Pré-visualização (Clique na carta desejada)", expanded=True):
                st.caption("Visualize todas as cartas da pasta antes de selecionar:")
                cols_grid = st.columns(4)
                for idx, item in enumerate(st.session_state.arquivos_drive):
                    with cols_grid[idx % 4]:
                        st.image(item["thumb_url"], use_container_width=True)
                        titulo_curto = CATALOGO_ARCANOS[idx]["num"] + " - " + CATALOGO_ARCANOS[idx]["nome"].split("(")[0].strip() if idx < 22 else item["name"]
                        if st.button(f"✓ {titulo_curto}", key=f"btn_gal_{idx}", use_container_width=True):
                            st.session_state.indice_carta_selecionada = idx

            # 2. Selectbox sincronizado com a Galeria
            labels_opcoes = [item["label"] for item in st.session_state.arquivos_drive]
            idx_escolhido = st.selectbox(
                "Ou selecione pelo nome na lista:",
                range(len(labels_opcoes)),
                index=st.session_state.indice_carta_selecionada,
                format_func=lambda i: labels_opcoes[i]
            )
            st.session_state.indice_carta_selecionada = idx_escolhido
            item_escolhido = st.session_state.arquivos_drive[idx_escolhido]

            with st.spinner(f"Carregando {item_escolhido['label']} em alta definição..."):
                try:
                    st.session_state.img_bytes = baixar_bytes_carta_drive(item_escolhido["id"], item_escolhido["name"])
                    st.session_state.nome_arquivo = Path(item_escolhido["name"]).stem
                except Exception as err_card:
                    st.error(f"Erro ao carregar a carta selecionada: {err_card}")

    if st.session_state.img_bytes:
        st.markdown("#### 🔍 Pré-visualização da Carta Selecionada")
        col_img_preview, _ = st.columns([1.2, 0.8])
        with col_img_preview:
            st.image(st.session_state.img_bytes, caption=f"Arquivo: {st.session_state.nome_arquivo}", use_container_width=True)

    ideia_custom = st.text_area(
        "✒️ Diretriz para o Vídeo (Opcional):",
        placeholder="Ex: Quero um vídeo de 20s, no estilo do vídeo referência.",
        height=80
    )

    if st.button("🔍 Analisar Arcano e Estruturar Camadas 2.5D", type="primary", use_container_width=True):
        if not st.session_state.img_bytes:
            st.error("⚠️ Primeiro carregue a pasta do Drive ou envie uma imagem.")
        else:
            with st.spinner("🕯️ Estruturando camadas de profundidade e simbolismo do Arcano..."):
                try:
                    pedido = ideia_custom.strip() or "Construir vídeo de 20s em estilo 2.5D cutout parallax com estética de papiro antigo, luz de velas, órbita 360 e diagrama celestial no céu."
                    st.session_state.duracao_total = extrair_duracao_segundos(pedido, padrao=20)
                    st.session_state.plano_ia = diagnosticar_carta_ia(
                        st.session_state.api_key_mem,
                        st.session_state.img_bytes,
                        pedido,
                        arcano_idx=st.session_state.indice_carta_selecionada
                    )
                except Exception as e:
                    st.error(f"Erro ao analisar carta: {e}")

with col_dir:
    st.subheader("🎬 Passo 2: Revisão & Renderização")

    if not st.session_state.plano_ia:
        st.info("👈 Escolha uma carta na Galeria ao lado e clique em **Analisar Arcano** para preparar as camadas 2.5D.")
    else:
        plano = st.session_state.plano_ia
        if plano.get("_aviso_chave"):
            st.markdown("""
            <div class="oracle-notice-bar">
                <span>🕯️ <strong>Modo Oráculo Interno Ativo</strong> — Funcionamento 100% gratuito habilitado automaticamente.</span>
                <span class="oracle-help-badge">?
                    <span class="tooltip-box">
                        <strong>Por que este aviso aparece?</strong><br>
                        Fique tranquilo! É assim mesmo que o sistema deve operar quando você usa sem chave paga ou quando uma chave anterior do Google AI Studio expira.<br><br>
                        O <strong>Oráculo Interno Iniciático</strong> já contém todos os 22 Arcanos mapeados e gera o seu vídeo normalmente sem nenhum custo.
                    </span>
                </span>
            </div>
            """, unsafe_allow_html=True)
            with st.expander("ℹ️ Ver detalhes técnicos da chave de API (Opcional — clique para abrir/minimizar)", expanded=False):
                st.caption(plano["_aviso_chave"])

        modelo_usado = plano.get("_modelo_usado", "Oráculo IA")
        st.success(f"✦ **Carta Estruturada ({modelo_usado}):** {plano.get('arcano_nome', 'Arcano Maior')}")

        with st.expander("📐 Camadas em Papiro 2.5D & Simbolismo (Editável)", expanded=True):
            camadas = plano.get("camadas_z_space", {})
            c1 = st.text_input("1º Plano (Elementos Frontais):", value=camadas.get("primeiro_plano", ""))
            c2 = st.text_input("Plano Central (Recorte 2.5D em Giro 360°):", value=camadas.get("plano_medio", ""))
            c3 = st.text_input("Plano de Fundo (Cenário Expandido):", value=camadas.get("plano_fundo", ""))
            particulas = st.text_input("🕯️ Partículas & Luz de Velas:", value=plano.get("particulas_e_fisica", ""))
            astro = st.text_input("🌌 Revelação no Diagrama Celestial (Tilt-up):", value=plano.get("astro_revelacao_ceu", ""))
            simbolo_uni = st.text_input("✡️ Glifo / Símbolo Hermético no Topo:", value=plano.get("simbolo_unicode", "✦"))

        with st.expander("⏱️ Duração, Música & Loop Infinito", expanded=True):
            duracao_escolhida = st.slider("Duração total do vídeo final (segundos):", min_value=8, max_value=30, value=int(st.session_state.duracao_total), step=2)
            audio_upload = st.file_uploader("Adicionar música de fundo (.mp3 / .wav):", type=["mp3", "wav", "m4a"])
            aplicar_loop_reverso = st.checkbox("Ciclo Hermético Perfeito (Vai ao céu e retorna suavemente à carta 2D)", value=True)

        plano["astro_revelacao_ceu"] = astro
        plano["simbolo_unicode"] = simbolo_uni

        prompt_tecnico = st.text_area(
            "Roteiro Técnico de Renderização:",
            value=(
                f"{plano.get('veo_prompt_en', '')} "
                f"Foreground: {c1}. Midground: {c2}. Background: {c3}. "
                f"Particles: {particulas}. Sky reveal: {astro}."
            ),
            height=85
        )

        if st.button("🚀 GERAR VÍDEO DO ARCANO AGORA", type="primary", use_container_width=True):
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
                    ok = renderizar_video_veo(st.session_state.api_key_mem, st.session_state.img_bytes, prompt_tecnico, raw_mp4, barra, status_txt)

                if ok:
                    barra.progress(90)
                    status_txt.info(f"🎞️ Finalizando ciclo reverso ({duracao_escolhida}s) e mixagem de áudio via FFmpeg...")
                    pos_producao_loop_e_audio(raw_mp4, caminho_audio_temp, final_mp4, aplicar_loop_reverso)
                    barra.progress(100)
                    status_txt.success(f"✦ Vídeo Concluído ({duracao_escolhida}s)! Assista abaixo ou clique para baixar.")

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

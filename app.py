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
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;600&family=Inter:wght@400;500;600&display=swap');

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
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Barra Lateral */
section[data-testid="stSidebar"] {
    background: #1A0C06 !important;
    border-right: 1px solid #4A2E18 !important;
}

/* Títulos com Cinzel suave (sem exagero e sem sombra pesada) */
h1, h2, h3 {
    font-family: 'Cinzel', Georgia, serif !important;
    color: var(--parchment-light) !important;
    letter-spacing: 0.03em !important;
    font-weight: 600 !important;
}

/* Textos corridos, labels e markdown com fonte Inter super limpa — preservando os ícones Material Symbols do Streamlit! */
.stApp, p, label, .stMarkdown, .stCaption, li, input, textarea {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Garante que todos os ícones internos do Streamlit (setas, olho da senha, upload, etc.) usem a fonte de ícones nativa */
span[data-testid="stIconMaterial"], .material-symbols-rounded, [ translate="no" ] {
    font-family: 'Material Symbols Rounded' !important;
}

p, label {
    font-size: 0.96rem !important;
    line-height: 1.55 !important;
    color: var(--parchment-mid) !important;
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
# MOTOR 1 (IA GENERATIVA DE VÍDEO GRATUITA - HUGGING FACE / GRADIO SPACES)
# Gera vídeo com IA Generativa Real (como o vídeo teste do chat) sem custo!
# ==============================================================================
def renderizar_video_ia_generativa_gratuita(
    img_bytes: bytes,
    prompt_en: str,
    saida_raw: Path,
    barra_progresso,
    texto_status,
    hf_token: str = ""
) -> bool:
    """
    Tenta gerar o vídeo em motores de IA Generativa de Vídeo gratuitos na nuvem
    (LTX-Video / Wan-2.1 / SVD via Gradio Client). Se as filas gratuitas estiverem
    lotadas no momento, faz fallback automático para o novo Motor Diorama 3D Real!
    """
    try:
        from gradio_client import Client, handle_file
    except ImportError:
        return False

    temp_img = PASTA_TEMP / "input_ia_gen.png"
    temp_img.write_bytes(img_bytes)

    espacos_ia_gratuitos = [
        ("Lightricks/LTX-Video", "ltx"),
        ("Wan-AI/Wan2.1", "wan"),
        ("multimodalart/stable-video-diffusion", "svd"),
    ]

    for space_id, tipo in espacos_ia_gratuitos:
        try:
            texto_status.info(f"🌐 Conectando ao Motor de Vídeo IA Gratuito ({space_id})...")
            barra_progresso.progress(20)
            kwargs = {"hf_token": hf_token.strip()} if hf_token and hf_token.strip() else {}
            cl = Client(space_id, **kwargs)
            barra_progresso.progress(40)
            texto_status.info(f"🎬 Gerando movimento 3D generativo por IA em {space_id}...")

            if tipo == "svd":
                res = cl.predict(handle_file(str(temp_img)), api_name="/video")
            else:
                res = cl.predict(
                    prompt=prompt_en,
                    image=handle_file(str(temp_img)),
                )

            video_path = res[0] if isinstance(res, (list, tuple)) else res
            if isinstance(video_path, dict) and "video" in video_path:
                video_path = video_path["video"]
            if video_path and os.path.exists(str(video_path)):
                shutil.copy(str(video_path), str(saida_raw))
                barra_progresso.progress(85)
                return True
        except Exception:
            continue

    return False

# ==============================================================================
# MOTOR 2 (DIORAMA 3D DE SILHUETA RECORTADA & CÂMERA ESPACIAL REAL - 100% GRATUITO)
# Corrige o problema de "apenas dar zoom/inverter a carta inteira":
# - Remove o fundo chapado e recorta a SILHUETA REAL do personagem (Paper Cutout)
# - Cria 6 planos de profundidade em perspectiva 3D (Chão 3D, Pilares Laterais,
#   Elementos de 1º Plano, Silhueta do Personagem com Borda de Papel, Montanhas e Céu)
# ==============================================================================
def extrair_silhueta_personagem_tarot(card_rgba: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image]:
    """
    Separa de verdade a figura central do fundo da carta (sem recortar um retângulo)!
    Identifica a cor dominante do fundo da carta (ex: amarelo/bege do Tarô de Marselha),
    isola o personagem central com contorno de recorte de papel (Paper Mario / MysticMayhem),
    isola os elementos da base/primeiro plano e cria o cenário limpo ao fundo.
    """
    from scipy import ndimage

    w, h = card_rgba.size
    arr = np.array(card_rgba)
    rgb = arr[:, :, :3].astype(np.float32)

    # 1. Recorta apenas a área interna da arte (eliminando as bordas pretas/brancas e a caixa do nome embaixo)
    x0, y0, x1, y1 = int(w * 0.09), int(h * 0.06), int(w * 0.91), int(h * 0.84)
    inner_mask = np.zeros((h, w), dtype=bool)
    inner_mask[y0:y1, x0:x1] = True

    # 2. Amostra os cantos superiores internos da carta para descobrir a cor do céu/fundo da carta
    amostras_bg = np.concatenate([
        rgb[y0+5:y0+35, x0+5:x0+40].reshape(-1, 3),
        rgb[y0+5:y0+35, x1-40:x1-5].reshape(-1, 3),
        rgb[int(h*0.20):int(h*0.30), x0+5:x0+25].reshape(-1, 3),
        rgb[int(h*0.20):int(h*0.30), x1-25:x1-5].reshape(-1, 3),
    ], axis=0)
    cor_fundo = np.median(amostras_bg, axis=0)

    # Distância de cor em relação ao fundo chapado da carta
    dist_bg = np.linalg.norm(rgb - cor_fundo, axis=2)

    # O personagem/elementos são onde a cor difere do fundo OU onde há traços pretos de xilogravura
    luminancia = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    fg_raw = ((dist_bg > 34.0) | (luminancia < 85.0)) & inner_mask

    # Fecha buracos internos da silhueta do personagem para formar um recorte sólido de papel
    fg_closed = ndimage.binary_closing(fg_raw, structure=np.ones((9, 9)))
    fg_filled = ndimage.binary_fill_holes(fg_closed)

    # Foca a silhueta do personagem central (com máscara espacial suave nas laterais)
    yy, xx = np.mgrid[0:h, 0:w]
    centro_mask = ((xx > w * 0.14) & (xx < w * 0.86) & (yy > h * 0.08) & (yy < h * 0.82))
    silhueta_mask = fg_filled & centro_mask
    silhueta_mask = ndimage.binary_opening(silhueta_mask, structure=np.ones((5, 5)))
    silhueta_mask = ndimage.binary_dilation(silhueta_mask, structure=np.ones((4, 4)))

    # Cria a borda branca/pergaminho ao redor da silhueta recortada (Efeito Paper Cutout autêntico!)
    borda_dilatada = ndimage.binary_dilation(silhueta_mask, structure=np.ones((11, 11)))
    apenas_borda = borda_dilatada & (~silhueta_mask)

    cutout_arr = np.zeros((h, w, 4), dtype=np.uint8)
    # Pinta a borda de papel papiro (#F2DEC1) e sombra escura ao redor do personagem recortado
    cutout_arr[apenas_borda] = [238, 214, 178, 255]
    cutout_arr[silhueta_mask, :3] = arr[silhueta_mask, :3]
    cutout_arr[silhueta_mask, 3] = 255
    personagem_cutout = Image.fromarray(cutout_arr, mode="RGBA")

    # Cria elementos de 1º plano (base inferior da carta, pedras, plantas, escudo e letreiro recortado)
    fg_base_mask = np.zeros((h, w), dtype=bool)
    fg_base_mask[int(h * 0.68):int(h * 0.94), int(w * 0.06):int(w * 0.94)] = True
    fg_base_mask = fg_base_mask & ((dist_bg > 28.0) | (yy > h * 0.83))
    fg_base_dil = ndimage.binary_dilation(fg_base_mask, structure=np.ones((6, 6)))
    borda_fg = fg_base_dil & (~fg_base_mask)

    fg_arr = np.zeros((h, w, 4), dtype=np.uint8)
    fg_arr[borda_fg] = [213, 173, 122, 240]
    fg_arr[fg_base_mask, :3] = arr[fg_base_mask, :3]
    fg_arr[fg_base_mask, 3] = 255
    primeiro_plano_cutout = Image.fromarray(fg_arr, mode="RGBA")

    # Cria pilastras/arcos laterais em estilo diorama para passarem pela câmera durante o zoom
    pilares_arr = np.zeros((h, w, 4), dtype=np.uint8)
    larg_pilar = int(w * 0.13)
    pilares_arr[:, :larg_pilar, :3] = arr[:, :larg_pilar, :3]
    pilares_arr[:, :larg_pilar, 3] = 255
    pilares_arr[:, w-larg_pilar:, :3] = arr[:, w-larg_pilar:, :3]
    pilares_arr[:, w-larg_pilar:, 3] = 255
    pilares_laterais = Image.fromarray(pilares_arr, mode="RGBA")

    return personagem_cutout, primeiro_plano_cutout, pilares_laterais

def projetar_plano_3d_perspectiva(img_rgba: Image.Image, yaw_graus: float, pitch_graus: float = 0.0) -> Image.Image:
    """
    Aplica deformação real de perspectiva 3D (Homografia 8-coeficientes) em vez de apenas
    achatar a largura ou inverter a imagem! Mantém a orientação correta da arte da carta,
    criando o efeito de câmera orbitando no espaço 3D ao redor do recorte de papel,
    com múltiplas camadas de extrusão lateral (espessura 3D do cartão).
    """
    w, h = img_rgba.size
    # Limita o ângulo visual de cada plano para que a câmera orbite com paralaxe 3D realista SEM espelhar o texto/arte ao avesso!
    rad_y = math.radians(yaw_graus)
    inclinacao = math.sin(rad_y) # -1.0 a +1.0
    escala_x = 0.72 + 0.28 * math.cos(rad_y) # Nunca zera nem inverte a imagem!

    # Calcula os 4 vértices do trapézio em perspectiva 3D
    margem_x = (w * (1.0 - escala_x)) * 0.5
    desvio_y = h * 0.09 * inclinacao

    # Vértices de destino (x0,y0 = sup esq, x1,y1 = sup dir, x2,y2 = inf dir, x3,y3 = inf esq)
    dx_esq = margem_x
    dx_dir = w - margem_x
    dy_esq_top = max(0.0, -desvio_y)
    dy_esq_bot = h - max(0.0, -desvio_y)
    dy_dir_top = max(0.0, desvio_y)
    dy_dir_bot = h - max(0.0, desvio_y)

    # Resolve matriz de homografia (destino -> origem)
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float64)
    dst = np.array([
        [dx_esq, dy_esq_top],
        [dx_dir, dy_dir_top],
        [dx_dir, dy_dir_bot],
        [dx_esq, dy_esq_bot]
    ], dtype=np.float64)

    A = []
    B = []
    for i in range(4):
        x, y = dst[i]
        u, v = src[i]
        A.append([x, y, 1, 0, 0, 0, -x*u, -y*u])
        A.append([0, 0, 0, x, y, 1, -x*v, -y*v])
        B.append(u)
        B.append(v)
    coeffs = np.linalg.solve(np.array(A), np.array(B))

    warped = img_rgba.transform((w, h), Image.Transform.PERSPECTIVE, coeffs.tolist(), Image.Resampling.BICUBIC)

    # Cria extrusão 3D real (várias fatias laterais dando espessura de placa de madeira/papiro recortado)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dir_extrusao = int(-inclinacao * 14)
    if abs(dir_extrusao) > 1:
        r, g, b, a = warped.split()
        fatia_escura = Image.merge("RGBA", (
            r.point(lambda _: 115),
            g.point(lambda _: 78),
            b.point(lambda _: 42),
            a
        ))
        passos = abs(dir_extrusao)
        sinal = 1 if dir_extrusao > 0 else -1
        for s in range(passos, 0, -1):
            canvas.paste(fatia_escura, (s * sinal, int(abs(s) * 0.4)), warped)

    canvas.paste(warped, (0, 0), warped)
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
    """
    Novo Motor Diorama 3D Multi-Camadas:
    - A carta 2D abre-se como um teatro/diorama 3D;
    - A moldura e os pilares passam pelas bordas da lente;
    - A silhueta REAL recortada do personagem fica no centro de um palco 3D com montanhas,
      chão em perspectiva, tochas/brasas animadas e câmera orbitando com paralaxe de 6 camadas;
    - Depois a câmera faz o Tilt-up contínuo pelas montanhas até a Esfera Armilar no céu!
    """
    W, H = 720, 1280
    total_frames = duracao_s * fps
    img_pil = Image.open(io.BytesIO(img_bytes))
    card_full = img_pil.convert("RGBA").resize((int(W * 0.84), int(H * 0.80)), Image.Resampling.LANCZOS)
    cw, ch = card_full.size

    texto_status.info("✂️ Isolando silhueta real do personagem e construindo camadas 3D do Diorama...")
    personagem_cutout, fg_base_cutout, pilares_laterais = extrair_silhueta_personagem_tarot(card_full)

    # Fundo atmosférico profundo (sem o personagem chapado)
    bg_ambiente = img_pil.convert("RGB").resize((int(W * 1.35), int(H * 1.35)), Image.Resampling.LANCZOS)
    bg_ambiente = bg_ambiente.filter(ImageFilter.GaussianBlur(radius=26))
    bg_ambiente = ImageEnhance.Brightness(bg_ambiente).enhance(0.32)
    sepia_bg = Image.new("RGB", bg_ambiente.size, (34, 15, 6))
    bg_ambiente = Image.blend(bg_ambiente, sepia_bg, alpha=0.45)

    cor_p = (243, 184, 82)
    astro_txt = plano.get("astro_revelacao_ceu", "☉")
    simbolo = plano.get("simbolo_unicode", "✦")
    arcano_titulo = plano.get("arcano_nome", "ARCANO")

    rng = random.Random(42)
    estrelas = [(rng.randint(20, W-20), rng.randint(20, H-20), rng.randint(1, 3), rng.random()) for _ in range(150)]
    particulas = [
        {"x": rng.uniform(40, W-40), "y": rng.uniform(80, H-40), "vy": rng.uniform(3.5, 8.5), "r": rng.randint(2, 6), "fase": rng.uniform(0, 6.28), "camada": rng.choice([0, 1])}
        for _ in range(75)
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

        # Roteiro Cinematográfico Contínuo:
        # 0.00 -> 0.16: Desconstrução da carta 2D (os pilares da moldura avançam na direção da câmera e saem de quadro, revelando o palco 3D)
        # 0.16 -> 0.70: Câmara caminha dentro do palco 3D e faz órbita em paralaxe real ao redor da silhueta recortada do personagem
        # 0.70 -> 1.00: Tilt-up para o céu acima das montanhas revelando o Diagrama Celestial e a Esfera Armilar girando
        if t < 0.16:
            p = t / 0.16
            ease = p * p * (3 - 2 * p)
            cam_zoom = 1.0 + 0.32 * ease
            pilar_zoom = 1.0 + 0.95 * ease
            orbita_graus = ease * 25.0
            tilt_ceu = 0.0
            mix_carta_2d = max(0.0, 1.0 - p * 1.45)
        elif t < 0.70:
            p = (t - 0.16) / 0.54
            cam_zoom = 1.32 + 0.22 * math.sin(p * math.pi)
            pilar_zoom = 1.95 + 0.5 * p
            # Oscilação orbital ampla em paralaxe 3D (mostrando a profundidade Z e as bordas recortadas sem inverter o personagem de cabeça/lado)
            orbita_graus = 25.0 * math.cos(p * 2.0 * math.pi) + 38.0 * math.sin(p * 2.0 * math.pi)
            tilt_ceu = 0.0
            mix_carta_2d = 0.0
        else:
            p = (t - 0.70) / 0.30
            ease = p * p * (3 - 2 * p)
            cam_zoom = 1.32 - 0.15 * ease
            pilar_zoom = 2.45
            orbita_graus = (1.0 - ease) * 25.0
            tilt_ceu = ease
            mix_carta_2d = 0.0

        desloc_x_cam = int(math.sin(math.radians(orbita_graus * 2.2)) * 55)
        offset_y_cena = int(tilt_ceu * H * 0.92)

        # 1. Céu Noturno & Abóbada Celeste
        frame = Image.new("RGBA", (W, H), (18, 8, 3, 255))
        draw_sky = ImageDraw.Draw(frame)

        for sx, sy, sr, sf in estrelas:
            brilho = int(140 + 110 * math.sin(f_idx * 0.22 + sf * 10))
            pos_y_est = sy - int((1.0 - tilt_ceu) * H * 0.55)
            pos_x_est = (sx - int(desloc_x_cam * 0.2)) % W
            if 0 <= pos_y_est < H:
                draw_sky.ellipse((pos_x_est-sr, pos_y_est-sr, pos_x_est+sr, pos_y_est+sr), fill=(242, 222, 193, brilho))

        # 2. Fundo Atmosférico em Paralaxe Lenta (Z = -3)
        bg_x = -(bg_ambiente.width - W) // 2 - int(desloc_x_cam * 0.35)
        bg_y = -(bg_ambiente.height - H) // 2 + int(offset_y_cena * 0.75)
        frame.paste(bg_ambiente, (bg_x, bg_y))

        # 3. Cordilheira / Montanhas Escuras em Camadas 2.5D ao Fundo (Z = -2)
        draw_bg_mounts = ImageDraw.Draw(frame)
        base_montanha_y = int(H * 0.68) + offset_y_cena
        pts_montanha_fundo = []
        for mx in range(-80, W + 120, 40):
            mh_val = int(95 * math.sin(mx * 0.012 + 1.2) + 55 * math.cos(mx * 0.028))
            pts_montanha_fundo.append((mx - int(desloc_x_cam * 0.55), base_montanha_y - 120 + mh_val))
        pts_montanha_fundo.extend([(W + 120, H + offset_y_cena), (-80, H + offset_y_cena)])
        draw_bg_mounts.polygon(pts_montanha_fundo, fill=(28, 13, 6, 235), outline=(140, 94, 53, 180))

        # 4. Chão de Palco 3D com Grade de Perspectiva Hermética (Z = -1 a +1)
        chao_topo_y = int(H * 0.72) + offset_y_cena
        if chao_topo_y < H:
            draw_floor = ImageDraw.Draw(frame)
            draw_floor.rectangle((0, chao_topo_y, W, H), fill=(22, 10, 4, 248))
            vp_x = W // 2 - int(desloc_x_cam * 0.6)
            for gx in range(-900, 1600, 110):
                draw_floor.line([(vp_x, chao_topo_y), (gx - int(desloc_x_cam * 1.6), H)], fill=(122, 82, 48, 110), width=2)
            for gy_step in [18, 45, 85, 140, 215, 310]:
                ly = chao_topo_y + gy_step
                if ly < H:
                    draw_floor.line([(0, ly), (W, ly)], fill=(122, 82, 48, 95), width=1)

        # 5. Partículas Traseiras (Fogo/Luz de Velas atrás do personagem)
        draw_p = ImageDraw.Draw(frame)
        for p in particulas:
            p["y"] -= p["vy"]
            if p["y"] < 0:
                p["y"] = H
            if p["camada"] == 0:
                px = int(p["x"] + math.sin(f_idx * 0.14 + p["fase"]) * 16 - desloc_x_cam * 0.7) % W
                py = int(p["y"] + offset_y_cena * 0.5) % H
                r = p["r"]
                draw_p.ellipse((px-r, py-r, px+r, py+r), fill=(cor_p[0], cor_p[1], cor_p[2], 175))

        # 6. SILHUETA RECORTADA DO PERSONAGEM CENTRAL EM PERSPECTIVA 3D (Z = 0)
        char_3d = projetar_plano_3d_perspectiva(personagem_cutout, orbita_graus)
        char_w = int(cw * cam_zoom)
        char_h = int(ch * cam_zoom)
        char_zoomed = char_3d.resize((char_w, char_h), Image.Resampling.BILINEAR)
        char_x = (W - char_w) // 2 + int(desloc_x_cam * 0.95)
        char_y = (H - char_h) // 2 + offset_y_cena
        frame.paste(char_zoomed, (char_x, char_y), char_zoomed)

        # 7. ELEMENTOS DE 1º PLANO EM PARALAXE MAIS RÁPIDA (Z = +1 -> Frente do Personagem!)
        fg_3d = projetar_plano_3d_perspectiva(fg_base_cutout, orbita_graus * 1.25)
        fg_w = int(cw * (cam_zoom * 1.14))
        fg_h = int(ch * (cam_zoom * 1.14))
        fg_zoomed = fg_3d.resize((fg_w, fg_h), Image.Resampling.BILINEAR)
        fg_x = (W - fg_w) // 2 + int(desloc_x_cam * 1.55)
        fg_y = (H - fg_h) // 2 + int(offset_y_cena * 1.18) + 28
        frame.paste(fg_zoomed, (fg_x, fg_y), fg_zoomed)

        # 8. Pilares / Moldura Passando pelas Bordas da Lente no Início do Zoom (Z = +2)
        if pilar_zoom < 2.25:
            pw = int(cw * pilar_zoom)
            ph = int(ch * pilar_zoom)
            pil_zoomed = pilares_laterais.resize((pw, ph), Image.Resampling.BILINEAR)
            frame.paste(pil_zoomed, ((W - pw)//2 + int(desloc_x_cam * 1.9), (H - ph)//2 + int(offset_y_cena * 1.3)), pil_zoomed)

        # 9. Revelação do Diagrama Celestial & Esfera Armilar Dinâmica no Topo (Tilt-up)
        if tilt_ceu > 0.12:
            alpha_astro = int(min(1.0, (tilt_ceu - 0.12) / 0.65) * 255)
            cx_ceu, cy_ceu = W // 2, int(H * 0.36) - int((1.0 - tilt_ceu) * 260)
            giro_anel = f_idx * 4.5
            for idx_r, r_halo in enumerate([195, 150, 110]):
                draw_sky.arc(
                    (cx_ceu - r_halo, cy_ceu - r_halo, cx_ceu + r_halo, cy_ceu + r_halo),
                    start=giro_anel * (1 if idx_r % 2 == 0 else -1),
                    end=giro_anel * (1 if idx_r % 2 == 0 else -1) + 290,
                    fill=(213, 173, 122, int(alpha_astro * 0.75)),
                    width=3
                )
            draw_sky.ellipse((cx_ceu - 175, cy_ceu - 55, cx_ceu + 175, cy_ceu + 55), outline=(228, 189, 133, alpha_astro), width=3)
            draw_sky.ellipse((cx_ceu - 55, cy_ceu - 175, cx_ceu + 55, cy_ceu + 175), outline=(184, 134, 59, int(alpha_astro * 0.65)), width=2)
            draw_sky.ellipse((cx_ceu - 72, cy_ceu - 72, cx_ceu + 72, cy_ceu + 72), fill=(44, 22, 9, alpha_astro), outline=(243, 184, 82, alpha_astro), width=4)
            draw_sky.text((cx_ceu, cy_ceu - 8), simbolo, fill=(255, 230, 180, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 122), astro_txt.upper(), fill=(243, 184, 82, alpha_astro), anchor="mm")
            draw_sky.text((cx_ceu, cy_ceu + 154), arcano_titulo.upper(), fill=(230, 198, 150, alpha_astro), anchor="mm")

        # 10. Partículas Frontais (Brasas passando perto da lente)
        for p in particulas:
            if p["camada"] == 1:
                px = int(p["x"] + math.sin(f_idx * 0.18 + p["fase"]) * 22 - desloc_x_cam * 1.4) % W
                py = int(p["y"]) % H
                r = p["r"] + 1
                draw_p.ellipse((px-r, py-r, px+r, py+r), fill=(255, 210, 120, 235))

        # 11. Transição Suave da Carta 2D Original nos Primeiros Quadros
        if mix_carta_2d > 0.01:
            c2d_layer = Image.new("RGBA", (W, H), (23, 9, 3, int(255 * mix_carta_2d)))
            card_2d_scaled = card_full.resize((cw, ch), Image.Resampling.LANCZOS)
            mask_2d = Image.new("L", (cw, ch), int(255 * mix_carta_2d))
            c2d_layer.paste(card_2d_scaled, ((W - cw)//2, (H - ch)//2), mask_2d)
            frame = Image.alpha_composite(frame, c2d_layer)

        proc.stdin.write(frame.convert("RGB").tobytes())

        if f_idx % 8 == 0 or f_idx == total_frames - 1:
            pct = int(15 + 72 * (f_idx / total_frames))
            barra_progresso.progress(pct)
            texto_status.info(f"🕯️ Renderizando Diorama 3D Multi-Camadas: quadro {f_idx+1}/{total_frames}...")

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
            "🆓 Motor Diorama 3D Silhueta Recortada (100% Gratuito / Instantâneo)",
            "🌐 IA Generativa de Vídeo Cloud (Gratuito via Hugging Face + Fallback 3D)",
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
            st.warning(plano["_aviso_chave"])

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

                if "IA Generativa de Vídeo Cloud" in motor_escolhido:
                    ok = renderizar_video_ia_generativa_gratuita(
                        st.session_state.img_bytes,
                        prompt_tecnico,
                        raw_mp4,
                        barra,
                        status_txt
                    )
                    if not ok:
                        status_txt.info("⚡ Filas públicas de IA cheias no momento — ativando Motor Diorama 3D Silhueta Recortada...")
                        ok = renderizar_video_nativo_gratuito(
                            st.session_state.img_bytes,
                            plano,
                            raw_mp4,
                            barra,
                            status_txt,
                            duracao_s=duracao_ida
                        )
                elif "100% Gratuito" in motor_escolhido:
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

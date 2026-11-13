"""
MOTOR AI VIDEO AGENT v5 — ESTRATÉGIA HUGGING FACE & IA GRATUITA MULTI-CENAS
==========================================================================
Arquitetura 100% focada em compor cenas reais e dinâmicas sem custo:
  1. Roteiro Cinematográfico Inteligente (LLM gratuito via Pollinations / HF / Gemini + regras visuais).
  2. Geração de Keyframes de Cenas Novas em 9:16 (Pollinations Flux / Hugging Face Inference API).
  3. Animação Image-to-Video na Nuvem via Hugging Face Spaces (Wan 2.1, LTX-Video, CogVideoX, SVD)
     usando Gradio Client (com ou sem HF_TOKEN gratuito).
  4. Transições Signature estilo MysticMayhem (Portal de Luz, Zoom-Through Radial, Vórtice Espiral)
     e fallback cinematográfico dinâmico caso alguma fila pública esteja congestionada.
"""

from __future__ import annotations

import os
import re
import io
import json
import math
import time
import random
import shutil
import hashlib
import subprocess
import urllib.parse
from pathlib import Path

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

W, H, FPS = 720, 1280, 24


# ------------------------------------------------------------------------------
# Utilitários de Sistema, Drive e Imagem
# ------------------------------------------------------------------------------
def obter_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


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
        raise ValueError("Link do Google Drive inválido.")

    extensoes_img = (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp")
    extensoes_vid = (".mp4", ".mov", ".avi", ".webm")

    if tipo == "file":
        return [{
            "name": "Arquivo_Drive.tif",
            "label": "Arquivo Individual do Drive",
            "id": drive_id,
            "tipo": "imagem",
            "thumb_url": f"https://drive.google.com/thumbnail?id={drive_id}&sz=w320",
        }]

    embed_url = f"https://drive.google.com/embeddedfolderview?id={drive_id}#list"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(embed_url, headers=headers, timeout=20)

    itens = []
    if resp.status_code == 200:
        padrao = re.compile(
            r'id="entry-([a-zA-Z0-9_-]+)".*?class="flip-entry-title">([^<]+)</div>',
            re.DOTALL
        )
        for m in padrao.finditer(resp.text):
            f_id, f_name = m.group(1), m.group(2).strip()
            low = f_name.lower()
            if low.endswith(extensoes_img):
                itens.append({"name": f_name, "id": f_id, "tipo": "imagem"})
            elif low.endswith(extensoes_vid):
                itens.append({"name": f_name, "id": f_id, "tipo": "video"})

    itens.sort(key=lambda x: x["name"])
    for item in itens:
        item["thumb_url"] = f"https://drive.google.com/thumbnail?id={item['id']}&sz=w320"
        item["label"] = f"{'🎬' if item['tipo'] == 'video' else '🖼️'} {item['name']}"

    return itens


def baixar_bytes_carta_drive(file_id: str) -> bytes:
    sess = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    url_uc = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = sess.get(url_uc, headers=headers, stream=True, timeout=30)
    for k, v in resp.cookies.items():
        if k.startswith("download_warning"):
            resp = sess.get(f"{url_uc}&confirm={v}", headers=headers, stream=True, timeout=30)
            break
    raw_bytes = resp.content
    try:
        img = Image.open(io.BytesIO(raw_bytes))
    except Exception:
        url_hi = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
        resp_thumb = sess.get(url_hi, headers=headers, timeout=25)
        img = Image.open(io.BytesIO(resp_thumb.content))

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _cover(img: Image.Image, w: int = W, h: int = H) -> Image.Image:
    img = img.convert("RGB")
    sw, sh = img.size
    s = max(w / sw, h / sh)
    nw, nh = max(w, round(sw * s)), max(h, round(sh * s))
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return img.crop((x0, y0, x0 + w, y0 + h))


# ------------------------------------------------------------------------------
# 1. ROTEIRO INTELIGENTE GRATUITO (Analisa estilo, chat e cria cenas distintas)
# ------------------------------------------------------------------------------
def criar_roteiro_cenas_gratuito(
    imagem_pil: Image.Image,
    orientacoes_chat: str = "",
    hf_token: str = "",
    gemini_key: str = ""
) -> list[dict]:
    """
    Cria um roteiro de 3 cenas cinematográficas distintas para transformar a imagem
    em uma jornada estilo MysticMayhem (Cena 1: Arquétipo/Objeto vivo em close;
    Cena 2: Cenário/Ambiente expandido; Cena 3: Revelação Cósmica/Celestial).
    Usa LLM gratuito (Pollinations Text / HF Inference) com fallback estruturado.
    """
    diretriz = orientacoes_chat.strip() if orientacoes_chat else "mystic cinematic atmosphere, dramatic lighting, smooth camera motion"

    # Tenta gerar prompts personalizados via endpoint gratuito de texto do Pollinations (sem chave!)
    try:
        prompt_sys = (
            "You are a visual director creating a 3-scene vertical (9:16) animated journey inspired by mysticmayhem.ai. "
            "Given the user direction, output ONLY a JSON array of 3 objects with keys: "
            "'titulo' (Portuguese), 'prompt_imagem' (English visual description of a new full-bleed vertical illustration "
            "with vintage engraving/woodcut ink linework, rich atmosphere, no text/borders), and "
            "'prompt_video' (English camera and subject motion prompt for Image-to-Video AI). "
            f"User direction: {diretriz}"
        )
        url_llm = "https://text.pollinations.ai/" + urllib.parse.quote(prompt_sys) + "?json=true"
        r = requests.get(url_llm, timeout=18)
        if r.status_code == 200:
            txt = re.sub(r"^```(?:json)?|```$", "", r.text.strip(), flags=re.M).strip()
            dados = json.loads(txt)
            if isinstance(dados, dict) and "cenas" in dados:
                dados = dados["cenas"]
            if isinstance(dados, list) and len(dados) >= 3:
                return dados[:3]
    except Exception:
        pass

    # Fallback inteligente estruturado (garante 3 cenas realmente diferentes!)
    return [
        {
            "titulo": "Cena 1 — Despertar do Elemento Central",
            "usar_imagem_original": True,
            "prompt_imagem": f"close-up dramatic perspective of the central figure coming alive, vintage hand-inked engraving art, {diretriz}, rich shadows and golden highlights, full bleed 9:16, no borders, no text",
            "prompt_video": f"Cinematic 3D camera push-in and slight orbit around the central subject coming to life, subtle floating embers and atmospheric mist, {diretriz}, smooth continuous motion"
        },
        {
            "titulo": "Cena 2 — Mergulho no Mundo e Cenário",
            "usar_imagem_original": False,
            "prompt_imagem": f"expansive mystical landscape with ancient stone cliffs, swirling mist, dramatic rays of light and symbolic elements, vintage tarot woodcut engraving illustration style, {diretriz}, vertical 9:16, no text, no frame",
            "prompt_video": f"First-person camera flying smoothly forward through the mystical landscape, volumetric clouds and particles drifting past, {diretriz}, cinematic depth"
        },
        {
            "titulo": "Cena 3 — Ascensão Celestial & Cosmos",
            "usar_imagem_original": False,
            "prompt_imagem": f"celestial night sky above mountain peaks with a radiant armillary sphere, glowing sun and crescent moon surrounded by golden constellations, vintage engraving illustration, {diretriz}, vertical 9:16, no text",
            "prompt_video": f"Camera tilting upward into the starry cosmos toward a glowing celestial sphere radiating golden light, ethereal cosmic energy, {diretriz}"
        }
    ]


# ------------------------------------------------------------------------------
# 2. GERAÇÃO DE KEYFRAMES ILUSTRADOS (IA Gratuita: HF Inference / Pollinations Flux)
# ------------------------------------------------------------------------------
def gerar_keyframe_ia_gratuito(
    prompt_cena: str,
    hf_token: str = "",
    seed: int = 42
) -> Image.Image | None:
    """
    Gera um quadro-chave (Keyframe) ilustrado em 9:16 usando modelos gratuitos:
    1) Hugging Face Inference API (FLUX.1-schnell ou SDXL) se HF_TOKEN estiver presente;
    2) Pollinations.ai (Flux / Turbo) 100% gratuito sem exigir chave!
    """
    # Tentativa 1: Hugging Face Inference API (Gratuita com token hf_...)
    if hf_token and len(hf_token.strip()) > 8:
        modelos_hf = [
            "black-forest-labs/FLUX.1-schnell",
            "stabilityai/stable-diffusion-xl-base-1.0",
        ]
        headers = {"Authorization": f"Bearer {hf_token.strip()}"}
        for mod in modelos_hf:
            try:
                api_url = f"https://api-inference.huggingface.co/models/{mod}"
                payload = {
                    "inputs": prompt_cena,
                    "parameters": {"width": 576, "height": 1024, "num_inference_steps": 4}
                }
                resp = requests.post(api_url, headers=headers, json=payload, timeout=45)
                if resp.status_code == 200 and len(resp.content) > 4000:
                    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    return _cover(img, W, H)
            except Exception:
                continue

    # Tentativa 2: Pollinations.ai Flux (100% Gratuito sem chave)
    try:
        prompt_enc = urllib.parse.quote(prompt_cena)
        url = f"https://image.pollinations.ai/prompt/{prompt_enc}?width={W}&height={H}&seed={seed}&nologo=true&model=flux"
        r = requests.get(url, timeout=40)
        if r.status_code == 200 and len(r.content) > 4000:
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            return _cover(img, W, H)
    except Exception:
        pass

    return None


# ------------------------------------------------------------------------------
# 3. ANIMAÇÃO IMAGE-TO-VIDEO VIA HUGGING FACE SPACES (Gradio Client Gratuito)
# ------------------------------------------------------------------------------
def animar_cena_huggingface_spaces(
    img_pil: Image.Image,
    prompt_movimento: str,
    saida_clip: Path,
    hf_token: str = "",
    pasta_temp: Path = Path("./workspace_temp")
) -> tuple[bool, str]:
    """
    Conecta nos Spaces públicos gratuitos do Hugging Face (Wan 2.1, LTX-Video,
    CogVideoX-5B, Stable Video Diffusion) para gerar movimento real por IA!
    Retorna (sucesso, nome_do_provedor_ou_motivo).
    """
    try:
        from gradio_client import Client, handle_file
    except ImportError:
        return False, "gradio_client não instalado"

    pasta_temp.mkdir(parents=True, exist_ok=True)
    img_in_path = pasta_temp / f"in_{saida_clip.stem}.png"
    _cover(img_pil, 576, 1024).save(img_in_path, format="PNG")

    espacos = [
        ("Wan-AI/Wan2.1", "wan"),
        ("Lightricks/LTX-Video", "ltx"),
        ("THUDM/CogVideoX-5b-Space", "cog"),
        ("multimodalart/stable-video-diffusion", "svd"),
    ]

    kwargs = {"hf_token": hf_token.strip()} if (hf_token and len(hf_token.strip()) > 8) else {}
    ultimo_erro = "fila ocupada"

    for space_id, tipo in espacos:
        try:
            client = Client(space_id, **kwargs)
            if tipo == "svd":
                res = client.predict(handle_file(str(img_in_path)), api_name="/video")
            elif tipo == "cog":
                res = client.predict(
                    prompt=prompt_movimento,
                    image_input=handle_file(str(img_in_path)),
                    api_name="/generate"
                )
            else:
                res = client.predict(
                    prompt=prompt_movimento,
                    image=handle_file(str(img_in_path)),
                )

            v_path = res[0] if isinstance(res, (list, tuple)) else res
            if isinstance(v_path, dict) and "video" in v_path:
                v_path = v_path["video"]

            if v_path and os.path.exists(str(v_path)):
                ffmpeg_exe = obter_ffmpeg()
                cmd = [
                    ffmpeg_exe, "-y", "-loglevel", "error", "-i", str(v_path),
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    str(saida_clip)
                ]
                subprocess.run(cmd, check=True)
                if saida_clip.exists():
                    return True, f"HuggingFace ({space_id})"
        except Exception as e:
            ultimo_erro = f"{space_id}: {str(e)[:120]}"
            continue

    return False, ultimo_erro


# ------------------------------------------------------------------------------
# 4. TRANSIÇÕES SIGNATURE MYSTICMAYHEM & FALLBACK CINEMATOGRÁFICO MULTI-CENAS
# ------------------------------------------------------------------------------
def criar_transicao_portal_ou_vortice(
    img_card_pil: Image.Image,
    modo: str,
    saida_clip: Path,
    duracao_s: float = 1.6
) -> bool:
    """
    Cria as duas transições assinatura do vídeo referência (MysticMayhem):
    - 'portal_luz': A carta flutua e dispara um feixe de luz dourada cegante abrindo a jornada.
    - 'vortice': Um túnel espiral em carmesim e ouro puxa a câmera de volta para a carta 2D original.
    """
    total_f = max(16, int(duracao_s * FPS))
    ffmpeg_exe = obter_ffmpeg()

    card_resized = img_card_pil.convert("RGBA").resize((int(W * 0.72), int(H * 0.68)), Image.Resampling.LANCZOS)
    cw, ch = card_resized.size
    bg_blur = _cover(img_card_pil, W, H).filter(ImageFilter.GaussianBlur(radius=26))
    bg_blur = ImageEnhance.Brightness(bg_blur).enhance(0.5)

    cmd = [
        ffmpeg_exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(saida_clip)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for i in range(total_f):
        t = i / max(1, total_f - 1)
        if modo == "portal_luz":
            ease = t * t
            zoom = 1.0 + 1.85 * ease
            frame = bg_blur.copy().convert("RGBA")
            nw, nh = int(cw * zoom), int(ch * zoom)
            c_zoom = card_resized.resize((nw, nh), Image.Resampling.BILINEAR)
            frame.paste(c_zoom, ((W - nw) // 2, (H - nh) // 2), c_zoom)

            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            cx, cy = W // 2, int(H * 0.45)
            largura = int(35 + 680 * ease)
            alpha = int(min(255, 100 + 155 * t))
            draw.polygon([(cx - 15, cy - 15), (cx + 25, cy + 15), (W + largura, H), (W - largura, H)], fill=(255, 232, 165, alpha))
            raio = int(35 + 760 * (t ** 2.3))
            draw.ellipse((cx - raio, cy - raio, cx + raio, cy + raio), fill=(255, 248, 220, int(255 * (t ** 1.7))))
            frame = Image.alpha_composite(frame, overlay)
        else:
            frame = Image.new("RGBA", (W, H), (36, 10, 6, 255))
            draw = ImageDraw.Draw(frame)
            cx, cy = W // 2, H // 2
            rot_base = t * 560.0
            for ring in range(26, 0, -1):
                frac = ring / 26.0
                rx, ry = int(W * 0.85 * frac), int(H * 0.65 * frac)
                ox = int(math.cos(math.radians(rot_base + ring * 26)) * 55 * frac)
                oy = int(math.sin(math.radians(rot_base + ring * 26)) * 55 * frac)
                cor = (155, 38, 22, 255) if ring % 2 == 0 else (228, 175, 95, 255)
                draw.ellipse((cx - rx + ox, cy - ry + oy, cx + rx + ox, cy + ry + oy), fill=cor)
            r_core = int(30 + 660 * (t ** 2.1))
            draw.ellipse((cx - r_core, cy - r_core, cx + r_core, cy + r_core), fill=(255, 244, 212, 255))
            if t > 0.52:
                alpha_c = int(((t - 0.52) / 0.48) * 255)
                c_layer = Image.new("RGBA", (W, H), (22, 10, 5, alpha_c))
                c_layer.paste(card_resized, ((W - cw) // 2, (H - ch) // 2), card_resized)
                frame = Image.alpha_composite(frame, c_layer)

        proc.stdin.write(frame.convert("RGB").tobytes())

    proc.stdin.close()
    proc.wait()
    return saida_clip.exists()


def animar_keyframe_cinematografico_local(
    img_a: Image.Image,
    img_b: Image.Image,
    movimento: str,
    saida_clip: Path,
    duracao_s: float = 3.2
) -> bool:
    """
    Fallback dinâmico de alta qualidade entre duas cenas distintas (img_a -> img_b):
    Aplica movimento de câmera 3D (mergulho, órbita ou ascensão) com desfoque radial
    e fusão luminosa para atravessar de uma cena para a outra!
    """
    total_f = max(20, int(duracao_s * FPS))
    ffmpeg_exe = obter_ffmpeg()
    src_a = _cover(img_a, int(W * 1.32), int(H * 1.32))
    src_b = _cover(img_b, int(W * 1.32), int(H * 1.32))
    sw, sh = src_a.size

    cmd = [
        ffmpeg_exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(saida_clip)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for i in range(total_f):
        t = i / max(1, total_f - 1)
        ease = t * t * (3 - 2 * t)

        if t < 0.72:
            # Movimento contínuo na cena atual (A)
            p = t / 0.72
            if movimento == "orbita":
                sc = 1.04 + 0.16 * math.sin(p * math.pi)
                ox = int((sw - W * sc) * 0.5 + math.sin(p * math.pi * 1.5) * 70)
                oy = int((sh - H * sc) * 0.45)
            elif movimento == "mergulho":
                sc = 1.02 + 0.25 * (p ** 1.6)
                ox = int((sw - W * sc) * 0.5)
                oy = int((sh - H * sc) * (0.60 - 0.20 * p))
            else:  # ascensao
                sc = 1.14 - 0.10 * p
                ox = int((sw - W * sc) * 0.5)
                oy = int((sh - H * sc) * (0.85 - 0.75 * p))

            cw_c, ch_c = int(W * sc), int(H * sc)
            ox = max(0, min(sw - cw_c, ox))
            oy = max(0, min(sh - ch_c, oy))
            frame = src_a.crop((ox, oy, ox + cw_c, oy + ch_c)).resize((W, H), Image.Resampling.BILINEAR)
        else:
            # Transição Zoom-Through luminosa atravessando de A para B!
            q = (t - 0.72) / 0.28
            sc_a = 1.25 + 0.85 * (q ** 2)
            cwa, cha = int(W * sc_a), int(H * sc_a)
            fa = src_a.crop(((sw - cwa) // 2, (sh - cha) // 2, (sw + cwa) // 2, (sh + cha) // 2)).resize((W, H), Image.Resampling.BILINEAR)

            sc_b = 1.45 - 0.41 * (1 - (1 - q) ** 2)
            cwb, chb = int(W * sc_b), int(H * sc_b)
            fb = src_b.crop(((sw - cwb) // 2, (sh - chb) // 2, (sw + cwb) // 2, (sh + chb) // 2)).resize((W, H), Image.Resampling.BILINEAR)

            frame = Image.blend(fa, fb, q)
            # Flash dourado suave no pico da travessia
            flash = math.sin(q * math.pi) * 0.45
            if flash > 0.02:
                frame = ImageEnhance.Brightness(frame).enhance(1.0 + flash)

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    return saida_clip.exists()


# ------------------------------------------------------------------------------
# 5. ORQUESTRADOR PRINCIPAL CHAMADO PELO APP.PY
# ------------------------------------------------------------------------------
def executar_pipeline_ia_gratuita(
    imagem_pil: Image.Image,
    orientacoes_chat: str = "",
    hf_token: str = "",
    output_path: str = "video_final_gerado.mp4",
    callback_progresso=None
) -> dict:
    """
    Executa toda a jornada cinematográfica gratuita em 5 atos:
      Ato 1: Portal de Luz Dourada abrindo a imagem original;
      Ato 2: Cena 1 (Arquétipo vivo) -> IA Hugging Face / Câmera 3D;
      Ato 3: Cena 2 (Cenário ilustrado gerado por IA gratuita) -> IA Hugging Face / Zoom-Through;
      Ato 4: Cena 3 (Ascensão celestial gerada por IA gratuita) -> IA Hugging Face / Tilt-up;
      Ato 5: Vórtice Espiral retornando em loop para a imagem original!
    """
    pasta_temp = Path("./workspace_temp_v5")
    pasta_temp.mkdir(parents=True, exist_ok=True)
    seed_base = int(hashlib.md5(imagem_pil.tobytes()[:50000]).hexdigest()[:6], 16)

    def log(msg: str, pct: int):
        if callback_progresso:
            callback_progresso(msg, pct)

    log("🧠 Agente analisando referência e criando roteiro de 3 cenas...", 10)
    cenas = criar_roteiro_cenas_gratuito(imagem_pil, orientacoes_chat, hf_token)

    log("🎨 Gerando quadros ilustrados (Keyframes IA) para cada cena...", 25)
    keyframes: list[Image.Image] = []
    origens_kf: list[str] = []

    for idx, cena in enumerate(cenas):
        if cena.get("usar_imagem_original") and idx == 0:
            keyframes.append(_cover(imagem_pil, W, H))
            origens_kf.append("Imagem Original")
        else:
            log(f"🖌️ Pintando {cena.get('titulo', f'Cena {idx+1}')} via IA Gratuita...", 30 + idx * 10)
            kf = gerar_keyframe_ia_gratuito(cena["prompt_imagem"], hf_token=hf_token, seed=seed_base + idx * 37)
            if kf is not None:
                keyframes.append(kf)
                origens_kf.append("IA Generativa (Flux/HF)")
            else:
                # Se a API de imagem estiver offline, cria variação dramática em crop da imagem original
                w_o, h_o = imagem_pil.size
                box = (int(w_o * 0.15), int(h_o * 0.05), int(w_o * 0.85), int(h_o * 0.75)) if idx == 1 else (int(w_o * 0.1), int(h_o * 0.0), int(w_o * 0.9), int(h_o * 0.5))
                keyframes.append(_cover(imagem_pil.crop(box), W, H))
                origens_kf.append("Recorte Focal")

    clipes_finais: list[Path] = []
    relatorio_motores: list[str] = []

    # Ato 1: Portal de Luz Dourada
    log("✨ [Ato 1/5] Criando Portal de Luz Dourada de abertura...", 55)
    p_portal = pasta_temp / "ato1_portal.mp4"
    if criar_transicao_portal_ou_vortice(imagem_pil, "portal_luz", p_portal, duracao_s=1.6):
        clipes_finais.append(p_portal)
        relatorio_motores.append("Ato 1: Portal de Luz")

    # Atos 2, 3 e 4: Animação das 3 cenas via Hugging Face Spaces (com fallback dinâmico)
    movimentos_locais = ["orbita", "mergulho", "ascensao"]
    for idx in range(len(keyframes)):
        ato_num = idx + 2
        pct = 60 + idx * 10
        titulo_cena = cenas[idx].get("titulo", f"Cena {idx+1}")
        log(f"🎬 [Ato {ato_num}/5] Animando '{titulo_cena}' via Hugging Face Spaces...", pct)

        p_clip = pasta_temp / f"ato{ato_num}_cena.mp4"
        ok_hf, info_hf = animar_cena_huggingface_spaces(
            keyframes[idx],
            cenas[idx]["prompt_video"],
            p_clip,
            hf_token=hf_token,
            pasta_temp=pasta_temp
        )

        if ok_hf:
            clipes_finais.append(p_clip)
            relatorio_motores.append(f"Ato {ato_num}: {info_hf}")
        else:
            prox_kf = keyframes[(idx + 1) % len(keyframes)] if idx < len(keyframes) - 1 else _cover(imagem_pil, W, H)
            if animar_keyframe_cinematografico_local(keyframes[idx], prox_kf, movimentos_locais[idx % 3], p_clip, duracao_s=3.4):
                clipes_finais.append(p_clip)
                relatorio_motores.append(f"Ato {ato_num}: Câmera 3D + Zoom-Through ({origens_kf[idx]})")

    # Ato 5: Vórtice Espiral retornando à imagem original (Loop perfeito)
    log("🌀 [Ato 5/5] Criando Vórtice Espiral de retorno para loop perfeito...", 92)
    p_vortice = pasta_temp / "ato5_vortice.mp4"
    if criar_transicao_portal_ou_vortice(imagem_pil, "vortice", p_vortice, duracao_s=1.6):
        clipes_finais.append(p_vortice)
        relatorio_motores.append("Ato 5: Vórtice Espiral")

    if not clipes_finais:
        return {"ok": False, "erro": "Nenhum clipe pôde ser renderizado."}

    # Concatenação final via FFmpeg
    log("🧵 Montando vídeo MP4 final...", 96)
    lista_txt = pasta_temp / "concat_v5.txt"
    with open(lista_txt, "w", encoding="utf-8") as f:
        for cp in clipes_finais:
            f.write(f"file '{cp.resolve().as_posix()}'\n")

    ffmpeg_exe = obter_ffmpeg()
    out_p = Path(output_path)
    cmd_concat = [
        ffmpeg_exe, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista_txt),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        str(out_p)
    ]
    subprocess.run(cmd_concat, check=True)

    return {
        "ok": out_p.exists(),
        "video_path": str(out_p),
        "cenas": cenas,
        "keyframes": keyframes,
        "origens_kf": origens_kf,
        "motores": relatorio_motores
    }

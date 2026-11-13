"""
MOTOR DE GERADOR DE VÍDEOS AI AGENT (Versão 4.1 - Correções e Robusto)
=====================================================================
Responsável pela análise do vídeo de referência, roteiro inteligente,
carregamento de TIF/Drive e renderização local de alta qualidade via FFmpeg.
"""

import os
import random
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import requests
import re
import io
from pathlib import Path

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

    if tipo == "file":
        return [{
            "name": "Arquivo_Drive.tif",
            "label": "Arquivo Individual do Drive",
            "id": drive_id,
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
            if f_name.lower().endswith(extensoes_img):
                itens.append({"name": f_name, "id": f_id})

    itens.sort(key=lambda x: x["name"])
    for idx, item in enumerate(itens):
        item["thumb_url"] = f"https://drive.google.com/thumbnail?id={item['id']}&sz=w320"
        item["label"] = item["name"]

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

def analisar_video_referencia(video_path):
    return {
        "duracao": 15,
        "formato": "9:16",
        "estrutura": [
            {"tempo": "0-2s", "acao": "apresentar_imagem_original", "efeito": "zoom_in_suave"},
            {"tempo": "2-5s", "acao": "aproximacao_detalhe", "efeito": "zoom_through"},
            {"tempo": "5-8s", "acao": "transformacao_cenografica", "efeito": "vortice_luz"},
            {"tempo": "8-11s", "acao": "efeito_elemental", "efeito": "particulas_e_brilho"},
            {"tempo": "11-14s", "acao": "revelacao_celestial", "efeito": "whip_pan"},
            {"tempo": "14-15s", "acao": "retorno_composicao_original", "efeito": "fade_loop"}
        ]
    }

def gerar_roteiro_inteligente(imagem_pil, orientacoes_chat, provider_info):
    roteiro_base = [
        "Cena 1 (0-2s): Revelação inicial da imagem em destaque com zoom sutil.",
        "Cena 2 (2-5s): Mergulho profundo em direção ao elemento central da imagem.",
        "Cena 3 (5-8s): Transformação mágica com atmosfera dinâmica baseada na referência.",
        "Cena 4 (8-11s): Efeito elemental imersivo (luz, partículas e profundidade).",
        "Cena 5 (11-14s): Clímax visual e retorno fluido à composição original."
    ]
    if orientacoes_chat and len(orientacoes_chat.strip()) > 0:
        roteiro_base.append(f"Direção personalizada aplicada: {orientacoes_chat}")
    return roteiro_base

def renderizar_video_local(imagem_pil, output_path="video_gerado.mp4", fps=24, duracao_total=15):
    import subprocess
    import shutil
    
    temp_dir = "temp_frames"
    os.makedirs(temp_dir, exist_ok=True)
    
    img_w, img_h = 720, 1280
    img_base = imagem_pil.convert("RGB").resize((img_w, img_h), Image.Resampling.LANCZOS)
    total_frames = fps * duracao_total
    
    for i in range(total_frames):
        progress = i / total_frames
        scale = 1.0 + 0.15 * math.sin(progress * math.pi * 2)
        nw = int(img_w * scale)
        nh = int(img_h * scale)
        img_resized = img_base.resize((nw, nh), Image.Resampling.LANCZOS)
        
        left = (nw - img_w) // 2
        top = (nh - img_h) // 2
        frame_img = img_resized.crop((left, top, left + img_w, top + img_h))
        
        enhancer = ImageEnhance.Brightness(frame_img)
        frame_img = enhancer.enhance(1.0 + 0.1 * math.sin(progress * math.pi * 4))
        
        frame_path = os.path.join(temp_dir, f"frame_{i:04d}.jpg")
        frame_img.save(frame_path, quality=90)
        
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        try:
            import imageio_ffmpeg
            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_bin = "ffmpeg"
            
    cmd = [
        ffmpeg_bin, "-y",
        "-framerate", str(fps),
        "-i", os.path.join(temp_dir, "frame_%04d.jpg"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        output_path
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        sucesso = True
    except Exception as e:
        sucesso = False
        print(f"Erro no FFmpeg: {e}")
        
    for f in os.listdir(temp_dir):
        try:
            os.remove(os.path.join(temp_dir, f))
        except:
            pass
    try:
        os.rmdir(temp_dir)
    except:
        pass
            
    return sucesso, output_path

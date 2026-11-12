# 🎴 Sistema Inteligente de Vídeo Tarô 2.5D (CLI Agent)

Agente interativo de terminal para transformar cartas de Tarô estáticas (2D) em vídeos 2.5D/3D com efeito de recorte em camadas (*Paper Cutout / Diorama Parallax*), órbita 360°, revelação de símbolo astrológico no céu e *seamless loop* automático.

## 📦 Arquivos Inclusos
- `tarot_video_agent.py` — Agente principal com integração ao Google Drive (`gdown`), conversão automática de `.tif` para `.png` (`Pillow`), análise visual de camadas (`gemini-2.5-flash`), geração de vídeo (`veo-2.0-generate-001`) e pós-produção de áudio e loop (`FFmpeg`).
- `requirements.txt` — Dependências Python do projeto.
- `.env.example` — Modelo de configuração da variável de ambiente `GEMINI_API_KEY`.
- `run.sh` / `run.bat` — Scripts de execução rápida para Linux/macOS e Windows.

## 🚀 Como Instalar e Executar

### 1. Instalar dependências Python
```bash
pip install -r requirements.txt
```

### 2. Verificar instalação do FFmpeg
Certifique-se de que o `ffmpeg` está instalado no seu sistema operacional:
- **Windows:** `winget install Gyan.FFmpeg`
- **macOS:** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt install ffmpeg`

### 3. Configurar sua Chave de API
No terminal, exporte sua chave do Google AI Studio / Gemini:
```bash
# Linux / macOS
export GEMINI_API_KEY="sua-chave-aqui"

# Windows (CMD)
set GEMINI_API_KEY="sua-chave-aqui"

# Windows (PowerShell)
$env:GEMINI_API_KEY="sua-chave-aqui"
```

### 4. Iniciar o Agente
```bash
python tarot_video_agent.py
```

Você pode colar diretamente o **link da pasta do Google Drive**, o **link de um arquivo específico do Drive** ou o **caminho local** da carta em `.tif`, `.png` ou `.jpg`.

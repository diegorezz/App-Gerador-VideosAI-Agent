# 🎴 Tarot Video Studio 2.5D — Edição Gratuita (GitHub + Streamlit Cloud)

Repositório conectado ao app online: **`https://app-oraculo-agent-gerador.streamlit.app`**

---

## ✅ O que foi resolvido nesta versão:
1. **Motor 2.5D Diorama Parallax 100% Gratuito:** Não precisa mais pagar pela API do Google Veo! A análise usa o **Gemini 2.5 Flash (Gratuito)** e a geração do vídeo usa o **Motor 2.5D Nativo** integrado ao app (que recorta a carta em camadas Z-space, aplica o giro orbital 360° estilo *Paper Cutout*, adiciona partículas místicas, sobe a câmera para o céu noturno revelando o símbolo astrológico e faz o loop reverso para a carta 2D).
2. **FFmpeg 100% Ativo no Streamlit Cloud:** Adicionado o arquivo `packages.txt` (que instala o FFmpeg no servidor Linux da nuvem) + `imageio-ffmpeg` no `requirements.txt` (que garante o binário do FFmpeg mesmo sem configuração externa).

---

## 🚀 Passo a Passo Rápido para Atualizar seu App no GitHub

Sempre que você enviar ou editar os arquivos diretamente no seu repositório (`https://github.com/diegorezz/App-Gerador-VideosAI-Agent`), o seu site no Streamlit atualiza sozinho em menos de 1 minuto!

1. Abra o seu repositório no GitHub: **`https://github.com/diegorezz/App-Gerador-VideosAI-Agent`**
2. Clique em **Add file** -> **Upload files**.
3. Arraste para lá os arquivos desta pasta:
   - `packages.txt` *(Essencial para ativar o FFmpeg no servidor)*
   - `requirements.txt` *(Com as bibliotecas gratuitas de vídeo)*
   - `app.py` *(Com o novo Motor 2.5D Gratuito)*
   - `.streamlit/config.toml` *(Tema visual)*
4. Clique no botão verde **Commit changes**.
5. Caso o aviso do FFmpeg ainda apareça no seu app aberto, clique no botão **`< Manage app`** (no canto inferior direito da tela do Streamlit), clique nos **três pontinhos (`⋮`)** e escolha **Reboot app**. O status mudará imediatamente para **`✅ FFmpeg Ativo (Loop 16s + Áudio Habilitados)`**!

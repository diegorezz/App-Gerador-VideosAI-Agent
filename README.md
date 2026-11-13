# 🎬 AI Video Agent v5 — Estratégia Hugging Face & IA Gratuita Multi-Cenas

Aplicativo Streamlit para compor e animar vídeos multi-cenas em formato vertical (`9:16`) para redes sociais de forma **100% gratuita**, replicando a estética de transição dinâmica (Portal de Luz → Cenas Ilustradas → Vórtice Espiral em Loop).

## Como funciona a Estratégia de IA Gratuita:
1. **Roteiro Inteligente (LLM Gratuito)**: O Agente interpreta suas orientações no chat e estrutura 3 atos distintos (Despertar do Elemento Central → Mergulho no Cenário → Ascensão Celestial).
2. **Composição de Novas Cenas (FLUX.1 / Pollinations)**: Em vez de apenas dar zoom na mesma imagem parada, o motor pinta quadros-chave inéditos em `9:16` usando **Hugging Face Inference API (`FLUX.1-schnell`)** ou **Pollinations Flux** gratuitamente.
3. **Animação na Nuvem via Hugging Face Spaces**: Conecta automaticamente nos Spaces gratuitos (**Wan 2.1**, **LTX-Video**, **CogVideoX-5B** e **Stable Video Diffusion**) via `gradio_client` para gerar movimento real por IA.
4. **Transições Signature & Contingência Cinematográfica**: Abre com **Portal de Luz Dourada**, atravessa entre as cenas com **Zoom-Through luminoso** (caso alguma fila pública do Hugging Face esteja cheia no momento) e fecha com o **Vórtice Espiral** de volta à imagem original (loop perfeito).

## Dica para Melhorar a Prioridade no Hugging Face (Grátis):
- Crie uma conta gratuita em [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens), gere um token (`Read`) começando com `hf_...` e cole na barra lateral do aplicativo.

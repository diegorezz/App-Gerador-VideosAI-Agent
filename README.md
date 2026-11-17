# 🎴 ORÁCULO · Gerador de Vídeos v6

App Streamlit que gera vídeos de **20 segundos, 9:16, com áudio**, a partir dos 22 arcanos maiores.
Motor próprio: **custo zero por vídeo**, sem chave de API, sem fila de GPU.

---

## O que mudou em relação à v5

A versão anterior tentava terceirizar a animação para modelos de vídeo (Hugging Face Spaces, Veo).
Isso falhava por três motivos estruturais:

| Problema na v5 | Situação na v6 |
|---|---|
| Spaces públicos com API instável e fila ZeroGPU | **Não usa Spaces.** Motor 100% local |
| `veo-2.0-generate-001` descontinuado | **Nenhuma dependência de API** |
| Veo entrega 8s, o vídeo é de 20s | **20s exatos, em uma única renderização** |
| Efeitos calibrados à mão para uma carta | **Analisador automático por arcano** |

A descoberta central: o vídeo modelo do Drive **não é geração de vídeo por IA** — é
composição cinematográfica em camadas (profundidade, câmera, luz, partículas). Isso é
determinístico, gratuito e reproduzível nos 22 arcanos.

---

## Como usar

1. Envie a imagem do arcano (`.png`, `.jpg`, `.tif`).
2. Clique em **Analisar arcano** — o motor lê geometria, paleta, profundidade e o rosto.
3. Clique em **GERAR VÍDEO**.

O agente decide sozinho o efeito elemental (fogo / água / luz / terra / ar) a partir da
paleta da carta, o foco da câmera, o ritmo e a trilha. Você não escolhe motor nem efeito.

**Tempo de geração:** ~2 min a 540×960 · ~5 min a 720×1280 (Streamlit Cloud, 1 vCPU)

---

## Deploy no Streamlit Cloud

### 1. Suba os arquivos no GitHub

A estrutura precisa ser exatamente esta:

```
seu-repo/
├── app.py                    ← main file
├── requirements.txt
├── packages.txt
├── README.md
├── .streamlit/
│   └── config.toml
└── engine/
    ├── __init__.py
    ├── analisar_carta.py
    ├── audio.py
    └── v6.py
```

> **Atenção:** a pasta `engine/` é obrigatória. Sem ela o app quebra na primeira linha de import.

### 2. Aponte o Streamlit Cloud para o repo

Em [share.streamlit.io](https://share.streamlit.io/):
- **Main file path:** `app.py`
- **Python version:** `3.11`
- **Advanced settings → Secrets:** cole o conteúdo de `.streamlit/secrets.toml.example`

### 3. (Opcional) Listar as cartas do Drive

No arquivo de Secrets, adicione:

```toml
ARCANOS_JSON = '{
  "LE MAT": "1u056VmsEiw2jw3rWX9vTDNh_HRAMhocS",
  "LE BATELEUR": "1mvX-9sjpCiJ7tulHwH7UylhUZdo0hLAz",
  "LA PAPESSE": "13-owBCg6HVWPp9DTKPKoiOwt3goLDAdm",
  "L IMPERATRICE": "1Zbs1ATYnUlN81dxfSkHbfs0hfio7jy-S",
  "L EMPEREUR": "1H3JWYic-9QxHv1MpiICuzYq9uxy7of7b",
  "LE PAPE": "1WZk-n207dj3VoRBsHyfc1NzoYbpBGSRd",
  "L AMOUREUX": "1z02eKNerM9q6CeuZ6LuEce3RBcidFHZg",
  "LE CHARIOT": "1nVaJihwHMBabQakgsDbwZ9zjGIiJ7Jof",
  "LA JUSTICE": "1vSwJbqlabrMXixIss7qw959691_HB42R",
  "LE PENDU": "1-9oSxIbsweV9WHlc7ZO6HnFVJv1dQovt",
  "LA MORT": "1n2OZNnQzrSAfHiJXiKnczgotbtEKqz5o",
  "TEMPERANCE": "1sII92SbIqdIKUrqO3MhsTnozGVdoZ6jH",
  "LE DIABLE": "1R3I2xmnWrOWWNur4yI-00P5b6guUWURS",
  "LA TOUR": "1xbtm7y1NFwopp99rT8TcDQI5sYS3-E_9"
}'
```

As cartas do Drive precisam estar compartilhadas como "qualquer pessoa com o link".

---

## Arquitetura do motor

```
engine/analisar_carta.py     ← lê a carta, sem coordenada fixa
        │
        ├── geometria (bbox, linha do rótulo, piso)
        ├── paleta dominante (k-means, 8 cores)
        ├── mapa de profundidade (saturação + tinta + posição + saliência)
        ├── rosto (máscara de pele + validação geométrica do blob)
        └── elemento narrativo (decidido pela paleta)

engine/v6.py                 ← a cena
        ├── Ruido              bancos fbm animados
        ├── Elemento           fogo / água / luz / terra / ar
        ├── Cena               montanhas, neblina, sol, estrelas, partículas
        ├── Roteiro            curvas de 20s (ritmo editável em um lugar só)
        ├── camera()           push-in no foco → efeito → saída → celestial → retorno
        ├── warp_full()        projeção + paralaxe por profundidade (numba)
        └── MotorV6            render_frame / render_video

engine/audio.py              ← trilha sintetizada, casada com os tempos
```

### Timeline dos 20s

| Tempo | Ação |
|---|---|
| 0–1,8s | Carta inteira, brilho de verniz varrendo |
| 1,8–4,2s | Push-in no rosto/foco, paralaxe, poeira dourada |
| 4,2–6,9s | Efeito elemental nasce da base da carta, onda de calor, tremor |
| 6,9–9,2s | Dolly-out com dissolução em brasas |
| 8,2–13,6s | Revelação celestial: sol com coroa, raios, estrelas |
| 11,4–14,2s | Retorno da carta com luz de contorno |
| 14,2–20s | Assinatura final |

### Como mudar o ritmo

Edite a dataclass `Roteiro` em `engine/v6.py`. Todos os tempos e zooms estão nos campos
`t_push`, `t_elem`, `t_dis`, `t_cel`, `t_volta`, `zoom_foco`, `zoom_elem`, `zoom_fora`.

---

## Validado

O motor foi validado na **carta mais difícil da coleção** — Le Bateleur (mesa, objetos,
figura deslocada). Se funciona nela, funciona nas 22.

Análise automática nas 4 primeiras cartas:

| Arcano | Rosto | Elemento |
|---|---|---|
| I · LE BATELEUR | (0,45 · 0,20) ✓ | fogo |
| II · LA PAPESSE | (0,52 · 0,22) ✓ | fogo |
| III · L'IMPERATRICE | (0,53 · 0,27) ✓ | fogo |
| VIII · LA JUSTICE | (0,50 · 0,21) ✓ | fogo |

Veja `exemplos/exemplo_le_bateleur_20s.mp4` para o resultado da validação.

---

## Custos

| Item | Custo |
|---|---|
| Motor próprio | **R$ 0** |
| Streamlit Cloud (plano gratuito) | **R$ 0** |
| 22 vídeos | **R$ 0** |
| API de IA generativa | **nenhuma** |

O plano gratuito do Streamlit Cloud tem 1 GB de RAM. Um render de 20s em 540×960
usa ~500 MB, com folga. Para 720×1280, prefira uma máquina com 2 GB.

---

## Problemas conhecidos

**`ImportError: Numba needs NumPy 2.4 or less`**
O `requirements.txt` já fixa `numpy<2.5`. Se persistir, limpe o cache do Cloud
(*Manage app → Reboot*).

**Render muito lento**
Reduza `W`/`H` em `app.py` na chamada `MotorV6(card, depth, perfil, W=540, H=960, ...)`.
360×640 gera em ~1 min com qualidade de rascunho.

**Rosto não detectado em alguma carta**
O analisador cai automaticamente para o centro de saliência. O vídeo continua correto,
só o push-in mira outro ponto.

**`ffmpeg not found`**
Confirme que `packages.txt` foi enviado — o Streamlit Cloud instala via apt.

---

## Próximos passos sugeridos

1. **Lote dos 22** — script que lê todos os IDs do Drive e gera em sequência.
2. **Profundidade real** — trocar o mapa heurístico por `Depth Anything V2` (Small roda em CPU).
3. **Segmentação de figura** — `rembg` para separar personagem do fundo e ganhar oclusão real.
4. **Camada generativa opcional** — Kling 2.6 Pro (~US$ 0,47/clipe) para 1 clipe de virada por vídeo.

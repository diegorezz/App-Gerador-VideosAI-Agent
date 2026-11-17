# 🎴 ORÁCULO · Gerador de Vídeos v6

App Streamlit que gera vídeos de **20 segundos, 9:16, com áudio**, a partir dos **22 arcanos maiores**.
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

### Modo 1 · Um arcano
1. Escolha **Enviar do computador** ou **Escolher do catálogo** (os 22 já vêm com ID do Drive).
2. Clique em **Analisar arcano**.
3. Escolha a resolução e clique em **GERAR VÍDEO**.

### Modo 2 · Lote dos 22
1. Aba **⚡ Lote dos 22**.
2. Marque os arcanos (ou use *Selecionar todos*).
3. Clique em **GERAR N VÍDEO(S)**.
4. Ao final, baixe tudo em um **único .zip**.

O agente decide o efeito elemental pela correspondência hermética do arcano:

| Elemento | Arcanos |
|---|---|
| **fogo** | I Bateleur · IV Empereur · X Roue · XI Force · XIV Temperance · XVI Maison Dieu · XX Jugement |
| **água** | II Papesse · VII Chariot · XII Pendu · XIII Arcane sans Nom · XVIII Lune |
| **luz** | XIX Soleil |
| **terra** | III Imperatrice · V Pape · IX Ermite · XV Diable · XXI Monde |
| **ar** | 0 Mat · VI Amoureux · VIII Justice · XVII Etoile |

---

## Deploy no Streamlit Cloud

### 1. Estrutura do repositório

```
seu-repo/
├── app.py                    ← main file
├── requirements.txt
├── packages.txt
├── README.md
├── .streamlit/
│   └── config.toml
├── exemplos/
│   └── exemplo_le_bateleur_20s.mp4
└── engine/
    ├── __init__.py
    ├── analisar_carta.py
    ├── arcanos.py            ← catálogo: número, nome, elemento, ID do Drive
    ├── audio.py
    ├── lote.py               ← gerador em lote
    └── v6.py
```

> **Atenção:** a pasta `engine/` é obrigatória. Sem ela o app quebra no primeiro import.

### 2. Configuração

Em [share.streamlit.io](https://share.streamlit.io/):
- **Main file path:** `app.py`
- **Python version:** `3.11`

Os 22 IDs do Drive **já vêm embutidos** em `engine/arcanos.py`. Secrets é opcional.

### 3. Compartilhamento do Drive

A pasta dos arcanos precisa estar como **"qualquer pessoa com o link"**. Sem isso o
download falha (o app avisa quando recebe menos de 20 KB).

---

## Arquitetura do motor

```
engine/analisar_carta.py     ← lê a carta, sem coordenada fixa
        ├── geometria (bbox, linha do rótulo, piso)
        ├── paleta dominante (k-means, 8 cores)
        ├── mapa de profundidade (saturação + tinta + posição + saliência)
        ├── rosto (máscara de pele + validação geométrica do blob)
        └── elemento narrativo (fallback quando não há catálogo)

engine/arcanos.py            ← catálogo hermético dos 22 + IDs do Drive

engine/v6.py                 ← a cena
        ├── Ruido              bancos fbm animados
        ├── Elemento           fogo / água / luz / terra / ar
        ├── Cena               montanhas, neblina, sol, estrelas, partículas
        ├── Roteiro            curvas de 20s (ritmo editável em um lugar só)
        ├── camera()           push-in no foco → efeito → saída → celestial → retorno
        ├── warp_full()        projeção + paralaxe por profundidade (numba)
        └── MotorV6            render_frame / render_video

engine/audio.py              ← trilha sintetizada, casada com os tempos
engine/lote.py               ← orquestra download → análise → render → áudio → MP4
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

## Rodar localmente (recomendado para gerar os 22 em qualidade final)

O plano gratuito do Streamlit Cloud tem 1 vCPU e **limite de execução**. Para os 22 em
720×1280, rode na sua máquina:

```bash
pip install -r requirements.txt

# os 22 em qualidade final
python -m engine.lote --todos --res 720x1280 --saida ./videos

# apenas alguns
python -m engine.lote --numeros 0 1 16 --res 540x960

# a partir de uma pasta local (evita download)
python -m engine.lote --todos --arquivo ./arcanos_tif --res 720x1280
```

Saída por arcano: `NN_nome_20s.mp4`, `NN_nome_trilha.wav` e `NN_nome.json` (metadados).

---

## Validado

O motor foi validado em **três cartas estruturalmente diferentes**:

| Arcano | Elemento | Estrutura | Resultado |
|---|---|---|---|
| I · Le Bateleur | fogo | mesa + objetos + figura deslocada | ✅ |
| XIX · Le Soleil | luz | duas figuras + sol grande no topo | ✅ |
| XXI · Le Monde | terra | figura central em coroa de louros | ✅ |

O caso do Le Bateleur é o mais difícil da coleção (mesa, copos, dados e punhal atravessando
o quadro). Se funciona nele, funciona nas 22.

Veja `exemplos/exemplo_le_bateleur_20s.mp4`.

---

## Custos

| Item | Custo |
|---|---|
| Motor próprio | **R$ 0** |
| Streamlit Cloud (plano gratuito) | **R$ 0** |
| 22 vídeos | **R$ 0** |
| API de IA generativa | **nenhuma** |

---

## Problemas conhecidos

**`ImportError: Numba needs NumPy 2.4 or less`**
O `requirements.txt` fixa `numpy<2.5`. Se persistir: *Manage app → Reboot*.

**Render muito lento ou app reinicia no lote**
Limite do Streamlit Cloud. Use 360×640 no lote pela web, ou rode localmente.

**`ffmpeg not found`**
Confirme que `packages.txt` foi enviado — o Cloud instala via apt.

**Rosto não detectado em alguma carta**
O analisador cai automaticamente para o centro de saliência. O vídeo continua correto,
só o push-in mira outro ponto.

**Download do Drive falha**
A pasta precisa estar pública com link. Verifique em `engine/arcanos.py` se o ID confere.

---

## Próximos passos sugeridos

1. **Profundidade real** — trocar o mapa heurístico por `Depth Anything V2` (Small roda em CPU,
   +400 MB no deploy).
2. **Segmentação de figura** — `rembg` para separar personagem do fundo e ganhar oclusão real.
3. **Camada generativa opcional** — Kling 2.6 Pro (~US$ 0,47/clipe) para 1 clipe de virada por vídeo.
4. **Música adaptativa** — hoje a trilha é sintetizada por elemento; poderia usar biblioteca de samples.

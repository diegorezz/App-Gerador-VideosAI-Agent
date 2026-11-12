# 🎴 Guia Passo a Passo — Tarot Video Studio 2.5D (Para Não-Desenvolvedores)

Bem-vindo ao **Tarot Video Studio 2.5D**! Este sistema foi empacotado como um **Aplicativo Visual de Navegador** para que qualquer pessoa consiga transformar cartas estáticas em vídeos 2.5D/3D sem precisar digitar códigos ou usar o terminal.

---

## 🛠️ Etapa Única de Preparação (Só precisa fazer na 1ª vez)

### 1. Instalar o Python (Motor base gratuito)
Se o computador ainda não tiver o Python instalado:
- **No Windows:** Baixe em [python.org/downloads](https://www.python.org/downloads/). **MUITO IMPORTANTE:** Na primeira tela do instalador, marque a caixinha **"Add Python to PATH"** antes de clicar em "Install Now".
- **No Mac:** Já vem instalado na maioria dos Macs, ou baixe em [python.org/downloads](https://www.python.org/downloads/).

### 2. Pegar sua Chave de Inteligência Artificial do Google
1. Acesse [aistudio.google.com/apikey](https://aistudio.google.com/apikey) e entre com sua conta Google.
2. Clique no botão azul **"Create API key"**.
3. Copie o código gerado (ele começa com `AIza...`).
*(Nota: Para habilitar a geração do vídeo final em MP4 com o motor Veo, clique em "Set up Billing" ao lado da chave no site do Google para ativar a conta de faturamento).*

---

## 🚀 Como Abrir e Usar o Aplicativo no Dia a Dia

### Passo 1: Dar dois cliques no Inicializador
Abra a pasta onde você extraiu este arquivo `.zip`:
- **Se estiver no Windows:** Dê dois cliques no arquivo **`INICIAR_APLICATIVO_WINDOWS.bat`**.
- **Se estiver no Mac ou Linux:** Dê dois cliques no arquivo **`INICIAR_APLICATIVO_MAC_LINUX.command`**.

> O sistema vai instalar tudo sozinho em alguns segundos e **abrirá automaticamente uma aba no seu navegador** (Chrome, Edge ou Safari) com a plataforma pronta!

### Passo 2: Colar sua Chave na Barra Lateral
- Na barra lateral esquerda do aplicativo, cole a sua chave `AIza...` no campo **"Chave da API Google Gemini"**.
- Ela ficará salva no seu computador para que você não precise colar novamente nas próximas vezes.

### Passo 3: Escolher a Carta de Tarô
Você tem duas opções na tela:
1. **Enviar do Computador:** Basta arrastar o arquivo da carta (`.tif`, `.png` ou `.jpg`) para dentro da caixa na tela. O aplicativo converte arquivos `.tif` pesados automaticamente!
2. **Colar Link do Google Drive:** Escolha a opção do Google Drive, cole o link da sua pasta (`Arcanos - Imagens`) ou de um arquivo e clique em **"Buscar Cartas no Google Drive"**. Depois, escolha a carta na lista suspensa.

### Passo 4: Revisar as Camadas 3D e Gerar o Vídeo
1. Clique em **"🔍 Analisar Carta e Planejar Efeitos 2.5D"**.
2. O Agente vai mostrar na coluna da direita qual é a carta, o que ficará no 1º plano, no centro, no fundo, quais partículas serão animadas e qual astro aparecerá no céu.
3. Se quiser mudar qualquer detalhe (por exemplo, trocar o planeta no céu ou adicionar uma música `.mp3`), basta editar os campos de texto na tela.
4. Clique no botão dourado **"🚀 GERAR VÍDEO PRONTO AGORA"**.
5. Quando a barra chegar a 100%, o vídeo aparecerá na tela para você assistir e clicar em **"⬇️ BAIXAR VÍDEO PRONTO (.MP4)"**!

---

## ☁️ Quer usar no Celular ou de Qualquer Computador sem instalar nada? (Opcional)

Como este aplicativo foi construído em **Streamlit**, você pode colocá-lo gratuitamente na nuvem:
1. Suba esta pasta para uma conta gratuita no [GitHub](https://github.com/).
2. Entre em [share.streamlit.io](https://share.streamlit.io/), conecte seu GitHub e selecione o arquivo `app.py`.
3. Pronto! Você terá um **link próprio na internet** (ex: `meu-tarot-video.streamlit.app`) que abre direto no celular ou em qualquer computador do mundo sem precisar instalar nada!


---
## 🎞️ Novo motor: "Jornada pela Carta" (motor_jornada.py)

O arquivo `motor_jornada.py` precisa ficar **na mesma pasta do `app.py`** (se você sobe para o GitHub/Streamlit Cloud, envie os dois).

1. Escolha **Jornada pela Carta** na barra lateral (já vem como padrão).
2. Clique em **"1) Criar roteiro + cenas"** e confira as cenas ANTES de gastar com vídeo.
3. Clique em **GERAR VÍDEO**.

* **Sem chave Gemini:** recortes reais da carta + transições locais (rascunho, custo zero).
* **Com chave Gemini:** o Gemini lê a sua carta, escreve o roteiro e pinta as cenas no estilo dela.
* **Com chave + "Animar com Veo 3.1" (pago):** cada transição vira um "morph" feito por IA entre duas cenas — é o efeito do Vídeo Modelo.
* O vídeo termina na própria carta (loop perfeito), por isso o "reverse" espelhado foi desligado neste motor.

#!/bin/bash
cd "$(dirname "$0")"
echo "==================================================================="
echo "  🎴 INICIANDO TAROT VIDEO STUDIO 2.5D (PLATAFORMA VISUAL)"
echo "==================================================================="
echo ""
echo "[1/2] Verificando e instalando componentes necessários..."
pip3 install -r requirements.txt --quiet
echo ""
echo "[2/2] Abrindo o aplicativo no seu navegador..."
python3 -m streamlit run app.py

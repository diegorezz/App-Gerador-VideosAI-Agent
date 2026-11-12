@echo off
chcp 65001 >nul
title Tarot Video Studio 2.5D - Inicializador Automatico
echo ===================================================================
echo   🎴 INICIANDO TAROT VIDEO STUDIO 2.5D (PLATAFORMA VISUAL)
echo ===================================================================
echo.
echo [1/2] Verificando e instalando componentes necessarios...
pip install -r requirements.txt --quiet
echo.
echo [2/2] Abrindo o aplicativo no seu navegador...
echo       (Nao feche esta janela preta enquanto estiver usando o app)
echo.
streamlit run app.py
pause

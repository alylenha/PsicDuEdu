@echo off
rem ============================================================
rem  PsicoClin ERP - Iniciar sistema (Windows)
rem  Duplo clique: abre o servidor e o navegador automaticamente.
rem  Para encerrar: feche esta janela (ou Ctrl+C).
rem ============================================================
title PsicoClin ERP
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [AVISO] Sistema ainda nao instalado.
    echo Execute primeiro: instalar_windows.bat
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   PsicoClin ERP esta iniciando...
echo   O navegador abrira em http://127.0.0.1:5050
echo   Mantenha esta janela aberta enquanto usa o sistema.
echo ============================================================
echo.

start "" "http://127.0.0.1:5050"
".venv\Scripts\python.exe" run.py

pause

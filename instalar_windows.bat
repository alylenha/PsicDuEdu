@echo off
rem ============================================================
rem  PsicoClin ERP - Instalacao (Windows)
rem  Duplo clique neste arquivo. Requer Python 3.10+ instalado.
rem ============================================================
title PsicoClin ERP - Instalacao
cd /d "%~dp0"

echo.
echo ============================================================
echo   PsicoClin ERP - instalacao para Windows
echo ============================================================
echo.

rem --- localiza o Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo.
    echo Instale o Python gratuitamente em: https://www.python.org/downloads/
    echo IMPORTANTE: marque a caixinha "Add Python to PATH" na instalacao.
    echo Depois execute este arquivo novamente.
    echo.
    pause
    exit /b 1
)

echo [1/4] Criando ambiente virtual (pasta .venv)...
if not exist ".venv" (
    python -m venv .venv
    if errorlevel 1 goto falha
) else (
    echo       Ambiente ja existe - usando o atual.
)

echo [2/4] Atualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
if errorlevel 1 goto falha

echo [3/4] Instalando dependencias (Flask e cryptography)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 goto falha

echo [4/4] Preparando banco de dados e pastas...
".venv\Scripts\python.exe" -c "from app import db; db.init_db(); print('      Banco pronto em data/psiclin.db')"

echo.
echo ============================================================
echo   Instalacao concluida com sucesso!
echo.
echo   Para abrir o sistema: duplo clique em iniciar_windows.bat
echo ============================================================
echo.
pause
exit /b 0

:falha
echo.
echo [ERRO] A instalacao falhou. Verifique sua conexao com a internet
echo        e execute este arquivo novamente.
echo.
pause
exit /b 1

#!/bin/bash
# ============================================================
#  PsicoClin ERP — Instalação (macOS)
#  Duplo clique neste arquivo (ou: bash instalar_macos.command)
#  Requer Python 3.10+ (instale via python.org ou brew)
# ============================================================
cd "$(dirname "$0")"

echo
echo "============================================================"
echo "  PsicoClin ERP — instalação para macOS"
echo "============================================================"
echo

PY=""
for c in python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
    echo "[ERRO] Python não encontrado."
    echo "Instale gratuitamente em https://www.python.org/downloads/"
    echo "ou via Homebrew: brew install python"
    exit 1
fi
echo "Usando Python: $($PY --version 2>&1) ($PY)"

echo "[1/4] Criando ambiente virtual (pasta .venv)..."
if [ ! -d ".venv" ]; then
    "$PY" -m venv .venv || { echo "[ERRO] Falha ao criar o ambiente."; exit 1; }
else
    echo "      Ambiente já existe — usando o atual."
fi

echo "[2/4] Atualizando pip..."
./.venv/bin/python -m pip install --upgrade pip --quiet

echo "[3/4] Instalando dependências (Flask e cryptography)..."
./.venv/bin/python -m pip install -r requirements.txt --quiet || {
    echo "[ERRO] Falha na instalação — verifique a internet e tente de novo."
    exit 1
}

echo "[4/4] Preparando banco de dados e pastas..."
./.venv/bin/python -c "from app import db; db.init_db(); print('      Banco pronto em data/psiclin.db')"

echo
echo "============================================================"
echo "  Instalação concluída com sucesso!"
echo "  Para abrir o sistema: duplo clique em iniciar_macos.command"
echo "============================================================"

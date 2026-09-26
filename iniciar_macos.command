#!/bin/bash
# ============================================================
#  PsicoClin ERP — Iniciar sistema (macOS)
#  Duplo clique: abre o servidor e o navegador automaticamente.
#  Para encerrar: feche esta janela (ou Ctrl+C).
# ============================================================
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "[AVISO] Sistema ainda não instalado."
    echo "Execute primeiro: instalar_macos.command"
    exit 1
fi

echo
echo "============================================================"
echo "  PsicoClin ERP está iniciando..."
echo "  O navegador abrirá em http://127.0.0.1:5050"
echo "  Mantenha esta janela aberta enquanto usa o sistema."
echo "============================================================"
echo

open "http://127.0.0.1:5050" 2>/dev/null
./.venv/bin/python run.py

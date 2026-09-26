"""PsicoClin ERP — backup e restauração pela linha de comando.

Uso:
  python backup.py                        -> gera backups/psiclin_AAAA-MM-DD_HHMM.bak
  python backup.py --destino CAMINHO      -> gera o .bak em outro local (ex.: pendrive)
  python backup.py --restaurar ARQUIVO    -> restaura um .bak (sobrescreve os dados atuais)
  python backup.py --listar               -> lista os backups existentes

O .bak é um pacote com TODOS os dados: banco SQL, anexos e configurações.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# permite rodar de qualquer pasta
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.paths import BACKUPS_DIR, ensure_dirs  # noqa: E402
from app.services.backup_service import (criar_backup, listar_backups,  # noqa: E402
                                         restaurar_backup)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup e restauração do PsicoClin ERP")
    parser.add_argument("--destino", help="Caminho do .bak a gerar (opcional)")
    parser.add_argument("--restaurar", metavar="ARQUIVO", help="Restaura um arquivo .bak")
    parser.add_argument("--listar", action="store_true", help="Lista os backups existentes")
    args = parser.parse_args()

    ensure_dirs()

    if args.restaurar:
        resp = input(
            "ATENÇÃO: restaurar SOBRESCREVE os dados atuais pelos do arquivo.\n"
            f"  Arquivo: {args.restaurar}\nDigite RESTAURAR para confirmar: "
        )
        if resp.strip().upper() != "RESTAURAR":
            print("Cancelado — nada foi alterado.")
            return 1
        restaurar_backup(args.restaurar)
        print("✔ Backup restaurado com sucesso.")
        print("  Inicie o sistema normalmente (iniciar_windows.bat ou iniciar_macos.command).")
        return 0

    if args.listar:
        lista = listar_backups()
        if not lista:
            print("Nenhum backup encontrado em", BACKUPS_DIR)
        for b in lista:
            print(f"  {b.name}  ({b.stat().st_size / 1024:.1f} KB)")
        return 0

    caminho = criar_backup(args.destino)
    print(f"✔ Backup criado: {caminho}")
    print("  Guarde este arquivo em local seguro (pendrive, nuvem pessoal).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

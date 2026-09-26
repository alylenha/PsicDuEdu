"""Backup completo em .bak (pacote ZIP com banco + anexos + token Google) e restauração.

Todos os dados do sistema ficam dentro do .bak:
  - psiclin.db  (banco SQL completo)
  - anexos/     (arquivos anexos, já criptografados)
  - google_token.json (se existir)
"""
from __future__ import annotations

import datetime as _dt
import zipfile
from pathlib import Path

from app.paths import ANEXOS_DIR, BACKUPS_DIR, DB_PATH, DATA_DIR, ensure_dirs

MARCA = "PSICLIN_BAK_V1"


def _nome_backup() -> str:
    return f"psiclin_{_dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.bak"


def criar_backup(destino: Path | str | None = None) -> Path:
    """Gera o arquivo .bak e devolve o caminho criado."""
    ensure_dirs()
    if not DB_PATH.exists():
        raise FileNotFoundError("Banco de dados ainda não existe — inicie o sistema uma vez.")
    destino = Path(destino) if destino else BACKUPS_DIR / _nome_backup()
    destino.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("_psiclin_bak.txt", MARCA)
        z.write(DB_PATH, "psiclin.db")
        for arq in ANEXOS_DIR.rglob("*"):
            if arq.is_file():
                z.write(arq, f"anexos/{arq.relative_to(ANEXOS_DIR).as_posix()}")
        token = DATA_DIR / "google_token.json"
        if token.exists():
            z.write(token, "google_token.json")
    return destino


def restaurar_backup(arquivo_bak: Path | str) -> None:
    """Restaura o .bak sobre o diretório de dados (sobrescreve!)."""
    ensure_dirs()
    arquivo_bak = Path(arquivo_bak)
    if not arquivo_bak.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_bak}")
    with zipfile.ZipFile(arquivo_bak) as z:
        nomes = z.namelist()
        if "_psiclin_bak.txt" not in nomes or "psiclin.db" not in nomes:
            raise ValueError("Este arquivo não é um backup válido do PsicoClin.")
        # extrai sobre data/ (psiclin.db, anexos/..., google_token.json)
        z.extractall(DATA_DIR)


def listar_backups() -> list[Path]:
    ensure_dirs()
    return sorted(BACKUPS_DIR.glob("*.bak"), reverse=True)


def ultimo_backup() -> Path | None:
    lista = listar_backups()
    return lista[0] if lista else None


def backup_do_dia_ja_feito() -> bool:
    """True se já existe backup gerado hoje (backup automático diário)."""
    hoje = _dt.date.today().isoformat()
    return any(b.name.startswith(f"psiclin_{hoje}") for b in listar_backups())

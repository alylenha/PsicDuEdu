"""Caminhos do projeto — funcionam igual em Windows e macOS.

Todas as pastas são criadas automaticamente na primeira execução.
"""
from __future__ import annotations

from pathlib import Path

# Raiz do projeto = pasta acima deste arquivo (app/paths.py -> raiz)
BASE_DIR = Path(__file__).resolve().parent.parent

APP_DIR = BASE_DIR / "app"
STATIC_DIR = APP_DIR / "static"
TEMPLATE_DIR = APP_DIR / "templates"

DATA_DIR = BASE_DIR / "data"
ANEXOS_DIR = DATA_DIR / "anexos"
BACKUPS_DIR = BASE_DIR / "backups"

DB_PATH = DATA_DIR / "psiclin.db"
SCHEMA_PATH = APP_DIR / "schema.sql"


def ensure_dirs() -> None:
    """Cria as pastas de dados, anexos e backups, se não existirem."""
    for d in (DATA_DIR, ANEXOS_DIR, BACKUPS_DIR):
        d.mkdir(parents=True, exist_ok=True)

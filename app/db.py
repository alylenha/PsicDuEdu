"""Acesso ao banco SQLite (arquivo único em data/psiclin.db)."""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from flask import g

from .paths import DB_PATH, SCHEMA_PATH, ensure_dirs


def get_db() -> sqlite3.Connection:
    """Conexão por requisição (guardada no contexto do Flask)."""
    if "db" not in g:
        ensure_dirs()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc: Any = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    """Cria o banco e as tabelas (executado na 1ª execução e por scripts)."""
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
        _migrar_previsoes(conn)
        _migrar_risco(conn)
        conn.commit()
    finally:
        conn.close()


def _migrar_previsoes(conn: sqlite3.Connection) -> None:
    """Migração incremental para bancos criados antes das previsões."""
    cols_lanc = {r[1] for r in conn.execute("PRAGMA table_info(lancamentos)").fetchall()}
    if "previsao_id" not in cols_lanc:
        conn.execute("ALTER TABLE lancamentos ADD COLUMN previsao_id INTEGER REFERENCES previsoes(id) ON DELETE SET NULL")
    # garante tabela/índices mesmo se o schema antigo já criou o banco
    conn.execute(
        "CREATE TABLE IF NOT EXISTS previsoes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "data_prevista TEXT NOT NULL, "
        "tipo TEXT NOT NULL CHECK (tipo IN ('receita','despesa')), "
        "categoria TEXT NOT NULL, "
        "descricao TEXT NOT NULL DEFAULT '', "
        "valor_centavos INTEGER NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'prevista' "
        "CHECK (status IN ('prevista','efetivada','cancelada')), "
        "origem TEXT NOT NULL DEFAULT 'manual' "
        "CHECK (origem IN ('manual','agendamento')), "
        "agendamento_id INTEGER REFERENCES agendamentos(id) ON DELETE SET NULL, "
        "paciente_id INTEGER REFERENCES pacientes(id) ON DELETE SET NULL, "
        "lancamento_id INTEGER REFERENCES lancamentos(id) ON DELETE SET NULL, "
        "criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')), "
        "efetivado_em TEXT)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prev_data ON previsoes(data_prevista)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prev_status ON previsoes(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prev_ag ON previsoes(agendamento_id)")


def _migrar_risco(conn: sqlite3.Connection) -> None:
    """Migração incremental para classificação de risco clínico."""
    cols_pac = {r[1] for r in conn.execute("PRAGMA table_info(pacientes)").fetchall()}
    if "risco_id" not in cols_pac:
        conn.execute(
            "ALTER TABLE pacientes ADD COLUMN risco_id INTEGER "
            "REFERENCES categorias_risco(id) ON DELETE SET NULL"
        )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS categorias_risco ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "nome TEXT NOT NULL UNIQUE, "
        "cor TEXT NOT NULL DEFAULT '#8A8177', "
        "ativa INTEGER NOT NULL DEFAULT 1, "
        "ordem INTEGER NOT NULL DEFAULT 0, "
        "criada_em TEXT NOT NULL DEFAULT (datetime('now','localtime')))"
    )
    # população inicial (somente se vazia)
    n = conn.execute("SELECT COUNT(*) FROM categorias_risco").fetchone()[0]
    if n == 0:
        conn.executemany(
            "INSERT INTO categorias_risco (nome, cor, ordem) VALUES (?, ?, ?)",
            [("Baixo", "#7C9885", 1), ("Médio", "#C9A227", 2),
             ("Alto", "#C6938B", 3), ("Crítico", "#8A2B2B", 4)],
        )


def query(sql: str, params: Iterable[Any] = (), one: bool = False):
    db = get_db()
    cur = db.execute(sql, tuple(params))
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """Executa e confirma; retorna o lastrowid."""
    db = get_db()
    cur = db.execute(sql, tuple(params))
    db.commit()
    return int(cur.lastrowid or 0)


# ------------------------------------------------------------------
# Configurações (chave/valor) — usadas pelas integrações opcionais
# ------------------------------------------------------------------

def get_config(chave: str, default: str = "") -> str:
    row = query("SELECT valor FROM configuracoes WHERE chave = ?", (chave,), one=True)
    return row["valor"] if row and row["valor"] is not None else default


def set_config(chave: str, valor: str) -> None:
    execute(
        "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )


def get_all_config() -> dict[str, str]:
    rows = query("SELECT chave, valor FROM configuracoes")
    return {r["chave"]: (r["valor"] or "") for r in rows}

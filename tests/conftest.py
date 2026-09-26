"""Fixtures dos testes: app com banco em pasta temporária (não toca nos dados reais)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def app_ctx(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "anexos").mkdir(parents=True)
    backups = tmp_path / "backups"
    backups.mkdir()
    db_path = data / "teste.db"

    monkeypatch.setattr("app.db.DB_PATH", db_path)
    monkeypatch.setattr("app.paths.DB_PATH", db_path)
    monkeypatch.setattr("app.routes.prontuario.ANEXOS_DIR", data / "anexos")
    import app.services.backup_service as bs
    monkeypatch.setattr(bs, "DB_PATH", db_path)
    monkeypatch.setattr(bs, "DATA_DIR", data)
    monkeypatch.setattr(bs, "ANEXOS_DIR", data / "anexos")
    monkeypatch.setattr(bs, "BACKUPS_DIR", backups)

    from app import criar_app

    app = criar_app()
    app.config["TESTING"] = True
    with app.app_context():
        yield app


@pytest.fixture()
def cliente(app_ctx):
    return app_ctx.test_client()

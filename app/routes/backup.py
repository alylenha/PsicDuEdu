"""Backup — gerar, listar, baixar e restaurar arquivos .bak."""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   send_file, url_for)

from app import db
from app.services import backup_service

bp = Blueprint("backup", __name__, url_prefix="/backup")


@bp.route("/")
def pagina():
    return render_template(
        "backup/pagina.html", pagina="backup",
        backups=backup_service.listar_backups(),
        ultimo=backup_service.ultimo_backup(),
    )


@bp.route("/criar", methods=["POST"])
def criar():
    try:
        caminho = backup_service.criar_backup()
        flash(f"Backup criado: {caminho.name}", "sucesso")
    except Exception as e:
        flash(f"Falha ao criar backup: {e}", "erro")
    return redirect(url_for("backup.pagina"))


@bp.route("/baixar/<path:nome>")
def baixar(nome: str):
    caminho = backup_service.BACKUPS_DIR / nome
    if not caminho.exists() or caminho.suffix != ".bak":
        flash("Arquivo não encontrado.", "erro")
        return redirect(url_for("backup.pagina"))
    return send_file(caminho, as_attachment=True, download_name=caminho.name)


@bp.route("/restaurar", methods=["POST"])
def restaurar():
    arquivo = request.files.get("arquivo")
    caminho_servidor = (request.form.get("caminho") or "").strip()
    try:
        if arquivo and arquivo.filename:
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmp:
                destino = Path(tmp) / arquivo.filename
                arquivo.save(destino)
                backup_service.restaurar_backup(destino)
            flash(f"Backup restaurado do arquivo {arquivo.filename}.", "sucesso")
        elif caminho_servidor:
            backup_service.restaurar_backup(caminho_servidor)
            flash(f"Backup restaurado: {caminho_servidor}", "sucesso")
        else:
            flash("Selecione um arquivo .bak ou informe o caminho.", "erro")
    except Exception as e:
        flash(f"Falha ao restaurar: {e}", "erro")
    return redirect(url_for("backup.pagina"))

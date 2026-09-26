"""PsicoClin ERP — aplicação Flask (roda localmente em Windows e macOS)."""
from __future__ import annotations

import os
import secrets

from flask import Flask, redirect, render_template, request, url_for

from . import db
from .paths import ensure_dirs


def criar_app() -> Flask:
    ensure_dirs()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("PSICLIN_SECRET") or secrets.token_hex(32)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["JSON_AS_ASCII"] = False
    app.jinja_env.auto_reload = True

    db.init_db()
    _backup_automatico()

    # ---- Blueprints ----
    from .routes import (agenda, backup, dashboard, financeiro, integracoes,
                         pacientes, prontuario, relatorios)

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(pacientes.bp)
    app.register_blueprint(prontuario.bp)
    app.register_blueprint(agenda.bp)
    app.register_blueprint(financeiro.bp)
    app.register_blueprint(relatorios.bp)
    app.register_blueprint(integracoes.bp)
    app.register_blueprint(backup.bp)

    app.teardown_appcontext(db.close_db)

    # ---- Variáveis globais dos templates ----
    from .security import formatar_cpf
    from .utils import (STATUS_ICONS, STATUS_LABELS, data_br, formatar_moeda,
                        formatar_moeda_simples, hora_br, idade)

    @app.context_processor
    def _globais():
        return {
            "STATUS_LABELS": STATUS_LABELS,
            "STATUS_ICONS": STATUS_ICONS,
            "fmt_moeda": formatar_moeda,
            "fmt_valor": formatar_moeda_simples,
            "fmt_cpf": formatar_cpf,
            "fmt_data": data_br,
            "fmt_hora": hora_br,
            "fmt_idade": idade,
            "clinica_nome": db.get_config("clinica_nome", "PsicoClin ERP"),
        }

    # ---- Erros ----
    @app.errorhandler(404)
    def _404(_e):
        return render_template("erro.html", pagina="", codigo=404,
                               mensagem="Página não encontrada."), 404

    @app.errorhandler(403)
    def _403(_e):
        return render_template("erro.html", pagina="", codigo=403,
                               mensagem="Acesso bloqueado — desbloqueie o prontuário com a senha do paciente."), 403

    @app.errorhandler(500)
    def _500(e):
        return render_template("erro.html", pagina="", codigo=500,
                               mensagem=f"Erro interno: {e}"), 500

    return app


def _backup_automatico() -> None:
    """No primeiro start do dia, gera um .bak automaticamente (best-effort)."""
    try:
        from .services import backup_service

        if not backup_service.backup_do_dia_ja_feito():
            caminho = backup_service.criar_backup()
            print(f"[PsicoClin] Backup automático criado: {caminho.name}")
    except Exception as e:  # não impede a inicialização
        print(f"[PsicoClin] Aviso: backup automático não foi criado ({e})")


# Permite `flask --app app run` também
app = None


def main() -> None:
    global app
    app = criar_app()
    print("=" * 60)
    print("  PsicoClin ERP — sistema rodando localmente")
    print("  Abra no navegador:  http://127.0.0.1:5050")
    print("  Para encerrar: feche esta janela ou pressione Ctrl+C")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5050, debug=False)

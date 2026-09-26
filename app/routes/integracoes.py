"""Integrações opcionais — e-mail (SMTP) e Google Agenda.

Tudo é desativado por padrão: sem configuração, o sistema funciona 100% offline
e nada é enviado/sincronizado.
"""
from __future__ import annotations

from datetime import date, timedelta

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

from app import db
from app.services import email_service, google_calendar

bp = Blueprint("integracoes", __name__, url_prefix="/integracoes")

CHAVES_EMAIL = ["smtp_host", "smtp_porta", "smtp_usuario", "smtp_senha",
                "smtp_tls", "avisos_email_clinica", "avisos_email_paciente_falta",
                "clinica_nome", "clinica_endereco"]
CHAVES_GOOGLE = ["google_client_id", "google_client_secret", "google_calendar_id"]


@bp.route("/")
def pagina():
    return render_template(
        "integracoes/pagina.html", pagina="integracoes",
        cfg=db.get_all_config(),
        smtp_ok=email_service.smtp_configurado(),
        google_ok=google_calendar.oauth_configurado() and google_calendar.token_salvo(),
        google_creds=google_calendar.oauth_configurado(),
    )


@bp.route("/salvar_email", methods=["POST"])
def salvar_email():
    for chave in CHAVES_EMAIL:
        valor = (request.form.get(chave) or "").strip()
        if chave == "smtp_porta" and not valor:
            valor = "587"
        if chave == "smtp_tls" and not valor:
            valor = "1"
        db.set_config(chave, valor)
    flash("Configurações de e-mail salvas.", "sucesso")
    return redirect(url_for("integracoes.pagina"))


@bp.route("/salvar_google", methods=["POST"])
def salvar_google():
    for chave in CHAVES_GOOGLE:
        db.set_config(chave, (request.form.get(chave) or "").strip())
    flash("Credenciais do Google salvas. Clique em 'Conectar com o Google' para autorizar.",
          "sucesso")
    return redirect(url_for("integracoes.pagina"))


@bp.route("/teste_email", methods=["POST"])
def teste_email():
    import smtplib
    from email.message import EmailMessage

    destino = (request.form.get("destino") or db.get_config("avisos_email_clinica") or "").strip()
    if not destino:
        flash("Informe um e-mail de destino para o teste.", "erro")
        return redirect(url_for("integracoes.pagina"))
    msg = EmailMessage()
    msg["Subject"] = "PsicoClin — e-mail de teste ✔"
    msg["From"] = db.get_config("smtp_usuario")
    msg["To"] = destino
    msg.set_content("Se você recebeu este e-mail, a integração de avisos está funcionando!")
    try:
        email_service.enviar_mail(msg)
        flash(f"E-mail de teste enviado para {destino}.", "sucesso")
    except Exception as e:
        flash(f"Falha no envio: {e}", "erro")
    return redirect(url_for("integracoes.pagina"))


# ------------------------------------------------------------------
# Google Agenda (opcional — OAuth)
# ------------------------------------------------------------------

@bp.route("/google/conectar")
def google_conectar():
    if not google_calendar.oauth_configurado():
        flash("Preencha Client ID e Client Secret do Google antes de conectar.", "erro")
        return redirect(url_for("integracoes.pagina"))
    try:
        fluxo = google_calendar.construir_fluxo()
        url, _estado = fluxo.authorization_url(
            access_type="offline", include_granted_scopes="false", prompt="consent"
        )
        return redirect(url)
    except Exception as e:
        flash(f"Erro ao iniciar conexão: {e}", "erro")
        return redirect(url_for("integracoes.pagina"))


@bp.route("/google/callback")
def google_callback():
    try:
        fluxo = google_calendar.construir_fluxo()
        fluxo.fetch_token(code=request.args.get("code"))
        google_calendar.salvar_token(fluxo.credentials)
        flash("Google Agenda conectado! As sessões passam a ser espelhadas.", "sucesso")
    except Exception as e:
        flash(f"Falha ao autorizar o Google: {e}", "erro")
    return redirect(url_for("integracoes.pagina"))


@bp.route("/google/desconectar", methods=["POST"])
def google_desconectar():
    from app.paths import DATA_DIR

    (DATA_DIR / "google_token.json").unlink(missing_ok=True)
    flash("Google Agenda desconectado.", "sucesso")
    return redirect(url_for("integracoes.pagina"))


@bp.route("/google/teste", methods=["POST"])
def google_teste():
    if not (google_calendar.oauth_configurado() and google_calendar.token_salvo()):
        flash("Conecte o Google primeiro.", "erro")
        return redirect(url_for("integracoes.pagina"))
    ag = db.query(
        "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
        "JOIN pacientes p ON p.id = a.paciente_id "
        "WHERE a.data >= ? ORDER BY a.data LIMIT 1",
        (date.today().isoformat(),), one=True,
    )
    if ag is None:
        flash("Nenhum agendamento futuro para testar a sincronização.", "erro")
        return redirect(url_for("integracoes.pagina"))
    eid = google_calendar.sincronizar_agendamento(ag)
    if eid:
        db.execute("UPDATE agendamentos SET google_event_id = ? WHERE id = ?", (eid, ag["id"]))
        flash("Evento de teste criado no Google Agenda ✔", "sucesso")
    else:
        flash("Não foi possível sincronizar — veja as credenciais.", "erro")
    return redirect(url_for("integracoes.pagina"))


# ------------------------------------------------------------------
# Categorias de risco clínico (classificação manual de pacientes)
# ------------------------------------------------------------------

def _valida_cor(valor: str) -> str:
    v = (valor or "").strip()
    if len(v) == 7 and v.startswith("#"):
        try:
            int(v[1:], 16)
            return v.upper()
        except ValueError:
            pass
    return "#8A8177"


@bp.route("/risco/categorias")
def risco_categorias():
    cats = db.query(
        "SELECT r.*, (SELECT COUNT(*) FROM pacientes p WHERE p.risco_id = r.id) AS n_pacientes "
        "FROM categorias_risco r ORDER BY r.ordem, r.nome COLLATE NOCASE"
    )
    return render_template("integracoes/risco.html", pagina="integracoes", cats=cats)


@bp.route("/risco/categorias/nova", methods=["POST"])
def risco_categoria_nova():
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Informe o nome da categoria.", "erro")
        return redirect(url_for("integracoes.risco_categorias"))
    cor = _valida_cor(request.form.get("cor"))
    try:
        ordem = int(request.form.get("ordem") or 0)
    except ValueError:
        ordem = 0
    try:
        db.execute(
            "INSERT INTO categorias_risco (nome, cor, ordem) VALUES (?, ?, ?)",
            (nome, cor, ordem),
        )
    except Exception:
        flash("Já existe uma categoria com este nome.", "erro")
        return redirect(url_for("integracoes.risco_categorias"))
    flash("Categoria criada.", "sucesso")
    return redirect(url_for("integracoes.risco_categorias"))


@bp.route("/risco/categorias/<int:cid>/editar", methods=["POST"])
def risco_categoria_editar(cid: int):
    cat = db.query("SELECT * FROM categorias_risco WHERE id = ?", (cid,), one=True)
    if cat is None:
        flash("Categoria não encontrada.", "erro")
        return redirect(url_for("integracoes.risco_categorias"))
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Informe o nome da categoria.", "erro")
        return redirect(url_for("integracoes.risco_categorias"))
    cor = _valida_cor(request.form.get("cor"))
    try:
        ordem = int(request.form.get("ordem") or 0)
    except ValueError:
        ordem = 0
    try:
        db.execute(
            "UPDATE categorias_risco SET nome = ?, cor = ?, ordem = ? WHERE id = ?",
            (nome, cor, ordem, cid),
        )
    except Exception:
        flash("Já existe uma categoria com este nome.", "erro")
        return redirect(url_for("integracoes.risco_categorias"))
    flash("Categoria atualizada.", "sucesso")
    return redirect(url_for("integracoes.risco_categorias"))


@bp.route("/risco/categorias/<int:cid>/excluir", methods=["POST"])
def risco_categoria_excluir(cid: int):
    cat = db.query("SELECT * FROM categorias_risco WHERE id = ?", (cid,), one=True)
    if cat is None:
        flash("Categoria não encontrada.", "erro")
        return redirect(url_for("integracoes.risco_categorias"))
    db.execute("UPDATE pacientes SET risco_id = NULL WHERE risco_id = ?", (cid,))
    db.execute("DELETE FROM categorias_risco WHERE id = ?", (cid,))
    flash("Categoria excluída; pacientes ficaram sem classificação.", "sucesso")
    return redirect(url_for("integracoes.risco_categorias"))


@bp.route("/baixar_ics")
def baixar_ics():
    """Exporta os próximos 60 dias de agenda em .ics (Google/Apple/Outlook)."""
    from app.services.ics import gerar_ics

    hoje = date.today()
    ags = db.query(
        "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
        "JOIN pacientes p ON p.id = a.paciente_id "
        "WHERE a.data BETWEEN ? AND ? AND a.status != 'cancelado'",
        (hoje.isoformat(), (hoje + timedelta(days=60)).isoformat()),
    )
    from flask import Response

    return Response(
        gerar_ics(ags), mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=psiclin_agenda.ics"},
    )

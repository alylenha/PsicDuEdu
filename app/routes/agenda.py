"""Agenda — visão semanal, agendamentos, status e pagamento com 1 clique."""
from __future__ import annotations

from datetime import date, timedelta

from flask import (Blueprint, Response, flash, redirect, render_template,
                   request, url_for)

from app import db
from app.services import email_service
from app.services.ics import gerar_ics
from app.utils import STATUS_LABELS, data_br, parse_data, parse_moeda

bp = Blueprint("agenda", __name__, url_prefix="/agenda")


def _semana_inicio(d: date) -> date:
    return d - timedelta(days=d.weekday())


PERIODOS_DIA = {
    "manha": ("06:00", "12:00"),
    "tarde": ("12:00", "18:00"),
    "noite": ("18:00", "24:00"),
}


def _link_semana(ref_iso: str, profissional: str, paciente_id: int,
                 tipo: str, periodo: str) -> str:
    """Link de navegação da semana preservando os filtros ativos."""
    params: dict = {"ref": ref_iso}
    if profissional:
        params["profissional"] = profissional
    if paciente_id:
        params["paciente"] = paciente_id
    if tipo:
        params["tipo"] = tipo
    if periodo:
        params["periodo"] = periodo
    return url_for("agenda.calendario", **params)


@bp.route("/")
def calendario():
    ref = parse_data(request.args.get("ref")) if request.args.get("ref") else date.today()
    inicio = _semana_inicio(ref)
    dias = [inicio + timedelta(days=i) for i in range(7)]
    ini_s, fim_s = dias[0].isoformat(), dias[-1].isoformat()

    profissional = (request.args.get("profissional") or "").strip()
    try:
        paciente_id = int(request.args.get("paciente") or 0)
    except ValueError:
        paciente_id = 0
    tipo = (request.args.get("tipo") or "").strip()
    periodo = (request.args.get("periodo") or "").strip()

    where = ["a.data BETWEEN ? AND ?"]
    params: list = [ini_s, fim_s]
    if profissional:
        where.append("LOWER(a.profissional) = LOWER(?)")
        params.append(profissional)
    if paciente_id:
        where.append("a.paciente_id = ?")
        params.append(paciente_id)
    if tipo:
        where.append("a.tipo = ?")
        params.append(tipo)
    if periodo in PERIODOS_DIA:
        hi, hf = PERIODOS_DIA[periodo]
        where.append("a.hora_inicio >= ? AND a.hora_inicio < ?")
        params += [hi, hf]
    ags = db.query(
        "SELECT a.*, p.nome AS paciente_nome, p.telefone AS paciente_telefone "
        "FROM agendamentos a JOIN pacientes p ON p.id = a.paciente_id "
        f"WHERE {' AND '.join(where)} ORDER BY a.data, a.hora_inicio",
        tuple(params),
    )
    por_dia: dict[str, list] = {d.isoformat(): [] for d in dias}
    for a in ags:
        por_dia.setdefault(a["data"], []).append(a)

    profissionais = [r["profissional"] for r in db.query(
        "SELECT DISTINCT profissional FROM agendamentos WHERE profissional != '' ORDER BY profissional"
    )]
    pacientes = db.query("SELECT id, nome FROM pacientes ORDER BY nome COLLATE NOCASE")
    tipos = [r["tipo"] for r in db.query(
        "SELECT DISTINCT tipo FROM agendamentos WHERE tipo != '' ORDER BY tipo"
    )]
    filtros_ativos = bool(profissional or paciente_id or tipo or periodo)
    return render_template(
        "agenda/semana.html", pagina="agenda", dias=dias, por_dia=por_dia,
        ref=ref, inicio=inicio, fim=dias[-1],
        profissional=profissional, paciente=paciente_id, tipo=tipo, periodo=periodo,
        filtros_ativos=filtros_ativos, profissionais=profissionais,
        pacientes=pacientes, tipos=tipos,
        hoje_iso=date.today().isoformat(),
        link_anterior=_link_semana((inicio - timedelta(days=7)).isoformat(),
                                   profissional, paciente_id, tipo, periodo),
        link_hoje=_link_semana(date.today().isoformat(),
                               profissional, paciente_id, tipo, periodo),
        link_seguinte=_link_semana((dias[-1] + timedelta(days=1)).isoformat(),
                                   profissional, paciente_id, tipo, periodo),
    )


def _pacientes_ativos():
    return db.query(
        "SELECT id, nome FROM pacientes WHERE ativo = 1 ORDER BY nome COLLATE NOCASE"
    )


def _dados_form() -> dict:
    data = parse_data(request.form.get("data"))
    paciente_id = int(request.form.get("paciente_id") or 0)
    if not paciente_id:
        raise ValueError("Selecione o paciente.")
    hi = (request.form.get("hora_inicio") or "").strip()
    hf = (request.form.get("hora_fim") or "").strip()
    if not hi or not hf:
        raise ValueError("Informe hora de início e fim.")
    status = request.form.get("status") or "agendado"
    if status not in STATUS_LABELS:
        raise ValueError("Status inválido.")
    texto_valor = (request.form.get("valor") or "").strip()
    valor = parse_moeda(texto_valor) if texto_valor else 0
    return {
        "paciente_id": paciente_id,
        "data": data.isoformat(),
        "hora_inicio": hi,
        "hora_fim": hf,
        "tipo": (request.form.get("tipo") or "Sessão").strip(),
        "profissional": (request.form.get("profissional") or "").strip(),
        "status": status,
        "valor_centavos": valor,
        "observacoes": (request.form.get("observacoes") or "").strip(),
    }


@bp.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        try:
            dados = _dados_form()
        except ValueError as e:
            flash(str(e), "erro")
            return render_template("agenda/form.html", pagina="agenda",
                                   ag=None, pacientes=_pacientes_ativos())
        pid = db.execute(
            "INSERT INTO agendamentos (paciente_id, data, hora_inicio, hora_fim, tipo, "
            "profissional, status, valor_centavos, observacoes) VALUES (?,?,?,?,?,?,?,?,?)",
            (dados["paciente_id"], dados["data"], dados["hora_inicio"], dados["hora_fim"],
             dados["tipo"], dados["profissional"], dados["status"],
             dados["valor_centavos"], dados["observacoes"]),
        )
        ag = db.query(
            "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
            "JOIN pacientes p ON p.id = a.paciente_id WHERE a.id = ?", (pid,), one=True
        )
        try:
            if email_service.avisar_novo_agendamento(ag):
                db.execute("UPDATE agendamentos SET email_enviado = 1 WHERE id = ?", (pid,))
        except Exception:
            pass
        try:
            from app.routes.financeiro import sincronizar_previsao_agendamento
            sincronizar_previsao_agendamento(pid)
        except Exception:
            pass
        flash("Agendamento criado.", "sucesso")
        return redirect(url_for("agenda.calendario", ref=dados["data"]))
    return render_template("agenda/form.html", pagina="agenda",
                           ag=None, pacientes=_pacientes_ativos())


@bp.route("/<int:aid>/editar", methods=["GET", "POST"])
def editar(aid: int):
    ag = db.query("SELECT * FROM agendamentos WHERE id = ?", (aid,), one=True)
    if ag is None:
        flash("Agendamento não encontrado.", "erro")
        return redirect(url_for("agenda.calendario"))
    if request.method == "POST":
        try:
            dados = _dados_form()
        except ValueError as e:
            flash(str(e), "erro")
            return render_template("agenda/form.html", pagina="agenda",
                                   ag=ag, pacientes=_pacientes_ativos())
        db.execute(
            "UPDATE agendamentos SET paciente_id=?, data=?, hora_inicio=?, hora_fim=?, "
            "tipo=?, profissional=?, status=?, valor_centavos=?, observacoes=? WHERE id=?",
            (dados["paciente_id"], dados["data"], dados["hora_inicio"], dados["hora_fim"],
             dados["tipo"], dados["profissional"], dados["status"],
             dados["valor_centavos"], dados["observacoes"], aid),
        )
        try:
            from app.routes.financeiro import sincronizar_previsao_agendamento
            sincronizar_previsao_agendamento(aid)
        except Exception:
            pass
        flash("Agendamento atualizado.", "sucesso")
        return redirect(url_for("agenda.calendario", ref=dados["data"]))
    return render_template("agenda/form.html", pagina="agenda",
                           ag=ag, pacientes=_pacientes_ativos())


@bp.route("/<int:aid>/status", methods=["POST"])
def status(aid: int):
    ag = db.query("SELECT * FROM agendamentos WHERE id = ?", (aid,), one=True)
    if ag is None:
        flash("Agendamento não encontrado.", "erro")
        return redirect(url_for("agenda.calendario"))
    novo = request.form.get("status") or ""
    if novo not in STATUS_LABELS:
        flash("Status inválido.", "erro")
        return redirect(request.referrer or url_for("agenda.calendario"))
    db.execute("UPDATE agendamentos SET status = ? WHERE id = ?", (novo, aid))
    try:
        from app.routes.financeiro import sincronizar_previsao_agendamento
        sincronizar_previsao_agendamento(aid)
    except Exception:
        pass
    try:
        if novo == "cancelado":
            email_service.avisar_cancelamento(ag)
            if ag["google_event_id"]:
                from app.services import google_calendar
                google_calendar.remover_evento(ag["google_event_id"])
        elif novo == "faltou":
            email_service.avisar_falta(ag)
    except Exception:
        pass
    flash(f"Status alterado para {STATUS_LABELS[novo]}.", "sucesso")
    return redirect(request.referrer or url_for("agenda.calendario"))


@bp.route("/<int:aid>/receber", methods=["POST"])
def receber(aid: int):
    """Marca a sessão como paga: efetiva a previsão (se houver) ou cria a receita."""
    ag = db.query("SELECT * FROM agendamentos WHERE id = ?", (aid,), one=True)
    if ag is None:
        flash("Agendamento não encontrado.", "erro")
        return redirect(url_for("agenda.calendario"))
    if ag["pago"]:
        flash("Esta sessão já foi registrada como paga.", "erro")
        return redirect(request.referrer or url_for("agenda.calendario"))
    if not ag["valor_centavos"]:
        flash("Defina um valor para a sessão antes de registrar o pagamento.", "erro")
        return redirect(request.referrer or url_for("agenda.calendario"))
    forma = (request.form.get("forma_pagamento") or "PIX").strip()
    try:
        from app.routes.financeiro import sincronizar_previsao_agendamento
        sincronizar_previsao_agendamento(aid)
        prev = db.query(
            "SELECT * FROM previsoes WHERE agendamento_id = ? AND status = 'prevista' "
            "ORDER BY id DESC",
            (aid,), one=True,
        )
        if prev is not None:
            from app.routes.financeiro import _efetivar_previsao
            _efetivar_previsao(prev, forma)
            flash("Receita registrada no financeiro e sessão marcada como paga.", "sucesso")
            return redirect(request.referrer or url_for("agenda.calendario"))
    except Exception:
        pass
    paciente = db.query("SELECT nome FROM pacientes WHERE id = ?", (ag["paciente_id"],), one=True)
    nome = paciente["nome"] if paciente else "?"
    lid = db.execute(
        "INSERT INTO lancamentos (data, tipo, categoria, descricao, valor_centavos, "
        "forma_pagamento, agendamento_id) VALUES (?, 'receita', 'Sessão', ?, ?, ?, ?)",
        (ag["data"], f"Sessão — {nome} ({data_br(ag['data'])})",
         ag["valor_centavos"], forma, aid),
    )
    db.execute(
        "UPDATE agendamentos SET pago = 1, lancamento_id = ?, "
        "status = CASE WHEN status IN ('agendado','confirmado') THEN 'realizado' "
        "ELSE status END WHERE id = ?",
        (lid, aid),
    )
    flash("Receita registrada no financeiro e sessão marcada como paga.", "sucesso")
    return redirect(request.referrer or url_for("agenda.calendario"))


@bp.route("/exportar.ics")
def exportar_ics():
    ref = parse_data(request.args.get("ref")) if request.args.get("ref") else date.today()
    inicio = _semana_inicio(ref)
    fim = inicio + timedelta(days=6)
    ags = db.query(
        "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
        "JOIN pacientes p ON p.id = a.paciente_id "
        "WHERE a.data BETWEEN ? AND ? AND a.status != 'cancelado'",
        (inicio.isoformat(), fim.isoformat()),
    )
    conteudo = gerar_ics(ags)
    nome = f"agenda_{inicio.isoformat()}_{fim.isoformat()}.ics"
    return Response(
        conteudo, mimetype="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={nome}"},
    )

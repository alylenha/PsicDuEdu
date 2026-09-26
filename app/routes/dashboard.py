"""Dashboard — indicadores principais + gráficos + agenda do dia."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, flash, render_template, request, url_for
from werkzeug.utils import redirect

from app import db
from app.utils import data_br, mes_aniversario, mes_nome, parse_data

bp = Blueprint("dashboard", __name__)


def _ultimo_dia_mes(ano: int, mes: int) -> date:
    proximo = date(ano + (mes == 12), (mes % 12) + 1, 1)
    return proximo - timedelta(days=1)


@bp.route("/")
def index():
    hoje = date.today()

    # ---- Filtros: competência (AAAA-MM) e/ou intervalo de dias ----
    comp = (request.args.get("comp") or "").strip()
    de_txt = (request.args.get("de") or "").strip()
    ate_txt = (request.args.get("ate") or "").strip()
    try:
        if de_txt or ate_txt:
            ini = parse_data(de_txt) if de_txt else parse_data(ate_txt)
            fim = parse_data(ate_txt) if ate_txt else parse_data(de_txt)
            if fim < ini:
                ini, fim = fim, ini
            modo = "intervalo"
            comp = ""
        else:
            if comp:
                ref = datetime.strptime(comp, "%Y-%m").date()
            else:
                ref = hoje
                comp = ref.strftime("%Y-%m")
            ini = ref.replace(day=1)
            fim = _ultimo_dia_mes(ref.year, ref.month)
            modo = "competencia"
    except ValueError:
        flash("Filtro de período inválido.", "erro")
        return redirect(url_for("dashboard.index"))

    ini_s, fim_s = ini.isoformat(), fim.isoformat()
    # janela de 6 meses TERMINANDO no fim do período filtrado
    mes_ini, ano_ini = fim.month - 5, fim.year
    while mes_ini < 1:
        mes_ini += 12
        ano_ini -= 1
    inicio_6m = date(ano_ini, mes_ini, 1)

    kpi_pacientes = db.query(
        "SELECT COUNT(*) AS n FROM pacientes WHERE ativo = 1", one=True
    )["n"]
    kpi_hoje = db.query(
        "SELECT COUNT(*) AS n FROM agendamentos WHERE data = ? AND status != 'cancelado'",
        (hoje.isoformat(),), one=True,
    )["n"]
    kpi_mes = db.query(
        "SELECT COUNT(*) AS n FROM agendamentos WHERE data BETWEEN ? AND ? AND status != 'cancelado'",
        (ini_s, fim_s,), one=True,
    )["n"]

    rec_mes = db.query(
        "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
        "WHERE tipo='receita' AND data BETWEEN ? AND ?",
        (ini_s, fim_s,), one=True,
    )["t"]
    des_mes = db.query(
        "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
        "WHERE tipo='despesa' AND data BETWEEN ? AND ?",
        (ini_s, fim_s,), one=True,
    )["t"]

    realizados_mes = db.query(
        "SELECT COUNT(*) AS n FROM agendamentos WHERE status='realizado' AND data BETWEEN ? AND ?",
        (ini_s, fim_s,), one=True,
    )["n"]
    ticket = (rec_mes // realizados_mes) if realizados_mes else 0

    # gráfico: receita x despesa dos últimos 6 meses
    labels_6m, receitas_6m, despesas_6m = [], [], []
    ano, mes = inicio_6m.year, inicio_6m.month
    for _ in range(6):
        ini = date(ano, mes, 1)
        fim = date(ano + (mes == 12), (mes % 12) + 1, 1) - timedelta(days=1)
        r = db.query(
            "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
            "WHERE tipo='receita' AND data BETWEEN ? AND ?",
            (ini.isoformat(), fim.isoformat(),), one=True,
        )["t"]
        d = db.query(
            "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
            "WHERE tipo='despesa' AND data BETWEEN ? AND ?",
            (ini.isoformat(), fim.isoformat(),), one=True,
        )["t"]
        labels_6m.append(mes_nome(mes)[:3])
        receitas_6m.append(r / 100)
        despesas_6m.append(d / 100)
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1

    # gráfico: atendimentos por mês (últimos 6 meses, não cancelados)
    atend_6m = []
    ano, mes = inicio_6m.year, inicio_6m.month
    for _ in range(6):
        ini = date(ano, mes, 1)
        fim = date(ano + (mes == 12), (mes % 12) + 1, 1) - timedelta(days=1)
        n = db.query(
            "SELECT COUNT(*) AS n FROM agendamentos WHERE status != 'cancelado' "
            "AND data BETWEEN ? AND ?",
            (ini.isoformat(), fim.isoformat(),), one=True,
        )["n"]
        atend_6m.append(n)
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1

    # status dos agendamentos do período (gráfico rosca)
    status_rows = db.query(
        "SELECT status, COUNT(*) AS n FROM agendamentos "
        "WHERE data BETWEEN ? AND ? GROUP BY status",
        (ini_s, fim_s,),
    )

    # distribuição de risco clínico (somente pacientes ativos)
    risco_rows = db.query(
        "SELECT r.nome, r.cor, COUNT(p.id) AS n FROM categorias_risco r "
        "LEFT JOIN pacientes p ON p.risco_id = r.id AND p.ativo = 1 "
        "GROUP BY r.id HAVING n > 0 ORDER BY r.ordem, r.nome COLLATE NOCASE"
    )
    risco_total = db.query(
        "SELECT COUNT(*) AS n FROM pacientes WHERE ativo = 1 AND risco_id IS NOT NULL",
        one=True,
    )["n"]

    if modo == "intervalo" or ini != hoje.replace(day=1) or fim != _ultimo_dia_mes(hoje.year, hoje.month):
        agenda_hoje = db.query(
            "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
            "JOIN pacientes p ON p.id = a.paciente_id "
            "WHERE a.data BETWEEN ? AND ? ORDER BY a.data, a.hora_inicio",
            (ini_s, fim_s,),
        )
        agenda_titulo = f"Agenda do período ({data_br(ini_s)} a {data_br(fim_s)})"
    else:
        agenda_hoje = db.query(
            "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
            "JOIN pacientes p ON p.id = a.paciente_id "
            "WHERE a.data = ? ORDER BY a.hora_inicio",
            (hoje.isoformat(),),
        )
        agenda_titulo = "Agenda de hoje"

    aniversariantes = [
        dict(r) for r in db.query("SELECT nome, data_nascimento FROM pacientes WHERE ativo=1")
        if mes_aniversario(r["data_nascimento"]) == ini.month
    ]
    aniversariantes.sort(key=lambda p: (p["data_nascimento"] or "")[5:10])

    if ini.day == 1 and fim == _ultimo_dia_mes(ini.year, ini.month):
        periodo_txt = f"{mes_nome(ini.month)} de {ini.year}"
    else:
        periodo_txt = f"{data_br(ini_s)} a {data_br(fim_s)}"

    return render_template(
        "dashboard.html",
        pagina="dashboard",
        hoje=hoje,
        comp=comp, de=de_txt, ate=ate_txt, modo=modo,
        periodo_txt=periodo_txt,
        agenda_titulo=agenda_titulo,
        mes_aniversario=f"{mes_nome(ini.month)}",
        kpi_pacientes=kpi_pacientes,
        kpi_hoje=kpi_hoje,
        kpi_mes=kpi_mes,
        rec_mes=rec_mes,
        des_mes=des_mes,
        resultado_mes=rec_mes - des_mes,
        ticket=ticket,
        labels_6m=labels_6m,
        receitas_6m=receitas_6m,
        despesas_6m=despesas_6m,
        atend_6m=atend_6m,
        status_mes=status_rows,
        risco_dist=risco_rows, risco_total=risco_total,
        agenda_hoje=agenda_hoje,
        aniversariantes=aniversariantes,
    )

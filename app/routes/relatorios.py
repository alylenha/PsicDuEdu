"""Relatórios imprimíveis (Ctrl+P / salvar como PDF no navegador)."""
from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, render_template, request

from app import db
from app.security import formatar_cpf
from app.utils import data_br, formatar_moeda, idade, parse_data

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")


def _periodo():
    hoje = date.today()
    de = parse_data(request.args.get("de")) if request.args.get("de") else hoje.replace(day=1)
    ate = parse_data(request.args.get("ate")) if request.args.get("ate") else hoje
    return de, ate


@bp.route("/")
def menu():
    de, ate = _periodo()
    return render_template("relatorios/menu.html", pagina="relatorios", de=de, ate=ate)


@bp.route("/faturamento")
def faturamento():
    de, ate = _periodo()
    linhas = db.query(
        "SELECT data, tipo, categoria, descricao, valor_centavos, forma_pagamento "
        "FROM lancamentos WHERE data BETWEEN ? AND ? ORDER BY data, tipo",
        (de.isoformat(), ate.isoformat()),
    )
    receitas = db.query(
        "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
        "WHERE tipo='receita' AND data BETWEEN ? AND ?",
        (de.isoformat(), ate.isoformat()), one=True,
    )["t"]
    despesas = db.query(
        "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
        "WHERE tipo='despesa' AND data BETWEEN ? AND ?",
        (de.isoformat(), ate.isoformat()), one=True,
    )["t"]
    return render_template("relatorios/faturamento.html", pagina="relatorios",
                           de=de, ate=ate, linhas=linhas, receitas=receitas,
                           despesas=despesas, resultado=receitas - despesas)


@bp.route("/dre")
def dre():
    """DRE simplificada: receitas por categoria - despesas por categoria."""
    de, ate = _periodo()
    receitas = db.query(
        "SELECT categoria, SUM(valor_centavos) AS total FROM lancamentos "
        "WHERE tipo='receita' AND data BETWEEN ? AND ? GROUP BY categoria ORDER BY total DESC",
        (de.isoformat(), ate.isoformat()),
    )
    despesas = db.query(
        "SELECT categoria, SUM(valor_centavos) AS total FROM lancamentos "
        "WHERE tipo='despesa' AND data BETWEEN ? AND ? GROUP BY categoria ORDER BY total DESC",
        (de.isoformat(), ate.isoformat()),
    )
    total_r = sum(r["total"] for r in receitas)
    total_d = sum(r["total"] for r in despesas)
    return render_template("relatorios/dre.html", pagina="relatorios", de=de, ate=ate,
                           receitas=receitas, despesas=despesas,
                           total_r=total_r, total_d=total_d,
                           resultado=total_r - total_d)


@bp.route("/atendimentos")
def atendimentos():
    de, ate = _periodo()
    linhas = db.query(
        "SELECT p.id AS paciente_id, p.nome, COUNT(*) AS sessoes, "
        "SUM(CASE WHEN a.status='faltou' THEN 1 ELSE 0 END) AS faltas, "
        "SUM(CASE WHEN a.pago=1 THEN a.valor_centavos ELSE 0 END) AS pago_centavos, "
        "SUM(CASE WHEN a.pago=0 AND a.status IN ('realizado','faltou') THEN a.valor_centavos ELSE 0 END) AS a_receber_centavos "
        "FROM agendamentos a JOIN pacientes p ON p.id = a.paciente_id "
        "WHERE a.data BETWEEN ? AND ? AND a.status IN ('realizado','faltou') "
        "GROUP BY p.id, p.nome ORDER BY p.nome COLLATE NOCASE",
        (de.isoformat(), ate.isoformat()),
    )
    return render_template("relatorios/atendimentos.html", pagina="relatorios",
                           de=de, ate=ate, linhas=linhas)


@bp.route("/nao_pagos")
def nao_pagos():
    de, ate = _periodo()
    linhas = db.query(
        "SELECT a.*, p.nome AS paciente_nome, p.telefone "
        "FROM agendamentos a JOIN pacientes p ON p.id = a.paciente_id "
        "WHERE a.pago = 0 AND a.status IN ('realizado','faltou') "
        "AND a.data BETWEEN ? AND ? ORDER BY a.data",
        (de.isoformat(), ate.isoformat()),
    )
    total = sum(a["valor_centavos"] for a in linhas)
    return render_template("relatorios/nao_pagos.html", pagina="relatorios",
                           de=de, ate=ate, linhas=linhas, total=total)


@bp.route("/ficha_paciente")
def ficha_paciente():
    pid = request.args.get("paciente_id", type=int)
    paciente = db.query("SELECT * FROM pacientes WHERE id = ?", (pid,), one=True) if pid else None
    pacientes = db.query("SELECT id, nome FROM pacientes ORDER BY nome COLLATE NOCASE")
    ags, n_pront, n_anexos = [], 0, 0
    if paciente:
        ags = db.query(
            "SELECT * FROM agendamentos WHERE paciente_id = ? ORDER BY data DESC LIMIT 30",
            (pid,),
        )
        n_pront = db.query("SELECT COUNT(*) AS n FROM prontuarios WHERE paciente_id = ?",
                           (pid,), one=True)["n"]
        n_anexos = db.query("SELECT COUNT(*) AS n FROM anexos WHERE paciente_id = ?",
                            (pid,), one=True)["n"]
    return render_template("relatorios/ficha_paciente.html", pagina="relatorios",
                           pacientes=pacientes, p=paciente, ags=ags,
                           n_pront=n_pront, n_anexos=n_anexos,
                           idade=idade, formatar_cpf=formatar_cpf, data_br=data_br,
                           hoje=date.today())


@bp.route("/agenda_dia")
def agenda_dia():
    dia = parse_data(request.args.get("dia")) if request.args.get("dia") else date.today()
    linhas = db.query(
        "SELECT a.*, p.nome AS paciente_nome, p.telefone "
        "FROM agendamentos a JOIN pacientes p ON p.id = a.paciente_id "
        "WHERE a.data = ? ORDER BY a.hora_inicio",
        (dia.isoformat(),),
    )
    return render_template("relatorios/agenda_dia.html", pagina="relatorios",
                           dia=dia, linhas=linhas, data_br=data_br)

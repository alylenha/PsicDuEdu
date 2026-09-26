"""Pacientes — cadastro, busca, edição, ativar/desativar.

Ao cadastrar, a senha padrão do prontuário é criada automaticamente:
4 primeiros dígitos do CPF + 4 últimos (sempre 8 caracteres).
"""
from __future__ import annotations

from flask import (Blueprint, flash, redirect, render_template, request,
                   url_for)

from app import db, security
from app.security import formatar_cpf

bp = Blueprint("pacientes", __name__)


def _paciente_do_form() -> dict:
    from app.utils import parse_data

    try:
        risco_id = int(request.form.get("risco_id") or 0) or None
    except ValueError:
        risco_id = None
    if risco_id:
        existe = db.query("SELECT id FROM categorias_risco WHERE id = ? AND ativa = 1",
                          (risco_id,), one=True)
        if not existe:
            risco_id = None
    return {
        "nome": (request.form.get("nome") or "").strip(),
        "cpf": security.apenas_digitos(request.form.get("cpf") or ""),
        "data_nascimento": parse_data(request.form.get("data_nascimento")).isoformat()
        if request.form.get("data_nascimento") else "",
        "telefone": (request.form.get("telefone") or "").strip(),
        "email": (request.form.get("email") or "").strip().lower(),
        "endereco": (request.form.get("endereco") or "").strip(),
        "seg_nome": (request.form.get("seg_nome") or "").strip(),
        "seg_telefone": (request.form.get("seg_telefone") or "").strip(),
        "observacoes": (request.form.get("observacoes") or "").strip(),
        "risco_id": risco_id,
    }


def _categorias_risco():
    return db.query(
        "SELECT * FROM categorias_risco WHERE ativa = 1 ORDER BY ordem, nome COLLATE NOCASE"
    )


def _valida(dados: dict, id_atual: int | None) -> bool:
    if not dados["nome"]:
        flash("Informe o nome do paciente.", "erro")
        return False
    if not security.validar_cpf(dados["cpf"]):
        flash("CPF inválido — verifique os dígitos.", "erro")
        return False
    existente = db.query(
        "SELECT id FROM pacientes WHERE cpf = ? AND id != ?",
        (dados["cpf"], id_atual or 0), one=True,
    )
    if existente:
        flash("Já existe um paciente cadastrado com este CPF.", "erro")
        return False
    return True


@bp.route("/pacientes")
def lista():
    q = (request.args.get("q") or "").strip()
    filtro = request.args.get("filtro", "ativos")
    sql = ("SELECT p.*, r.nome AS risco_nome, r.cor AS risco_cor "
           "FROM pacientes p LEFT JOIN categorias_risco r ON r.id = p.risco_id")
    conds, params = [], []
    if filtro == "ativos":
        conds.append("p.ativo = 1")
    elif filtro == "inativos":
        conds.append("p.ativo = 0")
    if q:
        conds.append("(p.nome LIKE ? OR p.cpf LIKE ?)")
        like = f"%{q}%"
        params += [like, like]
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY p.nome COLLATE NOCASE"
    pacientes = db.query(sql, params)
    return render_template("pacientes/lista.html", pagina="pacientes",
                           pacientes=pacientes, q=q, filtro=filtro,
                           formatar_cpf=formatar_cpf)


@bp.route("/pacientes/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        dados = _paciente_do_form()
        if _valida(dados, None):
            pid = db.execute(
                "INSERT INTO pacientes (nome, cpf, data_nascimento, telefone, email, "
                "endereco, seg_nome, seg_telefone, observacoes, risco_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (dados["nome"], dados["cpf"], dados["data_nascimento"], dados["telefone"],
                 dados["email"], dados["endereco"], dados["seg_nome"],
                 dados["seg_telefone"], dados["observacoes"], dados["risco_id"]),
            )
            # senha padrão do prontuário: 4 primeiros + 4 últimos dígitos do CPF
            senha = security.senha_padrao(dados["cpf"])
            salt = security.novo_salt()
            db.execute(
                "INSERT INTO acesso_prontuario (paciente_id, salt, hash_senha) VALUES (?, ?, ?)",
                (pid, salt, security.hash_senha(senha, salt)),
            )
            flash(f"Paciente cadastrado! Senha do prontuário: {senha} "
                  "(4 primeiros + 4 últimos dígitos do CPF). Anote e guarde com segurança.",
                  "sucesso")
            return redirect(url_for("pacientes.lista"))
    return render_template("pacientes/form.html", pagina="pacientes", p=None,
                           categorias_risco=_categorias_risco())


@bp.route("/pacientes/<int:pid>/editar", methods=["GET", "POST"])
def editar(pid: int):
    p = db.query("SELECT * FROM pacientes WHERE id = ?", (pid,), one=True)
    if p is None:
        flash("Paciente não encontrado.", "erro")
        return redirect(url_for("pacientes.lista"))
    if request.method == "POST":
        dados = _paciente_do_form()
        if _valida(dados, pid):
            db.execute(
                "UPDATE pacientes SET nome=?, cpf=?, data_nascimento=?, telefone=?, "
                "email=?, endereco=?, seg_nome=?, seg_telefone=?, observacoes=?, "
                "risco_id=? WHERE id=?",
                (dados["nome"], dados["cpf"], dados["data_nascimento"], dados["telefone"],
                 dados["email"], dados["endereco"], dados["seg_nome"],
                 dados["seg_telefone"], dados["observacoes"], dados["risco_id"], pid),
            )
            flash("Dados do paciente atualizados.", "sucesso")
            return redirect(url_for("pacientes.lista"))
        dados["id"] = pid
        return render_template("pacientes/form.html", pagina="pacientes", p=dados,
                               categorias_risco=_categorias_risco())
    return render_template("pacientes/form.html", pagina="pacientes", p=p,
                           formatar_cpf=formatar_cpf,
                           categorias_risco=_categorias_risco())


@bp.route("/pacientes/<int:pid>/alternar", methods=["POST"])
def alternar(pid: int):
    db.execute("UPDATE pacientes SET ativo = 1 - ativo WHERE id = ?", (pid,))
    flash("Situação do paciente alterada.", "sucesso")
    return redirect(url_for("pacientes.lista"))

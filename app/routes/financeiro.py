"""Financeiro — lançamentos efetivos + gestão de previsões a pagar/a receber."""
from __future__ import annotations

from datetime import datetime

from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, url_for)

from app import db
from app.utils import (CATEGORIAS_DESPESA, CATEGORIAS_RECEITA, FORMAS_PAGAMENTO,
                       data_br, parse_data, parse_moeda)

bp = Blueprint("financeiro", __name__, url_prefix="/financeiro")

STATUS_PREVISAO = ("prevista", "efetivada", "cancelada")
ORIGENS_PREVISAO = ("manual", "agendamento")


# ------------------------------------------------------------------
# Helpers de previsão
# ------------------------------------------------------------------

def _tem_coluna_lanc_previsao() -> bool:
    try:
        cols = {r["name"] for r in db.query("PRAGMA table_info(lancamentos)")}
        return "previsao_id" in cols
    except Exception:
        return False


def sincronizar_previsoes_agenda() -> int:
    """Garante uma previsão 'prevista' para cada agendamento com valor.

    Retorna a quantidade de previsões criadas. Usado pela tela de
    previsões (automático + manual) e pelos fluxos da agenda.
    """
    ags = db.query(
        "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
        "JOIN pacientes p ON p.id = a.paciente_id "
        "WHERE a.valor_centavos > 0 AND a.status != 'cancelado' AND (a.pago = 0 OR a.pago IS NULL)"
    )
    criadas = 0
    for ag in ags:
        existente = db.query(
            "SELECT * FROM previsoes WHERE agendamento_id = ? AND status = 'prevista' "
            "ORDER BY id DESC",
            (ag["id"],), one=True,
        )
        descricao = f"Sessão — {ag['paciente_nome']} ({data_br(ag['data'])})"
        if existente:
            if (existente["data_prevista"] != ag["data"]
                    or existente["valor_centavos"] != ag["valor_centavos"]):
                db.execute(
                    "UPDATE previsoes SET data_prevista = ?, valor_centavos = ?, "
                    "descricao = ?, paciente_id = ? WHERE id = ?",
                    (ag["data"], ag["valor_centavos"], descricao,
                     ag["paciente_id"], existente["id"]),
                )
            continue
        # não recria se já foi efetivada para este agendamento
        efetivada = db.query(
            "SELECT id FROM previsoes WHERE agendamento_id = ? AND status = 'efetivada'",
            (ag["id"],), one=True,
        )
        if efetivada:
            continue
        db.execute(
            "INSERT INTO previsoes (data_prevista, tipo, categoria, descricao, "
            "valor_centavos, status, origem, agendamento_id, paciente_id) "
            "VALUES (?, 'receita', 'Sessão', ?, ?, 'prevista', 'agendamento', ?, ?)",
            (ag["data"], descricao, ag["valor_centavos"], ag["id"], ag["paciente_id"]),
        )
        criadas += 1
    return criadas


def sincronizar_previsao_agendamento(ag_id: int) -> None:
    """Sincroniza (ou cancela) a previsão de um agendamento específico."""
    ag = db.query(
        "SELECT a.*, p.nome AS paciente_nome FROM agendamentos a "
        "JOIN pacientes p ON p.id = a.paciente_id WHERE a.id = ?",
        (ag_id,), one=True,
    )
    if ag is None:
        return
    prevista = db.query(
        "SELECT * FROM previsoes WHERE agendamento_id = ? AND status = 'prevista' "
        "ORDER BY id DESC",
        (ag_id,), one=True,
    )
    invalida = (not ag["valor_centavos"] or ag["status"] == "cancelado" or ag["pago"])
    if invalida:
        if prevista:
            db.execute("UPDATE previsoes SET status = 'cancelada' WHERE id = ?", (prevista["id"],))
        return
    descricao = f"Sessão — {ag['paciente_nome']} ({data_br(ag['data'])})"
    if prevista:
        db.execute(
            "UPDATE previsoes SET data_prevista = ?, valor_centavos = ?, descricao = ?, "
            "paciente_id = ? WHERE id = ?",
            (ag["data"], ag["valor_centavos"], descricao, ag["paciente_id"], prevista["id"]),
        )
        return
    efetivada = db.query(
        "SELECT id FROM previsoes WHERE agendamento_id = ? AND status = 'efetivada'",
        (ag_id,), one=True,
    )
    if efetivada:
        return
    db.execute(
        "INSERT INTO previsoes (data_prevista, tipo, categoria, descricao, "
        "valor_centavos, status, origem, agendamento_id, paciente_id) "
        "VALUES (?, 'receita', 'Sessão', ?, ?, 'prevista', 'agendamento', ?, ?)",
        (ag["data"], descricao, ag["valor_centavos"], ag["id"], ag["paciente_id"]),
    )


def _efetivar_previsao(prev, forma_pagamento: str = "") -> int:
    """Cria o lançamento idêntico à previsão e dá baixa (agenda inclusa)."""
    if prev["status"] != "prevista":
        raise ValueError("Só é possível efetivar previsões pendentes.")
    forma_pagamento = (forma_pagamento or "").strip()
    if not forma_pagamento:
        raise ValueError("Informe a forma de pagamento para efetivar.")
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tem_col = _tem_coluna_lanc_previsao()
    if tem_col:
        lid = db.execute(
            "INSERT INTO lancamentos (data, tipo, categoria, descricao, valor_centavos, "
            "forma_pagamento, agendamento_id, previsao_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (prev["data_prevista"], prev["tipo"], prev["categoria"], prev["descricao"],
             prev["valor_centavos"], forma_pagamento,
             prev["agendamento_id"], prev["id"]),
        )
    else:
        lid = db.execute(
            "INSERT INTO lancamentos (data, tipo, categoria, descricao, valor_centavos, "
            "forma_pagamento, agendamento_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (prev["data_prevista"], prev["tipo"], prev["categoria"], prev["descricao"],
             prev["valor_centavos"], forma_pagamento,
             prev["agendamento_id"]),
        )
    db.execute(
        "UPDATE previsoes SET status = 'efetivada', lancamento_id = ?, efetivado_em = ? "
        "WHERE id = ?",
        (lid, agora, prev["id"]),
    )
    if prev["agendamento_id"]:
        db.execute(
            "UPDATE agendamentos SET pago = 1, lancamento_id = ?, "
            "status = CASE WHEN status IN ('agendado','confirmado') THEN 'realizado' "
            "ELSE status END WHERE id = ?",
            (lid, prev["agendamento_id"]),
        )
    return lid


def buscar_previsoes_iguais(tipo: str, data_iso: str, valor_centavos: int):
    """Regra do popup: tipo + data + valor exatamente iguais e ainda prevista."""
    return db.query(
        "SELECT * FROM previsoes WHERE status = 'prevista' AND tipo = ? "
        "AND data_prevista = ? AND valor_centavos = ? ORDER BY data_prevista, id",
        (tipo, data_iso, valor_centavos),
    )


# ------------------------------------------------------------------
# Lançamentos (efetivos)
# ------------------------------------------------------------------

@bp.route("/")
def lista():
    de = request.args.get("de") or ""
    ate = request.args.get("ate") or ""
    tipo = request.args.get("tipo") or ""
    categoria = request.args.get("categoria") or ""

    por_pagina = (request.args.get("por_pagina") or "20").strip()
    if por_pagina not in ("20", "50", "100", "tudo"):
        por_pagina = "20"
    try:
        pag = max(int(request.args.get("pagina") or 1), 1)
    except ValueError:
        pag = 1

    sql_base = "FROM lancamentos WHERE 1=1"
    params: list = []
    if de:
        sql_base += " AND data >= ?"
        params.append(parse_data(de).isoformat())
    if ate:
        sql_base += " AND data <= ?"
        params.append(parse_data(ate).isoformat())
    if tipo in ("receita", "despesa"):
        sql_base += " AND tipo = ?"
        params.append(tipo)
    if categoria:
        sql_base += " AND categoria = ?"
        params.append(categoria)

    total = db.query(f"SELECT COUNT(*) AS n {sql_base}", params, one=True)["n"]
    if por_pagina == "tudo":
        total_paginas = 1
        pag = 1
        lancamentos = db.query(
            f"SELECT * {sql_base} ORDER BY data DESC, id DESC", params)
    else:
        limite = int(por_pagina)
        total_paginas = max((total + limite - 1) // limite, 1)
        pag = min(pag, total_paginas)
        lancamentos = db.query(
            f"SELECT * {sql_base} ORDER BY data DESC, id DESC LIMIT ? OFFSET ?",
            params + [limite, (pag - 1) * limite])
    receitas = db.query(
        "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
        "WHERE tipo='receita' AND data BETWEEN COALESCE(NULLIF(?, ''), '0000-01-01') "
        "AND COALESCE(NULLIF(?, ''), '9999-12-31')",
        (de, ate), one=True,
    )["t"]
    despesas = db.query(
        "SELECT COALESCE(SUM(valor_centavos),0) AS t FROM lancamentos "
        "WHERE tipo='despesa' AND data BETWEEN COALESCE(NULLIF(?, ''), '0000-01-01') "
        "AND COALESCE(NULLIF(?, ''), '9999-12-31')",
        (de, ate), one=True,
    )["t"]

    todas_categorias = sorted(set(CATEGORIAS_RECEITA + CATEGORIAS_DESPESA))
    editando = None
    try:
        editar_id = int(request.args.get("editar") or 0)
    except ValueError:
        editar_id = 0
    if editar_id:
        editando = db.query("SELECT * FROM lancamentos WHERE id = ?", (editar_id,), one=True)
    return render_template(
        "financeiro/lista.html", pagina="financeiro", aba="lancamentos",
        lancamentos=lancamentos,
        receitas=receitas, despesas=despesas, resultado=receitas - despesas,
        de=de, ate=ate, tipo=tipo, categoria=categoria,
        categorias=todas_categorias, formas=FORMAS_PAGAMENTO,
        cats_receita=CATEGORIAS_RECEITA, cats_despesa=CATEGORIAS_DESPESA,
        editando=editando, pag=pag, por_pagina=por_pagina,
        total=total, total_paginas=total_paginas,
    )


def _dados_form() -> dict:
    data = parse_data(request.form.get("data"))
    tipo = request.form.get("tipo")
    if tipo not in ("receita", "despesa"):
        raise ValueError("Tipo inválido.")
    valor = parse_moeda(request.form.get("valor") or "")
    categoria = (request.form.get("categoria") or "").strip()
    if not categoria:
        raise ValueError("Informe a categoria.")
    try:
        previsao_id = int(request.form.get("previsao_id") or 0)
    except ValueError:
        previsao_id = 0
    return {
        "data": data.isoformat(),
        "tipo": tipo,
        "categoria": categoria,
        "descricao": (request.form.get("descricao") or "").strip(),
        "valor_centavos": valor,
        "forma_pagamento": (request.form.get("forma_pagamento") or "").strip(),
        "previsao_id": previsao_id,
    }


@bp.route("/novo", methods=["POST"])
def novo():
    try:
        dados = _dados_form()
    except ValueError as e:
        flash(str(e), "erro")
        return redirect(url_for("financeiro.lista"))
    # Se o usuário confirmou o popup, vincula e efetiva a previsão indicada.
    if dados["previsao_id"]:
        prev = db.query("SELECT * FROM previsoes WHERE id = ?", (dados["previsao_id"],), one=True)
        if prev is not None and prev["status"] == "prevista":
            if not dados["forma_pagamento"]:
                flash("Informe a forma de pagamento para efetivar a previsão.", "erro")
                return redirect(url_for("financeiro.lista"))
            if (prev["tipo"] == dados["tipo"] and prev["data_prevista"] == dados["data"]
                    and prev["valor_centavos"] == dados["valor_centavos"]):
                tem_col = _tem_coluna_lanc_previsao()
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if tem_col:
                    lid = db.execute(
                        "INSERT INTO lancamentos (data, tipo, categoria, descricao, "
                        "valor_centavos, forma_pagamento, agendamento_id, previsao_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (dados["data"], dados["tipo"], dados["categoria"], dados["descricao"],
                         dados["valor_centavos"], dados["forma_pagamento"],
                         prev["agendamento_id"], prev["id"]),
                    )
                else:
                    lid = db.execute(
                        "INSERT INTO lancamentos (data, tipo, categoria, descricao, "
                        "valor_centavos, forma_pagamento, agendamento_id) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (dados["data"], dados["tipo"], dados["categoria"], dados["descricao"],
                         dados["valor_centavos"], dados["forma_pagamento"],
                         prev["agendamento_id"]),
                    )
                db.execute(
                    "UPDATE previsoes SET status = 'efetivada', lancamento_id = ?, "
                    "efetivado_em = ? WHERE id = ?",
                    (lid, agora, prev["id"]),
                )
                if prev["agendamento_id"]:
                    db.execute(
                        "UPDATE agendamentos SET pago = 1, lancamento_id = ?, "
                        "status = CASE WHEN status IN ('agendado','confirmado') "
                        "THEN 'realizado' ELSE status END WHERE id = ?",
                        (lid, prev["agendamento_id"]),
                    )
                flash("Lançamento registrado e previsão efetivada.", "sucesso")
                return redirect(url_for("financeiro.lista"))
            flash("A previsão mudou (data/valor/tipo). Lançamento feito sem vínculo.", "erro")
    tem_col = _tem_coluna_lanc_previsao()
    if tem_col:
        db.execute(
            "INSERT INTO lancamentos (data, tipo, categoria, descricao, valor_centavos, "
            "forma_pagamento, previsao_id) VALUES (?, ?, ?, ?, ?, ?, NULL)",
            (dados["data"], dados["tipo"], dados["categoria"], dados["descricao"],
             dados["valor_centavos"], dados["forma_pagamento"]),
        )
    else:
        db.execute(
            "INSERT INTO lancamentos (data, tipo, categoria, descricao, valor_centavos, forma_pagamento) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dados["data"], dados["tipo"], dados["categoria"], dados["descricao"],
             dados["valor_centavos"], dados["forma_pagamento"]),
        )
    flash("Lançamento registrado.", "sucesso")
    return redirect(url_for("financeiro.lista"))


@bp.route("/<int:lid>/editar", methods=["POST"])
def editar(lid: int):
    """Atualiza um lançamento existente (mesmo formulário do 'Novo lançamento')."""
    lanc = db.query("SELECT * FROM lancamentos WHERE id = ?", (lid,), one=True)
    if lanc is None:
        flash("Lançamento não encontrado.", "erro")
        return redirect(url_for("financeiro.lista"))
    try:
        dados = _dados_form()
    except ValueError as e:
        flash(str(e), "erro")
        return redirect(url_for("financeiro.lista", editar=lid))
    db.execute(
        "UPDATE lancamentos SET data = ?, tipo = ?, categoria = ?, descricao = ?, "
        "valor_centavos = ?, forma_pagamento = ? WHERE id = ?",
        (dados["data"], dados["tipo"], dados["categoria"], dados["descricao"],
         dados["valor_centavos"], dados["forma_pagamento"], lid),
    )
    # espelha na previsão efetivada vinculada, se houver
    try:
        prev_id = lanc["previsao_id"]
    except Exception:
        prev_id = None
    prev = None
    if prev_id:
        prev = db.query("SELECT * FROM previsoes WHERE id = ?", (prev_id,), one=True)
    if prev is None:
        prev = db.query("SELECT * FROM previsoes WHERE lancamento_id = ?", (lid,), one=True)
    if prev is not None:
        db.execute(
            "UPDATE previsoes SET data_prevista = ?, tipo = ?, categoria = ?, "
            "descricao = ?, valor_centavos = ? WHERE id = ?",
            (dados["data"], dados["tipo"], dados["categoria"], dados["descricao"],
             dados["valor_centavos"], prev["id"]),
        )
    flash("Lançamento atualizado.", "sucesso")
    return redirect(url_for("financeiro.lista"))


@bp.route("/<int:lid>/excluir", methods=["POST"])
def excluir(lid: int):
    # se o lançamento veio de uma sessão da agenda, libera a sessão para nova baixa
    ag = db.query("SELECT id FROM agendamentos WHERE lancamento_id = ?", (lid,), one=True)
    if ag:
        db.execute(
            "UPDATE agendamentos SET pago = 0, lancamento_id = NULL WHERE id = ?",
            (ag["id"],),
        )
    prev = db.query("SELECT * FROM previsoes WHERE lancamento_id = ?", (lid,), one=True)
    if prev is not None:
        db.execute(
            "UPDATE previsoes SET status = 'prevista', lancamento_id = NULL, "
            "efetivado_em = NULL WHERE id = ?",
            (prev["id"],),
        )
        if prev["agendamento_id"]:
            db.execute(
                "UPDATE agendamentos SET pago = 0, lancamento_id = NULL WHERE id = ?",
                (prev["agendamento_id"],),
            )
    db.execute("DELETE FROM lancamentos WHERE id = ?", (lid,))
    flash("Lançamento excluído.", "sucesso")
    return redirect(request.referrer or url_for("financeiro.lista"))


# ------------------------------------------------------------------
# Previsões (contas a pagar / a receber)
# ------------------------------------------------------------------

@bp.route("/previsoes")
def previsoes():
    criadas = sincronizar_previsoes_agenda()
    if criadas:
        flash(f"{criadas} previsão(ões) gerada(s) a partir da agenda.", "sucesso")
    de = request.args.get("de") or ""
    ate = request.args.get("ate") or ""
    tipo = request.args.get("tipo") or ""
    status = request.args.get("status") or ""
    origem = request.args.get("origem") or ""

    sql = ("SELECT pr.*, p.nome AS paciente_nome FROM previsoes pr "
           "LEFT JOIN pacientes p ON p.id = pr.paciente_id WHERE 1=1")
    params: list = []
    if de:
        sql += " AND pr.data_prevista >= ?"
        params.append(parse_data(de).isoformat())
    if ate:
        sql += " AND pr.data_prevista <= ?"
        params.append(parse_data(ate).isoformat())
    if tipo in ("receita", "despesa"):
        sql += " AND pr.tipo = ?"
        params.append(tipo)
    if status in STATUS_PREVISAO:
        sql += " AND pr.status = ?"
        params.append(status)
    if origem in ORIGENS_PREVISAO:
        sql += " AND pr.origem = ?"
        params.append(origem)
    sql += " ORDER BY pr.data_prevista, pr.id"
    itens = db.query(sql, params)

    total_previsto = sum(r["valor_centavos"] for r in itens if r["status"] == "prevista")
    total_receita = sum(r["valor_centavos"] for r in itens
                        if r["status"] == "prevista" and r["tipo"] == "receita")
    total_despesa = sum(r["valor_centavos"] for r in itens
                        if r["status"] == "prevista" and r["tipo"] == "despesa")
    pacientes = db.query("SELECT id, nome FROM pacientes ORDER BY nome COLLATE NOCASE")
    todas_categorias = sorted(set(CATEGORIAS_RECEITA + CATEGORIAS_DESPESA))
    return render_template(
        "financeiro/previsoes.html", pagina="financeiro", aba="previsoes",
        itens=itens, total_previsto=total_previsto,
        total_receita=total_receita, total_despesa=total_despesa,
        de=de, ate=ate, tipo=tipo, status=status, origem=origem,
        pacientes=pacientes, categorias=todas_categorias,
        formas=FORMAS_PAGAMENTO,
    )


@bp.route("/previsoes/novo", methods=["POST"])
def previsao_novo():
    try:
        data = parse_data(request.form.get("data"))
        tipo = request.form.get("tipo")
        if tipo not in ("receita", "despesa"):
            raise ValueError("Tipo inválido.")
        valor = parse_moeda(request.form.get("valor") or "")
        categoria = (request.form.get("categoria") or "").strip()
        if not categoria:
            raise ValueError("Informe a categoria.")
        try:
            paciente_id = int(request.form.get("paciente_id") or 0) or None
        except ValueError:
            paciente_id = None
        descricao = (request.form.get("descricao") or "").strip()
    except ValueError as e:
        flash(str(e), "erro")
        return redirect(url_for("financeiro.previsoes"))
    db.execute(
        "INSERT INTO previsoes (data_prevista, tipo, categoria, descricao, valor_centavos, "
        "status, origem, paciente_id) VALUES (?, ?, ?, ?, ?, 'prevista', 'manual', ?)",
        (data.isoformat(), tipo, categoria, descricao, valor, paciente_id),
    )
    flash("Previsão registrada.", "sucesso")
    return redirect(url_for("financeiro.previsoes"))


@bp.route("/previsoes/<int:pid>/efetivar", methods=["POST"])
def previsao_efetivar(pid: int):
    prev = db.query("SELECT * FROM previsoes WHERE id = ?", (pid,), one=True)
    if prev is None:
        flash("Previsão não encontrada.", "erro")
        return redirect(url_for("financeiro.previsoes"))
    try:
        _efetivar_previsao(prev, request.form.get("forma_pagamento") or "")
    except ValueError as e:
        flash(str(e), "erro")
        return redirect(request.referrer or url_for("financeiro.previsoes"))
    flash("Previsão efetivada e lançamento criado.", "sucesso")
    return redirect(request.referrer or url_for("financeiro.previsoes"))


@bp.route("/previsoes/<int:pid>/cancelar", methods=["POST"])
def previsao_cancelar(pid: int):
    prev = db.query("SELECT * FROM previsoes WHERE id = ?", (pid,), one=True)
    if prev is None:
        flash("Previsão não encontrada.", "erro")
        return redirect(url_for("financeiro.previsoes"))
    if prev["status"] == "efetivada":
        flash("Previsão já efetivada: exclua o lançamento para reabri-la.", "erro")
        return redirect(request.referrer or url_for("financeiro.previsoes"))
    novo_status = "prevista" if prev["status"] == "cancelada" else "cancelada"
    db.execute("UPDATE previsoes SET status = ? WHERE id = ?", (novo_status, pid))
    flash(f"Previsão {novo_status}.", "sucesso")
    return redirect(request.referrer or url_for("financeiro.previsoes"))


@bp.route("/previsoes/<int:pid>/excluir", methods=["POST"])
def previsao_excluir(pid: int):
    prev = db.query("SELECT * FROM previsoes WHERE id = ?", (pid,), one=True)
    if prev is None:
        flash("Previsão não encontrada.", "erro")
        return redirect(url_for("financeiro.previsoes"))
    if prev["status"] == "efetivada":
        flash("Previsão efetivada não pode ser excluída: exclua o lançamento.", "erro")
        return redirect(request.referrer or url_for("financeiro.previsoes"))
    db.execute("DELETE FROM previsoes WHERE id = ?", (pid,))
    flash("Previsão excluída.", "sucesso")
    return redirect(request.referrer or url_for("financeiro.previsoes"))


@bp.route("/api/checar-previsao")
def api_checar_previsao():
    """API do popup: lista previstas com tipo+data+valor exatamente iguais."""
    tipo = (request.args.get("tipo") or "").strip()
    data_txt = (request.args.get("data") or "").strip()
    valor_txt = (request.args.get("valor") or "").strip()
    if tipo not in ("receita", "despesa") or not data_txt or not valor_txt:
        return jsonify({"previsoes": []})
    try:
        data_iso = parse_data(data_txt).isoformat()
        valor = parse_moeda(valor_txt)
    except ValueError:
        return jsonify({"previsoes": []})
    rows = buscar_previsoes_iguais(tipo, data_iso, valor)
    return jsonify({"previsoes": [
        {"id": r["id"], "data": data_br(r["data_prevista"]),
         "descricao": r["descricao"] or "—",
         "categoria": r["categoria"], "origem": r["origem"]}
        for r in rows
    ]})

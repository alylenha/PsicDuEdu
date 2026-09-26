"""Prontuário — desbloqueio por senha, evoluções criptografadas e anexos.

O conteúdo é armazenado cifrado (Fernet, chave derivada da senha do paciente)
e decifrado apenas para exibição. A senha é solicitada em cada nova abertura
e fica válida por 40 minutos (janela deslizante renovada a cada acesso) —
depois o prontuário volta ao estado bloqueado e a senha é exigida de novo.
"""
from __future__ import annotations

import secrets
from datetime import date

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   send_file, url_for)

from app import db, security, unlock
from app.paths import ANEXOS_DIR, ensure_dirs
from app.utils import data_br

bp = Blueprint("prontuario", __name__, url_prefix="/prontuario")


def _carregar_paciente(pid: int):
    p = db.query("SELECT * FROM pacientes WHERE id = ?", (pid,), one=True)
    if p is None:
        abort(404)
    return p


def _salt_hash(pid: int):
    a = db.query(
        "SELECT salt, hash_senha FROM acesso_prontuario WHERE paciente_id = ?",
        (pid,), one=True,
    )
    if a is None:
        abort(404)
    return bytes(a["salt"]), bytes(a["hash_senha"])


@bp.route("/<int:pid>")
def ver(pid: int):
    p = _carregar_paciente(pid)
    salt, _hash = _salt_hash(pid)
    senha = unlock.senha_valida_agora(pid)
    aberto = senha is not None

    evolucoes: list[dict] = []
    anexos: list = []
    if aberto:
        rows = db.query(
            "SELECT * FROM prontuarios WHERE paciente_id = ? ORDER BY data_sessao DESC, id DESC",
            (pid,),
        )
        for r in rows:
            try:
                texto = security.decifrar(r["conteudo_criptografado"], senha, salt)
            except security.InvalidToken:
                texto = "⚠️ Não foi possível decifrar este registro com a senha atual."
            evolucoes.append(dict(r, conteudo=texto))
        anexos = db.query("SELECT * FROM anexos WHERE paciente_id = ? ORDER BY id DESC", (pid,))

    total = db.query(
        "SELECT COUNT(*) AS n FROM prontuarios WHERE paciente_id = ?", (pid,), one=True
    )["n"]
    return render_template(
        "prontuario/ver.html", pagina="prontuario", p=p, aberto=aberto,
        evolucoes=evolucoes, anexos=anexos, total=total,
        minutos_restantes=unlock.minutos_restantes(pid),
    )


@bp.route("/<int:pid>/desbloquear", methods=["POST"])
def desbloquear(pid: int):
    _carregar_paciente(pid)
    senha = (request.form.get("senha") or "").strip()
    salt, hash_esperado = _salt_hash(pid)
    if security.verificar_senha(senha, salt, hash_esperado):
        unlock.marcar_aberto(pid, senha)
        flash("Prontuário desbloqueado por 40 minutos (renovados a cada acesso).", "sucesso")
    else:
        flash("Senha incorreta. O prontuário permanece bloqueado.", "erro")
    return redirect(url_for("prontuario.ver", pid=pid))


@bp.route("/<int:pid>/bloquear", methods=["POST"])
def bloquear(pid: int):
    unlock.bloquear(pid)
    flash("Prontuário bloqueado — a senha será solicitada na próxima abertura.", "sucesso")
    return redirect(url_for("prontuario.ver", pid=pid))


@bp.route("/<int:pid>/nova_evolucao", methods=["POST"])
def nova_evolucao(pid: int):
    salt, _hash = _salt_hash(pid)
    senha = unlock.senha_valida_agora(pid)
    if senha is None:
        abort(403)
    texto = (request.form.get("conteudo") or "").strip()
    if not texto:
        flash("Escreva o texto da evolução antes de salvar.", "erro")
        return redirect(url_for("prontuario.ver", pid=pid))
    token = security.cifrar(texto, senha, salt)
    db.execute(
        "INSERT INTO prontuarios (paciente_id, data_sessao, tipo, conteudo_criptografado) "
        "VALUES (?, ?, ?, ?)",
        (pid, request.form.get("data_sessao") or date.today().isoformat(),
         request.form.get("tipo") or "Evolução", token),
    )
    flash("Evolução salva e criptografada.", "sucesso")
    return redirect(url_for("prontuario.ver", pid=pid))


@bp.route("/<int:pid>/trocar_senha", methods=["POST"])
def trocar_senha(pid: int):
    atual = (request.form.get("senha_atual") or "").strip()
    nova = (request.form.get("nova_senha") or "").strip()
    salt, hash_atual = _salt_hash(pid)
    if not security.verificar_senha(atual, salt, hash_atual):
        flash("Senha atual incorreta — nada foi alterado.", "erro")
        return redirect(url_for("prontuario.ver", pid=pid))
    if not security.senha_valida(nova):
        flash("A nova senha deve ter pelo menos 8 caracteres.", "erro")
        return redirect(url_for("prontuario.ver", pid=pid))
    _recriptografar(pid, senha_antiga=atual, senha_nova=nova, salt_antigo=salt)
    unlock.marcar_aberto(pid, nova)  # nova senha válida por mais 40 min
    flash("Senha trocada: prontuário re-criptografado com a nova senha.", "sucesso")
    return redirect(url_for("prontuario.ver", pid=pid))


def _recriptografar(pid: int, senha_antiga: str, senha_nova: str, salt_antigo: bytes) -> None:
    """Troca a senha e re-criptografa evoluções + anexos."""
    ensure_dirs()
    novo_salt = security.novo_salt()
    pasta = ANEXOS_DIR / str(pid)
    pasta.mkdir(parents=True, exist_ok=True)

    # decifra evoluções com a senha antiga
    rows = db.query(
        "SELECT id, conteudo_criptografado FROM prontuarios WHERE paciente_id = ?", (pid,)
    )
    textos = [
        security.decifrar(r["conteudo_criptografado"], senha_antiga, salt_antigo) for r in rows
    ]

    # decifra anexos do disco
    anexos = db.query("SELECT id, nome_arquivo FROM anexos WHERE paciente_id = ?", (pid,))
    blobs = []
    for a in anexos:
        caminho = pasta / a["nome_arquivo"]
        blobs.append((a["id"], caminho,
                      security.decifrar_bytes(caminho.read_bytes(), senha_antiga, salt_antigo)))

    # grava tudo com a nova chave
    for r, texto in zip(rows, textos):
        db.execute(
            "UPDATE prontuarios SET conteudo_criptografado = ? WHERE id = ?",
            (security.cifrar(texto, senha_nova, novo_salt), r["id"]),
        )
    for aid, caminho, dados in blobs:
        novo_nome = f"{secrets.token_hex(16)}.bin"
        (pasta / novo_nome).write_bytes(security.cifrar_bytes(dados, senha_nova, novo_salt))
        caminho.unlink(missing_ok=True)
        db.execute("UPDATE anexos SET nome_arquivo = ? WHERE id = ?", (novo_nome, aid))

    db.execute(
        "UPDATE acesso_prontuario SET salt=?, hash_senha=?, "
        "atualizada_em=datetime('now','localtime') WHERE paciente_id=?",
        (novo_salt, security.hash_senha(senha_nova, novo_salt), pid),
    )


@bp.route("/<int:pid>/anexos", methods=["POST"])
def enviar_anexo(pid: int):
    arquivo = request.files.get("arquivo")
    if not arquivo or not arquivo.filename:
        flash("Selecione um arquivo para anexar.", "erro")
        return redirect(url_for("prontuario.ver", pid=pid))
    salt, _hash = _salt_hash(pid)
    senha = unlock.senha_valida_agora(pid)
    if senha is None:
        abort(403)
    ensure_dirs()
    pasta = ANEXOS_DIR / str(pid)
    pasta.mkdir(parents=True, exist_ok=True)
    nome_cifrado = f"{secrets.token_hex(16)}.bin"
    dados = arquivo.read()
    (pasta / nome_cifrado).write_bytes(security.cifrar_bytes(dados, senha, salt))
    db.execute(
        "INSERT INTO anexos (paciente_id, nome_original, nome_arquivo, tamanho_bytes) "
        "VALUES (?, ?, ?, ?)",
        (pid, arquivo.filename, nome_cifrado, len(dados)),
    )
    flash("Anexo enviado e criptografado.", "sucesso")
    return redirect(url_for("prontuario.ver", pid=pid))


@bp.route("/<int:pid>/anexos/<int:aid>/baixar")
def baixar_anexo(pid: int, aid: int):
    a = db.query("SELECT * FROM anexos WHERE id = ? AND paciente_id = ?", (aid, pid), one=True)
    if a is None:
        abort(404)
    salt, _hash = _salt_hash(pid)
    senha = unlock.senha_valida_agora(pid)
    if senha is None:
        abort(403)
    caminho = ANEXOS_DIR / str(pid) / a["nome_arquivo"]
    from io import BytesIO

    dados = security.decifrar_bytes(caminho.read_bytes(), senha, salt)
    return send_file(BytesIO(dados), download_name=a["nome_original"], as_attachment=True)


@bp.route("/<int:pid>/anexos/<int:aid>/excluir", methods=["POST"])
def excluir_anexo(pid: int, aid: int):
    senha = unlock.senha_valida_agora(pid)
    if senha is None:
        abort(403)
    a = db.query("SELECT * FROM anexos WHERE id = ? AND paciente_id = ?", (aid, pid), one=True)
    if a is None:
        abort(404)
    (ANEXOS_DIR / str(pid) / a["nome_arquivo"]).unlink(missing_ok=True)
    db.execute("DELETE FROM anexos WHERE id = ?", (aid,))
    flash("Anexo excluído.", "sucesso")
    return redirect(url_for("prontuario.ver", pid=pid))

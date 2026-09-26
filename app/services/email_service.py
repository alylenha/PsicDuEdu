"""Envio de e-mails de aviso (SMTP — Gmail, Outlook ou qualquer servidor).

Opcional: se o SMTP não estiver configurado na tela Integrações, nada é enviado.
Recomendamos usar uma "senha de app" do provedor (Gmail/Outlook) — gratuita.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app import db
from app.utils import data_br, formatar_moeda, hora_br


def smtp_configurado() -> bool:
    return bool(db.get_config("smtp_host")) and bool(db.get_config("smtp_usuario"))


def enviar_mail(msg: EmailMessage) -> bool:
    host = db.get_config("smtp_host")
    porta = int(db.get_config("smtp_porta", "587"))
    usuario = db.get_config("smtp_usuario")
    senha = db.get_config("smtp_senha")
    tls = db.get_config("smtp_tls", "1") == "1"

    if tls:
        with smtplib.SMTP(host, porta, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.login(usuario, senha)
            server.send_message(msg)
    else:
        with smtplib.SMTP_SSL(host, porta, timeout=20) as server:
            server.login(usuario, senha)
            server.send_message(msg)
    return True


def _msg(destinatarios: list[str], assunto: str, corpo: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = db.get_config("smtp_usuario")
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(corpo)
    return msg


def _clinica_destinatarios() -> list[str]:
    dest = [e for e in [db.get_config("avisos_email_clinica")] if e]
    return dest


def avisar_novo_agendamento(ag) -> bool:
    """Sessão marcada/remarcada."""
    if not smtp_configurado():
        return False
    paciente = db.query("SELECT * FROM pacientes WHERE id = ?", (ag["paciente_id"],), one=True)
    dests = [e for e in [paciente["email"] if paciente else None] + _clinica_destinatarios() if e]
    if not dests:
        return False
    assunto = f"Sessão agendada — {data_br(ag['data'])} às {hora_br(ag['hora_inicio'])}"
    corpo = (
        f"Olá{', ' + paciente['nome'] if paciente else ''}!\n\n"
        f"Sua sessão está agendada para {data_br(ag['data'])} das "
        f"{hora_br(ag['hora_inicio'])} às {hora_br(ag['hora_fim'])}.\n"
        f"Tipo: {ag['tipo']}\n"
        f"Profissional: {ag['profissional'] or '—'}\n\n"
        f"Para remarcar ou cancelar, entre em contato com a clínica.\n\n"
        f"— {db.get_config('clinica_nome', 'PsicoClin')}"
    )
    enviar_mail(_msg(dests, assunto, corpo))
    return True


def avisar_cancelamento(ag, motivo: str = "") -> bool:
    if not smtp_configurado():
        return False
    paciente = db.query("SELECT * FROM pacientes WHERE id = ?", (ag["paciente_id"],), one=True)
    dests = [e for e in [paciente["email"] if paciente else None] + _clinica_destinatarios() if e]
    if not dests:
        return False
    assunto = f"Sessão cancelada — {data_br(ag['data'])} às {hora_br(ag['hora_inicio'])}"
    corpo = (
        f"Olá{', ' + paciente['nome'] if paciente else ''}.\n\n"
        f"A sessão de {data_br(ag['data'])} às {hora_br(ag['hora_inicio'])} foi cancelada"
        + (f". Motivo: {motivo}" if motivo else ".")
        + "\n\nPara reagendar, entre em contato com a clínica.\n\n"
        f"— {db.get_config('clinica_nome', 'PsicoClin')}"
    )
    enviar_mail(_msg(dests, assunto, corpo))
    return True


def avisar_falta(ag) -> bool:
    """Aviso de falta — vai para a clínica (e opcionalmente para o paciente)."""
    if not smtp_configurado():
        return False
    paciente = db.query("SELECT * FROM pacientes WHERE id = ?", (ag["paciente_id"],), one=True)
    incluir_paciente = db.get_config("avisos_email_paciente_falta", "0") == "1"
    dests = _clinica_destinatarios()
    if incluir_paciente and paciente and paciente["email"]:
        dests.append(paciente["email"])
    if not dests:
        return False
    valor = formatar_moeda(ag["valor_centavos"]) if ag["valor_centavos"] else "não definido"
    assunto = f"Falta registrada — {paciente['nome'] if paciente else 'paciente'} — {data_br(ag['data'])}"
    corpo = (
        f"A sessão de {data_br(ag['data'])} às {hora_br(ag['hora_inicio'])} "
        f"foi registrada como FALTA.\n"
        f"Paciente: {paciente['nome'] if paciente else '?'}\n"
        f"Valor da sessão: {valor}\n\n"
        f"Lembre-se de registrar a cobrança (cláusula de faltas) se aplicável.\n\n"
        f"— {db.get_config('clinica_nome', 'PsicoClin')}"
    )
    enviar_mail(_msg(dests, assunto, corpo))
    return True

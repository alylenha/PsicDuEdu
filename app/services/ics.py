"""Geração de arquivos .ics (Google Agenda, Apple Agenda, Outlook)."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.utils import hora_br


def _esc(texto: str) -> str:
    """Escapa texto conforme RFC 5545."""
    return (
        (texto or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _dt_fmt(d: str, h: str) -> str:
    """'2026-09-28', '14:00' -> '20260928T140000' (flutuante, hora local)."""
    iso = f"{d}T{h}:00" if len(h) == 5 else f"{d}T{h}:00:00"
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%Y%m%dT%H%M%S")


def gerar_ics(agendamentos: list, titulo_clinica: str = "PsicoClin") -> str:
    """Gera o conteúdo .ics de uma lista de agendamentos (objetos sqlite3.Row)."""
    agora = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    linhas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PsicoClin ERP//Agenda//PT-BR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(titulo_clinica)} — Agenda",
    ]
    for a in agendamentos:
        inicio = _dt_fmt(a["data"], a["hora_inicio"])
        h_ini = datetime.strptime(a["hora_inicio"][:5], "%H:%M")
        h_fim = datetime.strptime(a["hora_fim"][:5], "%H:%M")
        duracao = max(0, int((h_fim - h_ini).total_seconds() // 60))
        fim = (datetime.fromisoformat(f"{a['data']}T{a['hora_inicio'][:5]}:00")
               + timedelta(minutes=duracao)).strftime("%Y%m%dT%H%M%S")
        linhas += [
            "BEGIN:VEVENT",
            f"UID:psiclin-{a['id']}@psiclin.local",
            f"DTSTAMP:{agora}",
            f"DTSTART:{inicio}",
            f"DTEND:{fim}",
            f"SUMMARY:{_esc('Sessão — ' + (a['paciente_nome'] if 'paciente_nome' in a.keys() else a['tipo']))}",
            f"DESCRIPTION:{_esc(a['observacoes'] or '')}",
            "END:VEVENT",
        ]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(linhas) + "\r\n"

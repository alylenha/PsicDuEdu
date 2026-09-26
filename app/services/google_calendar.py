"""Integração opcional com o Google Agenda.

Modo 1 — Sem configuração (sempre disponível):
  - Link "Adicionar ao Google Agenda" por consulta (template do Google).
  - Exportação .ics da agenda (ver services/ics.py).

Modo 2 — Sincronização completa (opcional, exige OAuth do Google Cloud Console,
gratuito): o usuário cola client_id/client_secret na tela Integrações e clica
"Conectar". O token fica salvo em data/google_token.json (local).
"""
from __future__ import annotations

import json
from urllib.parse import urlencode

from app import db

ESCOPO = "https://www.googleapis.com/auth/calendar.events"
TOKEN_PATH = None  # definido em runtime via app.paths


def link_google_agenda(ag, clinica: str = "PsicoClin") -> str:
    """Link universal 'Adicionar ao Google Agenda' (sem autenticação)."""
    from app.utils import hora_br

    def fmt(data: str, hora: str) -> str:
        return f"{data.replace('-', '')}T{hora_br(hora).replace(':', '')}00"

    inicio = fmt(ag["data"], ag["hora_inicio"])
    fim = fmt(ag["data"], ag["hora_fim"])
    params = {
        "action": "TEMPLATE",
        "text": f"Sessão — {ag.get('paciente_nome', '') or ag['tipo']}",
        "dates": f"{inicio}/{fim}",
        "details": f"{ag['tipo']} — {clinica}. {ag['observacoes'] or ''}".strip(),
        "location": db.get_config("clinica_endereco", ""),
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


# ------------------------------------------------------------------
# Modo 2: sincronização completa (opcional)
# ------------------------------------------------------------------

def oauth_configurado() -> bool:
    return bool(db.get_config("google_client_id")) and bool(db.get_config("google_client_secret"))


def token_salvo() -> bool:
    from app.paths import DATA_DIR
    return (DATA_DIR / "google_token.json").exists()


def construir_fluxo():
    """Cria o fluxo OAuth do Google (requer google-auth-oauthlib instalado)."""
    from google_auth_oauthlib.flow import Flow

    client_config = {
        "web": {
            "client_id": db.get_config("google_client_id"),
            "client_secret": db.get_config("google_client_secret"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://127.0.0.1:5050/integracoes/google/callback"],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=[ESCOPO],
        redirect_uri="http://127.0.0.1:5050/integracoes/google/callback",
    )


def salvar_token(creds) -> None:
    from app.paths import DATA_DIR

    (DATA_DIR / "google_token.json").write_text(json.dumps({
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }), encoding="utf-8")


def obter_credenciais():
    """Carrega credenciais salvas (renova se necessário)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from app.paths import DATA_DIR

    path = DATA_DIR / "google_token.json"
    if not path.exists():
        return None
    dados = json.loads(path.read_text(encoding="utf-8"))
    creds = Credentials(
        token=dados.get("token"),
        refresh_token=dados.get("refresh_token"),
        token_uri=dados.get("token_uri"),
        scopes=[ESCOPO],
    )
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        salvar_token(creds)
    return creds


def sincronizar_agendamento(ag) -> str | None:
    """Cria/atualiza o evento no Google Agenda. Retorna o event_id ou None."""
    if not (oauth_configurado() and token_salvo()):
        return None
    try:
        from googleapiclient.discovery import build

        creds = obter_credenciais()
        if creds is None:
            return None
        service = build("calendar", "v3", credentials=creds)
        from app.utils import hora_br

        evento = {
            "summary": f"Sessão — {ag.get('paciente_nome', '') or ag['tipo']}",
            "description": f"{ag['tipo']}. {ag['observacoes'] or ''}".strip(),
            "start": {"dateTime": f"{ag['data']}T{hora_br(ag['hora_inicio'])}:00",
                      "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": f"{ag['data']}T{hora_br(ag['hora_fim'])}:00",
                    "timeZone": "America/Sao_Paulo"},
        }
        cal_id = db.get_config("google_calendar_id", "primary")
        if ag["google_event_id"]:
            service.events().update(
                calendarId=cal_id, eventId=ag["google_event_id"], body=evento
            ).execute()
            return ag["google_event_id"]
        criado = service.events().insert(calendarId=cal_id, body=evento).execute()
        return criado.get("id")
    except Exception:
        return None


def remover_evento(google_event_id: str) -> None:
    if not (oauth_configurado() and token_salvo() and google_event_id):
        return
    try:
        from googleapiclient.discovery import build

        creds = obter_credenciais()
        if creds is None:
            return
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(
            calendarId=db.get_config("google_calendar_id", "primary"),
            eventId=google_event_id,
        ).execute()
    except Exception:
        pass

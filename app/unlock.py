"""Desbloqueio do prontuário com memória limitada por tempo.

Política: a senha é solicitada em cada nova abertura do prontuário e, após
validada, fica guardada APENAS no cookie de sessão do navegador (assinado
pelo Flask) por uma janela de 40 minutos, renovada a cada acesso (sliding).
Expirada a janela (ou fechando o navegador/reiniciando o servidor), o
prontuário volta a ficar bloqueado e a senha é exigida novamente.

Nada é gravado em disco. O cookie nunca sai da máquina local (servidor em
127.0.0.1) e os testes manipulam o relógio injetando a fonte de tempo.

A senha também é derivável do CPF (padrão = 4 primeiros + 4 últimos dígitos).
"""
from __future__ import annotations

import time as _modulo_tempo
from typing import Callable

from flask import session

TEMPO_MEMORIA_MIN = 40  # janela de memória da senha, em minutos

_SESSAO_CHAVE = "prontuario_senhas"

# Fonte de tempo injetável (testes). Em produção usa time.time().
_fonte_tempo: Callable[[], float] = _modulo_tempo.time


def definir_fonte_tempo(fn: Callable[[], float] | None) -> None:
    """Injeta um relógio (ex.: fake para testes). None restaura o real."""
    global _fonte_tempo
    _fonte_tempo = fn or _modulo_tempo.time


def _agora() -> float:
    return _fonte_tempo()


def _dict() -> dict:
    return dict(session.get(_SESSAO_CHAVE, {}))


def _limpar_expiradas(agora: float) -> dict:
    d = _dict()
    vivos = {
        pid: reg for pid, reg in d.items()
        if isinstance(reg, dict) and float(reg.get("expira_em", 0)) > agora
    }
    if len(vivos) != len(d):
        session[_SESSAO_CHAVE] = vivos
    return vivos


def marcar_aberto(paciente_id: int, senha: str) -> None:
    """Guarda a senha do paciente na sessão, válida por 40 minutos."""
    d = _dict()
    d[str(paciente_id)] = {
        "senha": senha,
        "expira_em": _agora() + TEMPO_MEMORIA_MIN * 60,
    }
    session[_SESSAO_CHAVE] = d
    session.permanent = False  # expira também ao fechar o navegador


def senha_valida_agora(paciente_id: int) -> str | None:
    """Senha ainda válida na janela (ou None = bloqueado).

    Um acesso dentro da janela renova o prazo (sliding) para +40 minutos.
    """
    agora = _agora()
    vivos = _limpar_expiradas(agora)
    reg = vivos.get(str(paciente_id))
    if reg is None:
        return None
    session[_SESSAO_CHAVE] = vivos
    session[_SESSAO_CHAVE][str(paciente_id)]["expira_em"] = agora + TEMPO_MEMORIA_MIN * 60
    return reg["senha"]


def minutos_restantes(paciente_id: int) -> int:
    """Minutos inteiros restantes de memória (0 se bloqueado/expirado)."""
    reg = _dict().get(str(paciente_id))
    if not isinstance(reg, dict):
        return 0
    restante = float(reg.get("expira_em", 0)) - _agora()
    return max(0, int(restante // 60))


def esta_aberto(paciente_id: int) -> bool:
    return senha_valida_agora(paciente_id) is not None


def bloquear(paciente_id: int) -> None:
    d = _dict()
    d.pop(str(paciente_id), None)
    session[_SESSAO_CHAVE] = d

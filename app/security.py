"""Segurança dos prontuários.

- Senha padrão do paciente = 4 primeiros dígitos do CPF + 4 últimos dígitos do CPF
  (ex.: CPF 123.456.789-00 -> senha "12347800"), sempre 8 caracteres.
- A senha nunca é armazenada: guardamos apenas salt + hash PBKDF2-SHA256 (200.000 iterações).
- O conteúdo do prontuário e os anexos são criptografados com chave Fernet
  derivada da senha do paciente. Sem a senha, não há recuperação.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

from cryptography.fernet import Fernet, InvalidToken

PBKDF2_ITERACOES = 200_000
SENHA_MIN_TAM = 8


# ------------------------------------------------------------------
# CPF
# ------------------------------------------------------------------

def apenas_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def validar_cpf(cpf: str) -> bool:
    """Valida CPF pelos dois dígitos verificadores. Aceita com ou sem máscara."""
    c = apenas_digitos(cpf)
    if len(c) != 11 or c == c[0] * 11:
        return False
    soma = sum(int(c[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10) % 11 % 10
    if d1 != int(c[9]):
        return False
    soma = sum(int(c[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10) % 11 % 10
    return d2 == int(c[10])


def formatar_cpf(cpf: str) -> str:
    """12345678900 -> 123.456.789-00"""
    c = apenas_digitos(cpf)
    if len(c) != 11:
        return cpf
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


def senha_padrao(cpf: str) -> str:
    """Senha padrão de 8 caracteres: 4 primeiros + 4 últimos dígitos do CPF."""
    c = apenas_digitos(cpf)
    if len(c) != 11:
        raise ValueError("CPF inválido para gerar a senha padrão.")
    return c[:4] + c[-4:]


# ------------------------------------------------------------------
# Senhas: hash PBKDF2 + verificação
# ------------------------------------------------------------------

def novo_salt() -> bytes:
    return secrets.token_bytes(16)


def hash_senha(senha: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, PBKDF2_ITERACOES)


def verificar_senha(senha: str, salt: bytes, hash_esperado: bytes) -> bool:
    return hmac.compare_digest(hash_senha(senha, salt), hash_esperado)


def senha_valida(senha: str) -> bool:
    """Regra para senha definida manualmente: mínimo de 8 caracteres."""
    return bool(senha) and len(senha) >= SENHA_MIN_TAM


# ------------------------------------------------------------------
# Criptografia ligada à senha do paciente (Fernet)
# ------------------------------------------------------------------

def chave_de_senha(senha: str, salt: bytes) -> bytes:
    """Deriva a chave Fernet (32 bytes -> base64) da senha + salt."""
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, PBKDF2_ITERACOES)
    return base64.urlsafe_b64encode(digest)


def cifrar(texto: str, senha: str, salt: bytes) -> str:
    """Criptografa texto; retorna token Fernet em texto (base64)."""
    return Fernet(chave_de_senha(senha, salt)).encrypt(texto.encode("utf-8")).decode("ascii")


def decifrar(token: str, senha: str, salt: bytes) -> str:
    """Descriptografa token; levanta InvalidToken se a senha estiver errada."""
    data = Fernet(chave_de_senha(senha, salt)).decrypt(token.encode("ascii"))
    return data.decode("utf-8")


def cifrar_bytes(dados: bytes, senha: str, salt: bytes) -> bytes:
    return Fernet(chave_de_senha(senha, salt)).encrypt(dados)


def decifrar_bytes(dados: bytes, senha: str, salt: bytes) -> bytes:
    return Fernet(chave_de_senha(senha, salt)).decrypt(dados)


__all__ = [
    "InvalidToken",
    "PBKDF2_ITERACOES",
    "SENHA_MIN_TAM",
    "apenas_digitos",
    "chave_de_senha",
    "cifrar",
    "cifrar_bytes",
    "decifrar",
    "decifrar_bytes",
    "formatar_cpf",
    "hash_senha",
    "novo_salt",
    "senha_padrao",
    "senha_valida",
    "validar_cpf",
    "verificar_senha",
]

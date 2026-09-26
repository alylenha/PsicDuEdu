"""Testes de segurança: CPF, senha padrão (4+4), hash e criptografia."""
import pytest

from app import security

CPF_VALIDO = "52998224725"       # 529.982.247-25 (CPF de teste válido)
SENHA_ESPERADA = "52994725"      # 5299 + 4725


def test_validar_cpf_valido():
    assert security.validar_cpf(CPF_VALIDO)
    assert security.validar_cpf("529.982.247-25")  # com máscara


@pytest.mark.parametrize("cpf", [
    "11111111111",   # repetido
    "52998224724",   # dígito verificador errado
    "1234567890",    # curto
    "",              # vazio
    "abcdefghijk",   # não numérico
])
def test_validar_cpf_invalido(cpf):
    assert not security.validar_cpf(cpf)


def test_senha_padrao_4_primeiros_mais_4_ultimos():
    assert security.senha_padrao(CPF_VALIDO) == SENHA_ESPERADA
    assert len(security.senha_padrao(CPF_VALIDO)) == 8
    # com máscara também funciona
    assert security.senha_padrao("529.982.247-25") == SENHA_ESPERADA


def test_senha_padrao_cpf_invalido_levanta_erro():
    with pytest.raises(ValueError):
        security.senha_padrao("123")


def test_hash_e_verificacao():
    salt = security.novo_salt()
    h = security.hash_senha(SENHA_ESPERADA, salt)
    assert h != SENHA_ESPERADA.encode()          # nunca guardar a senha
    assert security.verificar_senha(SENHA_ESPERADA, salt, h)
    assert not security.verificar_senha("00000000", salt, h)
    # salt diferente -> hash diferente (sem salt fixo no sistema)
    h2 = security.hash_senha(SENHA_ESPERADA, security.novo_salt())
    assert h != h2


def test_criptografia_fernet_ligada_a_senha():
    salt = security.novo_salt()
    segredo = "Paciente relata melhora do quadro ansioso."
    token = security.cifrar(segredo, SENHA_ESPERADA, salt)
    assert segredo not in token                       # conteúdo não aparece
    assert security.decifrar(token, SENHA_ESPERADA, salt) == segredo
    with pytest.raises(security.InvalidToken):
        security.decifrar(token, "senha-errada", salt)   # senha errada não abre
    with pytest.raises(security.InvalidToken):
        security.decifrar(token, SENHA_ESPERADA, security.novo_salt())  # salt errado


def test_criptografia_de_anexos_bytes():
    salt = security.novo_salt()
    dados = b"\x00\x01PDF-binario\x02"
    cifrado = security.cifrar_bytes(dados, SENHA_ESPERADA, salt)
    assert dados not in cifrado
    assert security.decifrar_bytes(cifrado, SENHA_ESPERADA, salt) == dados


def test_regra_senha_minimo_8():
    assert security.senha_valida("12345678")
    assert security.senha_valida("aB#9x_Wq!")
    assert not security.senha_valida("1234567")
    assert not security.senha_valida("")


def test_formatar_cpf():
    assert security.formatar_cpf(CPF_VALIDO) == "529.982.247-25"
    assert security.formatar_cpf("123") == "123"

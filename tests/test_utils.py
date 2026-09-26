"""Testes das utilidades: moeda pt-BR, datas, idade."""
import pytest

from app import utils


def test_parse_moeda_formato_ptbr():
    assert utils.parse_moeda("1.234,56") == 123456
    assert utils.parse_moeda("250,00") == 25000
    assert utils.parse_moeda("250") == 25000
    assert utils.parse_moeda("1234.56") == 123456        # aceita ponto decimal
    assert utils.parse_moeda("R$ 1.000,00") == 100000
    assert utils.parse_moeda(" 0,05 ") == 5


@pytest.mark.parametrize("valor", ["", "abc", "-10,00", "1,2,3"])
def test_parse_moeda_invalido(valor):
    with pytest.raises(ValueError):
        utils.parse_moeda(valor)


def test_formatar_moeda():
    assert utils.formatar_moeda(123456) == "R$ 1.234,56"
    assert utils.formatar_moeda(0) == "R$ 0,00"
    assert utils.formatar_moeda(5) == "R$ 0,05"
    assert utils.formatar_moeda(-500) == "-R$ 5,00"
    assert utils.formatar_moeda_simples(123456) == "1.234,56"


def test_parse_data():
    assert utils.parse_data("2026-09-25").isoformat() == "2026-09-25"
    assert utils.parse_data("25/09/2026").isoformat() == "2026-09-25"
    with pytest.raises(ValueError):
        utils.parse_data("25-13-2026")


def test_data_br_e_hora_br():
    assert utils.data_br("2026-09-25") == "25/09/2026"
    assert utils.data_br(None) == ""
    assert utils.hora_br("14:30:00") == "14:30"
    assert utils.hora_br("14:30") == "14:30"


def test_idade_e_aniversario():
    # alguém nascido há 30 anos
    from datetime import date, timedelta

    nasc = (date.today() - timedelta(days=30 * 365 + 7)).isoformat()
    assert utils.idade(nasc) in (29, 30)
    assert utils.mes_aniversario("1990-09-10") == 9
    assert utils.mes_aniversario(None) is None

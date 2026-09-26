"""Testes de integração do fluxo principal (banco em pasta temporária)."""
import re
import time
from datetime import date, timedelta

import pytest

from app import db, security, unlock

CPF = "52998224725"
SENHA = "52994725"  # 4 primeiros + 4 últimos do CPF


def _criar_paciente(cliente, nome="Maria Souza", cpf=CPF):
    return cliente.post("/pacientes/novo", data={
        "nome": nome, "cpf": cpf, "data_nascimento": "1990-05-14",
        "telefone": "(11) 98888-7777", "email": "maria@example.com",
        "endereco": "Rua das Flores, 123",
        "seg_nome": "João Souza (irmão)", "seg_telefone": "(11) 97777-6666",
        "observacoes": "",
    }, follow_redirects=True)


def _ultimo_paciente():
    return db.query("SELECT * FROM pacientes ORDER BY id DESC", one=True)


def test_paciente_criado_com_senha_padrao_do_cpf(cliente):
    resp = _criar_paciente(cliente)
    assert resp.status_code == 200
    p = _ultimo_paciente()
    assert p["cpf"] == CPF
    assert p["seg_nome"] == "João Souza (irmão)"          # contato de segurança salvo

    # mensagem exibe a senha padrão 4+4
    assert SENHA in resp.get_data(as_text=True)

    # hash do acesso corresponde à senha derivada do CPF
    a = db.query("SELECT * FROM acesso_prontuario WHERE paciente_id = ?", (p["id"],), one=True)
    assert a is not None
    assert security.verificar_senha(SENHA, bytes(a["salt"]), bytes(a["hash_senha"]))


def test_cpf_duplicado_rejeitado(cliente):
    _criar_paciente(cliente)
    resp = _criar_paciente(cliente, nome="Outra Pessoa")
    html = resp.get_data(as_text=True)
    assert "Já existe um paciente" in html
    assert db.query("SELECT COUNT(*) AS n FROM pacientes", one=True)["n"] == 1


def test_cpf_invalido_rejeitado(cliente):
    resp = _criar_paciente(cliente, cpf="12345678900")
    assert "CPF inválido" in resp.get_data(as_text=True)


def test_fluxo_prontuario_criptografado(cliente):
    _criar_paciente(cliente)
    p = _ultimo_paciente()

    # bloqueado: não mostra evoluções nem formulário
    resp = cliente.get(f"/prontuario/{p['id']}")
    html = resp.get_data(as_text=True)
    assert "Prontuário bloqueado" in html
    assert "nenhuma evolução" not in html.lower()

    # senha errada -> continua bloqueado
    resp = cliente.post(f"/prontuario/{p['id']}/desbloquear",
                        data={"senha": "00000000"}, follow_redirects=True)
    assert "Senha incorreta" in resp.get_data(as_text=True)

    # senha correta -> abre
    resp = cliente.post(f"/prontuario/{p['id']}/desbloquear",
                        data={"senha": SENHA}, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "desbloqueado" in html.lower()

    # grava evolução e confere cifra no banco
    resp = cliente.post(f"/prontuario/{p['id']}/nova_evolucao",
                        data={"data_sessao": date.today().isoformat(),
                              "tipo": "Evolução",
                              "conteudo": "Segredo clínico confidencial."}, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Segredo clínico confidencial." in html
    row = db.query("SELECT * FROM prontuarios WHERE paciente_id = ?", (p["id"],), one=True)
    assert "Segredo clínico confidencial." not in row["conteudo_criptografado"]  # cifrado no banco

    # bloquear de novo esconde o conteúdo
    cliente.post(f"/prontuario/{p['id']}/bloquear")
    resp = cliente.get(f"/prontuario/{p['id']}")
    assert "Segredo clínico confidencial." not in resp.get_data(as_text=True)


def test_prontuario_exige_senha_apos_40_minutos(cliente):
    """Regressão do erro relatado: expirada a janela de 40 min, o prontuário
    volta a bloquear e a senha é solicitada de novo na próxima abertura."""
    _criar_paciente(cliente)
    p = _ultimo_paciente()

    resp = cliente.post(f"/prontuario/{p['id']}/desbloquear",
                        data={"senha": SENHA}, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Prontuário aberto" in html
    assert "40 min" in html                      # banner: janela completa

    fake = {"agora": time.time()}
    unlock.definir_fonte_tempo(lambda: fake["agora"])
    try:
        fake["agora"] += 41 * 60                 # 41 min sem nenhum acesso
        resp = cliente.get(f"/prontuario/{p['id']}")
        html = resp.get_data(as_text=True)
        assert "Prontuário bloqueado" in html
        assert "Prontuário aberto" not in html
    finally:
        unlock.definir_fonte_tempo(None)


def test_janela_deslizante_renova_aos_acessos(cliente):
    """Dentro da janela o prontuário abre sem redigitar; cada acesso renova
    o prazo para +40 min; 40 min sem acesso volta a pedir a senha."""
    _criar_paciente(cliente)
    p = _ultimo_paciente()
    cliente.post(f"/prontuario/{p['id']}/desbloquear",
                 data={"senha": SENHA}, follow_redirects=True)
    cliente.post(f"/prontuario/{p['id']}/nova_evolucao",
                 data={"data_sessao": date.today().isoformat(), "tipo": "Evolução",
                       "conteudo": "Texto dentro da janela."})

    fake = {"agora": time.time()}
    unlock.definir_fonte_tempo(lambda: fake["agora"])
    try:
        fake["agora"] += 35 * 60
        html = cliente.get(f"/prontuario/{p['id']}").get_data(as_text=True)
        assert "Texto dentro da janela." in html          # ainda dentro da janela

        fake["agora"] += 15 * 60                          # 50 min após o desbloqueio
        html = cliente.get(f"/prontuario/{p['id']}").get_data(as_text=True)
        assert "Texto dentro da janela." in html          # aberto: houve renovação

        fake["agora"] += 45 * 60                          # 40 min sem nenhum acesso
        html = cliente.get(f"/prontuario/{p['id']}").get_data(as_text=True)
        assert "Texto dentro da janela." not in html
        assert "Prontuário bloqueado" in html
    finally:
        unlock.definir_fonte_tempo(None)


def test_troca_senha_recriptografa(cliente):
    _criar_paciente(cliente)
    p = _ultimo_paciente()
    cliente.post(f"/prontuario/{p['id']}/desbloquear", data={"senha": SENHA})
    cliente.post(f"/prontuario/{p['id']}/nova_evolucao",
                 data={"data_sessao": date.today().isoformat(), "tipo": "Evolução",
                       "conteudo": "Texto antes da troca."})

    nova = "novaSenha8"
    resp = cliente.post(f"/prontuario/{p['id']}/trocar_senha",
                        data={"senha_atual": SENHA, "nova_senha": nova},
                        follow_redirects=True)
    assert "re-criptografado" in resp.get_data(as_text=True)

    a = db.query("SELECT * FROM acesso_prontuario WHERE paciente_id = ?", (p["id"],), one=True)
    assert security.verificar_senha(nova, bytes(a["salt"]), bytes(a["hash_senha"]))
    row = db.query("SELECT * FROM prontuarios WHERE paciente_id = ?", (p["id"],), one=True)
    texto = security.decifrar(row["conteudo_criptografado"], nova, bytes(a["salt"]))
    assert texto == "Texto antes da troca."
    with pytest.raises(security.InvalidToken):
        security.decifrar(row["conteudo_criptografado"], SENHA, bytes(a["salt"]))


def test_agenda_e_pagamento_gera_receita(cliente):
    _criar_paciente(cliente)
    p = _ultimo_paciente()
    amanha = (date.today() + timedelta(days=1)).isoformat()

    resp = cliente.post("/agenda/novo", data={
        "paciente_id": p["id"], "data": amanha, "hora_inicio": "09:00",
        "hora_fim": "10:00", "tipo": "Sessão", "profissional": "Dra. Ana",
        "status": "agendado", "valor": "250,00", "observacoes": "",
    }, follow_redirects=True)
    assert resp.status_code == 200

    ag = db.query("SELECT * FROM agendamentos", one=True)
    assert ag["valor_centavos"] == 25000

    # registra pagamento -> cria receita vinculada
    cliente.post(f"/agenda/{ag['id']}/receber", data={"forma_pagamento": "PIX"})
    ag = db.query("SELECT * FROM agendamentos WHERE id = ?", (ag["id"],), one=True)
    assert ag["pago"] == 1
    lanc = db.query("SELECT * FROM lancamentos WHERE agendamento_id = ?", (ag["id"],), one=True)
    assert lanc["tipo"] == "receita" and lanc["valor_centavos"] == 25000


def test_agenda_filtros_paciente_tipo_e_periodo(cliente):
    _criar_paciente(cliente, nome="Ana Manha")
    pa = _ultimo_paciente()
    _criar_paciente(cliente, nome="Bruno Noite", cpf="11144477735")
    pb = _ultimo_paciente()
    hoje = date.today()
    segunda = hoje - timedelta(days=hoje.weekday())

    def _agendar(pid, hora, tipo, profissional):
        cliente.post("/agenda/novo", data={
            "paciente_id": pid, "data": segunda.isoformat(),
            "hora_inicio": hora, "hora_fim": f"{int(hora[:2]) + 1:02d}:00",
            "tipo": tipo, "profissional": profissional,
            "status": "agendado", "valor": "", "observacoes": "",
        }, follow_redirects=True)

    _agendar(pa["id"], "09:00", "Sessão", "Dra. Ana")
    _agendar(pb["id"], "14:00", "Avaliação", "Dr. Bento")
    _agendar(pa["id"], "19:00", "Sessão", "Dra. Ana")

    # sem filtros: 3 cards; botão "Limpar filtros" ausente
    html = cliente.get("/agenda/").get_data(as_text=True)
    assert html.count("compromisso status-borda-") == 3
    assert "Limpar filtros" not in html

    # filtro por paciente (2 de Ana) e navegação preserva o filtro
    html = cliente.get("/agenda/", query_string={"paciente": pa["id"]}).get_data(as_text=True)
    assert html.count("compromisso status-borda-") == 2
    assert f"paciente={pa['id']}" in html
    assert "Limpar filtros" in html

    # filtro por tipo de sessão
    html = cliente.get("/agenda/", query_string={"tipo": "Avaliação"}).get_data(as_text=True)
    assert html.count("compromisso status-borda-") == 1

    # filtro por período do dia
    html = cliente.get("/agenda/", query_string={"periodo": "manha"}).get_data(as_text=True)
    assert html.count("compromisso status-borda-") == 1
    html = cliente.get("/agenda/", query_string={"periodo": "tarde"}).get_data(as_text=True)
    assert html.count("compromisso status-borda-") == 1
    html = cliente.get("/agenda/", query_string={"periodo": "noite"}).get_data(as_text=True)
    assert html.count("compromisso status-borda-") == 1

    # combinado: profissional + período
    html = cliente.get("/agenda/", query_string={
        "profissional": "Dra. Ana", "periodo": "noite"}).get_data(as_text=True)
    assert html.count("compromisso status-borda-") == 1


def test_financeiro_despesa_e_exclusao(cliente):
    resp = cliente.post("/financeiro/novo", data={
        "tipo": "despesa", "data": date.today().isoformat(), "valor": "1.500,00",
        "categoria": "Aluguel", "descricao": "Aluguel de setembro",
        "forma_pagamento": "PIX",
    }, follow_redirects=True)
    assert "Lançamento registrado." in resp.get_data(as_text=True)
    lanc = db.query("SELECT * FROM lancamentos", one=True)
    assert lanc["valor_centavos"] == 150000

    cliente.post(f"/financeiro/{lanc['id']}/excluir")
    assert db.query("SELECT COUNT(*) AS n FROM lancamentos", one=True)["n"] == 0


def test_backup_roundtrip(cliente, tmp_path):
    _criar_paciente(cliente)
    from app.services import backup_service

    caminho = backup_service.criar_backup()
    assert caminho.exists() and caminho.suffix == ".bak"

    # "apaga" tudo recriando o banco vazio e restaura
    from app import db as modulo_db

    modulo_db.init_db()
    backup_service.restaurar_backup(caminho)

    # valida diretamente no arquivo restaurado
    import sqlite3

    from app.paths import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    n = conn.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0]
    conn.close()
    assert n == 1


def test_exportar_ics(cliente):
    _criar_paciente(cliente)
    p = _ultimo_paciente()
    amanha = (date.today() + timedelta(days=1)).isoformat()
    cliente.post("/agenda/novo", data={
        "paciente_id": p["id"], "data": amanha, "hora_inicio": "14:00",
        "hora_fim": "15:00", "tipo": "Sessão", "profissional": "",
        "status": "agendado", "valor": "200,00", "observacoes": "",
    })
    resp = cliente.get("/agenda/exportar.ics")
    corpo = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "BEGIN:VCALENDAR" in corpo and "BEGIN:VEVENT" in corpo
    assert "DTSTART:" in corpo
    assert re.search(r"DTSTART:\d{8}T140000", corpo)


def test_paginas_principais_respondem(cliente):
    for url in ["/", "/pacientes", "/pacientes/novo", "/agenda/",
                "/financeiro/", "/relatorios/", "/integracoes/", "/backup/"]:
        resp = cliente.get(url)
        assert resp.status_code == 200, url

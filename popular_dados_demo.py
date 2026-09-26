"""Popula o banco de DESENVOLVIMENTO com pacientes e sessões de exemplo.

- 12 pacientes ativos (CPF válidos, senha padrão 4+4 do CPF no acesso do prontuário);
- Sessões recorrentes em setembro e outubro de 2026, dias e horários variados;
- Valores entre R$ 90,00 e R$ 120,00;
- Histórico realista: datas passadas = realizado/faltou; futuras = agendado;
  ~30% das realizadas pagas, gerando receita vinculada no financeiro.

Uso:  python popular_dados_demo.py   (idempotente: CPFs já cadastrados são pulados)
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from app import criar_app, db, security
from app.utils import FORMAS_PAGAMENTO, data_br

random.seed(42)

HOJE = date(2026, 9, 26)
# Segundas-feiras das semanas de setembro e outubro/2026
SEMANAS = [date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21), date(2026, 9, 28),
           date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19), date(2026, 10, 26)]

# (nome, 9 primeiros dígitos do CPF, nascimento, telefone)
PESSOAS = [
    ("Ana Beatriz Rocha Lima",   "111222334", "1985-03-12", "(11) 98812-4455"),
    ("Bruno Carvalho Nogueira",  "222333445", "1990-07-25", "(11) 97745-2211"),
    ("Carla Dias Ferreira",      "333444556", "1978-11-03", "(11) 96633-8899"),
    ("Diego Martins Almeida",    "444555667", "1995-01-19", "(11) 95521-7744"),
    ("Elisa Prado Monteiro",     "555666778", "1982-05-30", "(11) 94410-6633"),
    ("Felipe Souza Andrade",     "666777889", "1998-09-08", "(11) 93308-5522"),
    ("Gabriela Lima Pinto",      "777888990", "1975-12-14", "(11) 92297-4411"),
    ("Henrique Alves Barbosa",   "888999101", "1992-02-27", "(11) 91185-3300"),
    ("Isabela Nunes Cardoso",    "999000212", "1988-06-16", "(11) 91074-2288"),
    ("João Pedro Teixeira",      "123456789", "2000-04-05", "(11) 90963-1177"),
    ("Larissa Mendes Cavalcanti","234567891", "1980-08-21", "(11) 99852-0066"),
    ("Marcos Vinícius Duarte",   "345678912", "1993-10-11", "(11) 98741-9955"),
]

SEGUNDOS_CONTATO = ["Camila Rocha", "Otávio Nogueira", "Renata Dias", "Paulo Martins",
                    "Sofia Prado", "Juliana Souza", "Marcos Lima", "Beatriz Alves",
                    "Tiago Nunes", "Fernanda Teixeira", "Rafael Mendes", "Cláudia Duarte"]

HORARIOS = ["08:00", "09:00", "10:00", "11:00",   # manhã
            "13:00", "14:00", "15:00", "16:00",   # tarde
            "18:30", "19:00", "19:30", "20:00"]   # noite
TIPOS = ["Sessão", "Primeira consulta", "Retorno", "Avaliação", "Orientação"]
PROFISSIONAIS = ["Dra. Helena Costa", "Dr. Rafael Menezes", "Dra. Paula Andrade"]


def cpf_com_dv(nove: str) -> str:
    """Completa os 9 dígitos com os dois dígitos verificadores."""
    soma = sum(int(nove[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10) % 11 % 10
    dez = nove + str(d1)
    soma = sum(int(dez[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10) % 11 % 10
    return dez + str(d2)


def main() -> None:
    app = criar_app()
    with app.app_context():
        _popular()


def _popular() -> None:
    criados = pulados = 0
    total_sessoes = realizadas = faltas = futuras = pagas = 0
    total_receita = 0

    for i, (nome, nove, nasc, tel) in enumerate(PESSOAS):
        cpf = cpf_com_dv(nove)
        assert security.validar_cpf(cpf), f"CPF gerado inválido: {cpf}"
        row = db.query("SELECT id FROM pacientes WHERE cpf = ?", (cpf,), one=True)
        if row:
            pid = row["id"]
            print(f"* Paciente ja existe (completando sessoes): {nome}")
            pulados += 1
        else:
            pid = db.execute(
                "INSERT INTO pacientes (nome, cpf, data_nascimento, telefone, email, endereco, "
                "seg_nome, seg_telefone, observacoes, ativo) VALUES (?,?,?,?,?,?,?,?,?,1)",
                (nome, cpf, nasc, tel,
                 nome.split()[0].lower() + "@example.com",
                 f"Rua das Acacias, {100 + i * 7} - Sao Paulo/SP",
                 SEGUNDOS_CONTATO[i], f"(11) 9{8000 + i * 13:04d}-0000",
                 ""),
            )
            salt = security.novo_salt()
            db.execute(
                "INSERT INTO acesso_prontuario (paciente_id, salt, hash_senha) VALUES (?,?,?)",
                (pid, salt, security.hash_senha(security.senha_padrao(cpf), salt)),
            )
            criados += 1

        # ---- Sessões recorrentes: dia fixo da semana + horário fixo ----
        dia_semana = i % 6                      # Seg..Sáb (0..5)
        hora = HORARIOS[i]
        hora_fim = f"{int(hora[:2]) + 1:02d}:{hora[3:]}"
        tipo = TIPOS[i % len(TIPOS)]
        profissional = PROFISSIONAIS[i % len(PROFISSIONAIS)]
        semanas_do_paciente = [w for k, w in enumerate(SEMANAS) if (k + i) % 2 == 0]

        for semana in semanas_do_paciente:
            data_sessao = semana + timedelta(days=dia_semana)
            if not (date(2026, 9, 1) <= data_sessao <= date(2026, 10, 31)):
                continue
            # idempotência: não duplica sessão do mesmo paciente no mesmo dia
            if db.query("SELECT id FROM agendamentos WHERE paciente_id = ? AND data = ?",
                        (pid, data_sessao.isoformat()), one=True):
                continue
            valor = random.randint(90, 120) * 100  # R$ 90 a R$ 120
            if data_sessao >= HOJE:
                status = "agendado"
                futuras += 1
            else:
                status = "faltou" if random.random() < 0.15 else "realizado"
                faltas += status == "faltou"
                realizadas += status == "realizado"

            aid = db.execute(
                "INSERT INTO agendamentos (paciente_id, data, hora_inicio, hora_fim, tipo, "
                "profissional, status, valor_centavos, pago, observacoes) "
                "VALUES (?,?,?,?,?,?,?,?,0,'')",
                (pid, data_sessao.isoformat(), hora, hora_fim, tipo,
                 profissional, status, valor),
            )
            total_sessoes += 1

            # ~30% das realizadas passadas já estão pagas -> receita no financeiro
            if status == "realizado" and random.random() < 0.30:
                forma = random.choice(FORMAS_PAGAMENTO)
                lid = db.execute(
                    "INSERT INTO lancamentos (data, tipo, categoria, descricao, "
                    "valor_centavos, forma_pagamento, agendamento_id) "
                    "VALUES (?, 'receita', 'Sessão', ?, ?, ?, ?)",
                    (data_sessao.isoformat(), f"Sessão — {nome} ({data_br(data_sessao.isoformat())})",
                     valor, forma, aid),
                )
                db.execute(
                    "UPDATE agendamentos SET pago = 1, lancamento_id = ? WHERE id = ?",
                    (lid, aid),
                )
                pagas += 1
                total_receita += valor

    print("\n===== Populacao concluida =====")
    print(f"Pacientes criados agora: {criados} (ja existiam: {pulados})")
    print(f"Sessoes inseridas agora: {total_sessoes} "
          f"(realizadas: {realizadas} | faltas: {faltas} | futuras: {futuras})")
    print(f"Sessoes pagas agora: {pagas} - receita gerada: R$ {total_receita / 100:.2f}")
    print("Senha padrao do prontuario: 4 primeiros + 4 ultimos digitos do CPF.")


if __name__ == "__main__":
    main()

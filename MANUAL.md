# PsicoClin ERP — Manual Rápido

## 1. Instalação

### Windows
1. Instale o **Python 3.10+** (python.org) — marque **“Add Python to PATH”**.
2. Dê dois cliques em `instalar_windows.bat`.
3. Dê dois cliques em `iniciar_windows.bat`.
4. Abra **http://127.0.0.1:5050** no navegador.

### macOS
1. Instale o **Python 3.10+** (python.org ou `brew install python`).
2. Dê dois cliques em `instalar_macos.command`.
3. Dê dois cliques em `iniciar_macos.command`.
4. Abra **http://127.0.0.1:5050** no navegador.

### Manual (alternativo)
```
pip install -r requirements.txt
python run.py
```

Para encerrar o servidor, feche a janela do terminal (ou `Ctrl+C`).

---

## 2. Uso diário

### Dashboard (/)
- **KPIs**: pacientes ativos, atendimentos hoje/período, ticket médio, receitas, despesas, resultado.
- **Filtros**: competência (mês) ou intervalo de dias (**De**/**Até**) no topo.
- **Gráficos**: receitas × despesas (últimos 6 meses), atendimentos/mês, status da agenda, risco clínico (ativos).
- **Agenda**: dia (padrão) ou período (quando filtrado) + aniversariantes do mês.

### Pacientes (/pacientes)
- **Cadastro**: nome, CPF (validado), nascimento, telefone, e-mail, endereço, **contato de segurança** e **risco clínico**.
- **Senha do prontuário**: 4 primeiros + 4 últimos dígitos do CPF. Ex.: `1234.567.890-00` → `12348900`.
- **Busca**: por nome ou CPF. Edição, ativar/desativar.
- **Risco clínico**: categorias configuráveis em *Integrações → Risco clínico* (criar, editar, excluir).

### Agenda (/agenda)
- **Visão semanal**: navegue com **← Semana anterior | Hoje | Próxima semana →**.
- **Nova sessão**: paciente, data, horário, tipo, profissional, valor.
- **Status**: `agendado → confirmado → realizado` / `faltou` / `cancelado`.
- **Pagamento 1-clique**: botão **Receber** cria a receita no financeiro e marca como pago.
- **Exportar .ics**: botão no topo (importa no Google/Apple/Outlook).

### Prontuário (/prontuario)
- Acesso com a **senha do paciente** (padrão: derivada do CPF).
- Evoluções e anamneses **criptografadas** (Fernet).
- **Anexos** criptografados por paciente.
- Senha válida por **40 minutos** (renovada a cada acesso).
- **Troca de senha** disponível (mínimo 8 caracteres).
- ⚠️ **Não existe recuperação de senha** — anote em local seguro.

### Financeiro (/financeiro)
- **Lançamentos**: receitas e despesas com categoria, forma de pagamento e descrição.
- **Valores em pt-BR**: `1.234,56` (vírgula para decimal).
- **Filtros**: período, tipo, categoria.
- **Paginação**: 20 / 50 / 100 / tudo.
- **Edição**: botão **Editar** em cada linha.
- **Popup de conciliação**: ao lançar com mesma data+valor+tipo de uma previsão, oferece vincular e efetivar.

### Previsões (/financeiro/previsoes)
- **A receber**: gerada automaticamente da agenda + lançamento manual.
- **A pagar**: lançamento manual.
- **Efetivar**: cria o lançamento idêntico (exige **forma de pagamento**).
- **Filtros**: período, tipo, status (previstas/efetivadas/canceladas), origem (agenda/manual).

---

## 3. Relatórios (/relatórios)

Período padrão: mês atual. Ajuste em **De/Até** no topo — vale para todos os relatórios.

| Relatório | O que mostra |
|---|---|
| **Faturamento** | Todas as receitas e despesas do período, com totais. |
| **DRE** | Receitas × despesas por categoria, com resultado do período. |
| **Atendimentos por paciente** | Sessões realizadas, faltas, valores pagos e a receber. |
| **Sessões não pagas** | Realizadas/faltas com valor pendente — base para cobrança. |
| **Ficha do paciente** | Dados cadastrais, contato de segurança e histórico de sessões. |
| **Agenda do dia** | Lista horária das sessões de um dia — imprima e leve para a recepção. |

**Imprimir em PDF**: botão **🖨️ Imprimir / PDF** no topo (ou `Ctrl+P` → “Salvar como PDF”).

---

## 4. Backup

- **Pela tela**: menu *Backup* → “Criar backup (.bak)” e lista para download.
- **Pelo terminal** (na pasta do projeto):
  ```
  python backup.py                        → cria backups/psiclin_AAAA-MM-DD_HHMM.bak
  python backup.py --destino E:\cof.bak  → salva direto no pendrive
  python backup.py --listar              → lista os backups
  python backup.py --restaurar ARQUIVO   → restaura (sobrescreve os dados atuais)
  ```
- **Automático**: 1× ao dia no primeiro start do dia.
- Guarde cópias em pendrive ou nuvem pessoal — o `.bak` é auto-suficiente.

---

## 5. Integrações (opcionais, gratuitas)

Sem configurar nada, o sistema funciona 100% offline.

- **E-mail (SMTP)**: na tela *Integrações*, informe servidor SMTP e senha de app (Gmail: `conta → segurança → senhas de app`). O sistema envia avisos de sessão **marcada, cancelada e falta** para o paciente e/ou a clínica, com botão de envio de teste.
- **Google Agenda**:
  - *Sem configuração*: botão **Exportar .ics** na agenda (importa no Google, Apple Agenda ou Outlook).
  - *Sincronização completa (opcional)*: credenciais OAuth gratuitas do Google Cloud Console (assistente passo a passo na tela *Integrações*).

---

## 6. Dicas

- Valores sempre em **pt-BR** (vírgula para decimal).
- O sistema roda só no seu computador — **sem nuvem, sem custo**.
- O servidor escuta apenas em `127.0.0.1` (não acessível pela rede).
- **Não existe recuperação de senha de prontuário** — é isso que garante a privacidade.
- Dados locais (banco, anexos e backups) ficam em `data/` e `backups/` — **não suba esses arquivos para repositórios públicos** (o `.gitignore` já os exclui).

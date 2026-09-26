# 🧠 PsicoClin ERP

ERP gratuito e 100% local para clínicas de psicologia: **pacientes, agenda,
prontuários criptografados, financeiro, relatórios e dashboard** — com
integrações **opcionais** de e-mail e Google Agenda.

Roda em **Windows e macOS com a mesma estrutura**, sem nuvem e sem custo:
os dados ficam somente no computador da clínica.

> **📖 [Manual rápido](MANUAL.md)** — instalação, uso diário, relatórios e backup em 2 minutos.

---

## ✅ Requisitos

- **Python 3.10 ou superior** (gratuito — [python.org/downloads](https://www.python.org/downloads/))
  - Windows: marque **“Add Python to PATH”** durante a instalação.
  - macOS: instale pelo site ou `brew install python`.
- Navegador (Chrome, Edge, Safari ou Firefox) — já presente no sistema.

## 🚀 Instalação (1–2 cliques)

| Sistema | Instalar | Usar no dia a dia |
|---|---|---|
| **Windows** | duplo clique em `instalar_windows.bat` | duplo clique em `iniciar_windows.bat` |
| **macOS** | duplo clique em `instalar_macos.command` | duplo clique em `iniciar_macos.command` |

O navegador abrirá sozinho em **http://127.0.0.1:5050**.
Para encerrar, feche a janela do servidor (ou `Ctrl+C`).

> Instalando manualmente? `pip install -r requirements.txt` e `python run.py`.

## 📦 O que o sistema faz

- **Dashboard** — pacientes ativos, atendimentos hoje/mês, receitas × despesas,
  resultado e ticket médio + gráficos dos últimos 6 meses, agenda do dia e
  aniversariantes.
- **Pacientes** — cadastro completo com **CPF validado** e
  **contato de segurança (pessoa + telefone)**, busca, edição, ativar/desativar.
- **Agenda** — visão semanal, marcação de sessões com valor, status
  (agendado/confirmado/realizado/faltou/cancelado), **registro de pagamento
  com 1 clique** (gera a receita no financeiro), exportação `.ics`.
- **Prontuário 🔒** — evoluções e anamneses **criptografadas** com senha
  exclusiva de cada paciente + anexos criptografados. A senha é pedida a cada
  nova abertura e permanece válida por 40 minutos (renovados a cada acesso).
- **Financeiro** — receitas e despesas com categorias, forma de pagamento e
  filtros por período (aceita valores pt-BR: `1.234,56`).
- **Relatórios** (imprima em PDF pelo navegador): faturamento, DRE
  simplificada, atendimentos por paciente, sessões não pagas, ficha do
  paciente e agenda do dia.
- **Backup** — arquivo `.bak` com **todos os dados** (banco + anexos +
  configurações): botão na tela, comando no terminal e **automático 1× ao dia**.

## 🔐 Segurança dos prontuários (camada extra)

- **Senha exclusiva por paciente, com 8 caracteres.**
  - **Padrão = 4 primeiros dígitos do CPF + 4 últimos dígitos do CPF.**
    Ex.: CPF `123.456.789-00` → senha `12347800`.
  - Pode ser trocada por uma senha personalizada (mínimo 8 caracteres) na tela
    do prontuário — todo o conteúdo é re-criptografado na troca.
- A senha **nunca é armazenada**: guarda-se apenas hash **PBKDF2-SHA256**
  (200.000 iterações + salt aleatório).
- O conteúdo (evoluções e anexos) é cifrado com **Fernet** usando chave
  derivada da senha — abrir o arquivo do banco não revela nada sem a senha.
- A senha é solicitada em **cada nova abertura** do prontuário e, após
  desbloquear, fica válida por **40 minutos** na sessão do navegador —
  janela renovada a cada acesso (fechar o navegador, reiniciar o servidor
  ou clicar em “Bloquear agora” trava na hora).
- ⚠️ **Não existe recuperação de senha** — é isso que garante a privacidade.
  Anote as senhas dos pacientes em local seguro (cofre).
- O servidor responde apenas em `127.0.0.1` (nada é acessível pela rede).

## 🔗 Integrações opcionais (gratuitas, desligadas por padrão)

Sem configurar nada, o sistema funciona 100% offline.

- **Avisos por e-mail (SMTP)** — na tela *Integrações*, informe servidor SMTP
  e uma **senha de app** (Gmail: `conta → segurança → senhas de app`). O
  sistema envia avisos de sessão **marcada, cancelada e falta** para o
  paciente e/ou a clínica, com botão de envio de teste.
- **Google Agenda**:
  - *Sem configuração*: botão **Exportar .ics** na agenda (importa no Google,
    Apple Agenda ou Outlook) e download dos próximos 60 dias.
  - *Sincronização completa (opcional)*: credenciais OAuth gratuitas do Google
    Cloud Console (assistente passo a passo na tela *Integrações*). As sessões
    são espelhadas na agenda escolhida.

## 🗄️ Backup e restauração

- **Pela tela:** menu *Backup* → “Criar backup (.bak)” e lista para download.
- **Pelo terminal (na pasta do projeto):**
  ```
  python backup.py                     → cria backups/psiclin_AAAA-MM-DD_HHMM.bak
  python backup.py --destino E:\cof.bak → salva direto no pendrive
  python backup.py --listar            → lista os backups
  python backup.py --restaurar ARQUIVO → restaura (sobrescreve os dados atuais)
  ```
- **Automático:** no primeiro start do dia, um `.bak` é gerado sozinho.
- Guarde cópias em pendrive ou nuvem pessoal — o `.bak` é auto-suficiente.

## 📁 Estrutura de pastas

```
psiclin-erp/
├── instalar_windows.bat / instalar_macos.command   # instalação
├── iniciar_windows.bat  / iniciar_macos.command    # uso diário
├── run.py          # inicia o sistema
├── backup.py       # backup/restauração pelo terminal
├── requirements.txt
├── app/            # código (Flask), telas e design system
├── data/
│   ├── psiclin.db  # banco SQL (SQLite)
│   └── anexos/<id>/# anexos criptografados por paciente
└── backups/        # arquivos .bak gerados
```

## 🧪 Testes

```
python -m pytest tests/ -v
```

## 🎨 Design e créditos

Interface guiada pelos princípios do **Apple Human Interface Guidelines**
(tipografia hierárquica, clareza, foco visível), aplicados à web com a paleta
de **neutros quentes** (off-white, areia, bege). Referência documental:
catálogo **[mjmirza/apple-design-system](https://github.com/mjmirza/apple-design-system)**
(CC BY 4.0) — não distribuímos assets da Apple; veja `NOTICE`.

## 📄 Licença

Código sob licença **MIT** (`LICENSE`). Documentação sob **CC BY 4.0**.
Marcas e diretrizes da Apple pertencem à Apple Inc. — veja `NOTICE`.

---

*PsicoClin ERP — feito para clínicas pequenas cuidarem de pessoas, não de planilhas.* 🌱

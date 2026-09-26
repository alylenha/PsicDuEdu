-- ============================================================
-- PsicoClin ERP — estrutura do banco (SQLite)
-- Estrutura simples e legível, criada automaticamente na 1ª execução.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Pacientes
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pacientes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                    TEXT    NOT NULL,
    cpf                     TEXT    NOT NULL UNIQUE,          -- apenas dígitos, 11 posições
    data_nascimento         TEXT,                             -- AAAA-MM-DD
    telefone                TEXT,
    email                   TEXT,
    endereco                TEXT,
    -- contato de segurança (pessoa + telefone)
    seg_nome                TEXT,
    seg_telefone            TEXT,
    observacoes             TEXT,
    ativo                   INTEGER NOT NULL DEFAULT 1,       -- 1 = ativo, 0 = inativo
    risco_id                INTEGER REFERENCES categorias_risco(id) ON DELETE SET NULL,
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- Classificação de risco clínico (categorias livres, definidas pelo usuário)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias_risco (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                    TEXT    NOT NULL UNIQUE,
    cor                     TEXT    NOT NULL DEFAULT '#8A8177',
    ativa                   INTEGER NOT NULL DEFAULT 1,
    ordem                   INTEGER NOT NULL DEFAULT 0,
    criada_em               TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- Acesso ao prontuário: senha exclusiva por paciente
-- Guarda apenas salt + hash (PBKDF2-SHA256). A senha nunca é armazenada.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS acesso_prontuario (
    paciente_id             INTEGER PRIMARY KEY REFERENCES pacientes(id) ON DELETE CASCADE,
    salt                    BLOB    NOT NULL,
    hash_senha              BLOB    NOT NULL,
    atualizada_em           TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- Prontuário: evoluções / anamneses (CONTEÚDO CRIPTOGRAFADO)
-- criptograma = Fernet com chave derivada da senha do paciente (PBKDF2)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prontuarios (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id             INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    data_sessao             TEXT    NOT NULL,                 -- AAAA-MM-DD
    tipo                    TEXT    NOT NULL DEFAULT 'Evolução',
    conteudo_criptografado  TEXT    NOT NULL,                 -- token Fernet (base64)
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_pront_paciente ON prontuarios(paciente_id, data_sessao);

-- ------------------------------------------------------------
-- Agenda de atendimentos
-- status: agendado | confirmado | realizado | faltou | cancelado
-- pago: 0 = não, 1 = sim (receita lançada no financeiro)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agendamentos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id             INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    data                    TEXT    NOT NULL,                 -- AAAA-MM-DD
    hora_inicio             TEXT    NOT NULL,                 -- HH:MM
    hora_fim                TEXT    NOT NULL,                 -- HH:MM
    tipo                    TEXT    NOT NULL DEFAULT 'Sessão',
    profissional            TEXT    NOT NULL DEFAULT '',
    status                  TEXT    NOT NULL DEFAULT 'agendado',
    valor_centavos          INTEGER NOT NULL DEFAULT 0,
    pago                    INTEGER NOT NULL DEFAULT 0,
    lancamento_id           INTEGER REFERENCES lancamentos(id) ON DELETE SET NULL,
    email_enviado           INTEGER NOT NULL DEFAULT 0,
    google_event_id         TEXT,
    observacoes             TEXT    NOT NULL DEFAULT '',
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_agenda_data ON agendamentos(data);

-- ------------------------------------------------------------
-- Financeiro: receitas e despesas (valores guardados em centavos)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lancamentos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    data                    TEXT    NOT NULL,                 -- AAAA-MM-DD
    tipo                    TEXT    NOT NULL CHECK (tipo IN ('receita', 'despesa')),
    categoria               TEXT    NOT NULL,
    descricao               TEXT    NOT NULL DEFAULT '',
    valor_centavos          INTEGER NOT NULL,
    forma_pagamento         TEXT    NOT NULL DEFAULT '',
    agendamento_id          INTEGER REFERENCES agendamentos(id) ON DELETE SET NULL,
    previsao_id             INTEGER REFERENCES previsoes(id) ON DELETE SET NULL,
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_lanc_data ON lancamentos(data);

-- ------------------------------------------------------------
-- Financeiro: previsões de contas a pagar / a receber
-- status: prevista | efetivada | cancelada
-- origem: manual | agendamento (receita gerada da agenda)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS previsoes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    data_prevista           TEXT    NOT NULL,                 -- AAAA-MM-DD
    tipo                    TEXT    NOT NULL CHECK (tipo IN ('receita', 'despesa')),
    categoria               TEXT    NOT NULL,
    descricao               TEXT    NOT NULL DEFAULT '',
    valor_centavos          INTEGER NOT NULL,
    status                  TEXT    NOT NULL DEFAULT 'prevista'
                            CHECK (status IN ('prevista', 'efetivada', 'cancelada')),
    origem                  TEXT    NOT NULL DEFAULT 'manual'
                            CHECK (origem IN ('manual', 'agendamento')),
    agendamento_id          INTEGER REFERENCES agendamentos(id) ON DELETE SET NULL,
    paciente_id             INTEGER REFERENCES pacientes(id) ON DELETE SET NULL,
    lancamento_id           INTEGER REFERENCES lancamentos(id) ON DELETE SET NULL,
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    efetivado_em            TEXT
);

CREATE INDEX IF NOT EXISTS idx_prev_data ON previsoes(data_prevista);
CREATE INDEX IF NOT EXISTS idx_prev_status ON previsoes(status);
CREATE INDEX IF NOT EXISTS idx_prev_ag ON previsoes(agendamento_id);

-- ------------------------------------------------------------
-- Anexos: metadados — o arquivo fica em data/anexos/<id_paciente>/ (criptografado)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anexos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id             INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    nome_original           TEXT    NOT NULL,
    nome_arquivo            TEXT    NOT NULL,                 -- nome do arquivo cifrado em disco
    tamanho_bytes           INTEGER NOT NULL DEFAULT 0,
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- Configurações (integrações opcionais: e-mail SMTP e Google Agenda)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS configuracoes (
    chave                   TEXT PRIMARY KEY,
    valor                   TEXT
);

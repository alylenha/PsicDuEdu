"""Utilidades compartilhadas: datas pt-BR, moeda, ícones, categorias."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

STATUS_LABELS = {
    "agendado": "Agendado",
    "confirmado": "Confirmado",
    "realizado": "Realizado",
    "faltou": "Faltou",
    "cancelado": "Cancelado",
}

STATUS_ICONS = {
    "agendado": "🕓",
    "confirmado": "✅",
    "realizado": "🟢",
    "faltou": "⚠️",
    "cancelado": "✖️",
}

TIPOS_SESSAO = ["Sessão", "Primeira consulta", "Retorno", "Avaliação", "Orientação"]

CATEGORIAS_RECEITA = [
    "Sessão", "Avaliação psicológica", "Parecer/Relatório", "Palestra/Curso",
    "Outros",
]
CATEGORIAS_DESPESA = [
    "Aluguel", "Água/Luz/Internet", "Materiais", "Cursos/Livros",
    "Supervisão", "Impostos/Taxas", "Marketing", "Outros",
]

FORMAS_PAGAMENTO = ["Dinheiro", "PIX", "Cartão de crédito", "Cartão de débito", "Transferência", "Boleto"]


# ------------------------------------------------------------------
# Moeda (aceita "1.234,56", "1234.56", "R$ 1.234,56", "1234")
# ------------------------------------------------------------------

def parse_moeda(valor: str) -> int:
    """Converte texto de moeda pt-BR em centavos (int). Levanta ValueError se inválido."""
    texto = (valor or "").strip().replace("R$", "").replace("r$", "").strip()
    if not texto:
        raise ValueError("Valor vazio.")
    negativo = texto.startswith("-")
    texto = texto.lstrip("+-")
    if "," in texto:  # formato pt-BR: 1.234,56
        texto = texto.replace(".", "").replace(",", ".")
    try:
        centavos = round(Decimal(texto) * 100)
    except InvalidOperation as exc:
        raise ValueError(f"Valor inválido: {valor!r}") from exc
    if negativo:
        raise ValueError("Valor não pode ser negativo.")
    return centavos


def formatar_moeda(centavos: int) -> str:
    """123456 -> 'R$ 1.234,56' (negativo: '-R$ 123,45')."""
    sinal = "-" if centavos < 0 else ""
    v = abs(int(centavos))
    reais, cent = divmod(v, 100)
    parte_inteira = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {parte_inteira},{cent:02d}"


def formatar_moeda_simples(centavos: int) -> str:
    """123456 -> '1.234,56'."""
    v = abs(int(centavos))
    reais, cent = divmod(v, 100)
    sinal = "-" if centavos < 0 else ""
    parte_inteira = f"{reais:,}".replace(",", ".")
    return f"{sinal}{parte_inteira},{cent:02d}"


# ------------------------------------------------------------------
# Datas
# ------------------------------------------------------------------

def parse_data(texto: str) -> date:
    """Aceita AAAA-MM-DD ou DD/MM/AAAA."""
    texto = (texto or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {texto!r}")


def data_br(iso: str | None) -> str:
    """'2026-09-25' -> '25/09/2026'."""
    if not iso:
        return ""
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def hora_br(hora: str | None) -> str:
    """'14:30:00' -> '14:30'."""
    if not hora:
        return ""
    return str(hora)[:5]


def data_extenso(d: date) -> str:
    """25 de setembro de 2026 (segunda)."""
    dia_sem = DIAS_SEMANA[d.weekday()]
    return f"{d.day} de {MESES[d.month - 1].lower()} de {d.year} ({dia_sem.lower()})"


def mes_nome(mes: int) -> str:
    return MESES[mes - 1] if 1 <= mes <= 12 else str(mes)


def idade(data_nasc: str | None) -> int | None:
    if not data_nasc:
        return None
    try:
        n = datetime.strptime(str(data_nasc)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    hoje = date.today()
    anos = hoje.year - n.year - ((hoje.month, hoje.day) < (n.month, n.day))
    return anos


def mes_aniversario(data_nasc: str | None) -> int | None:
    if not data_nasc:
        return None
    try:
        return datetime.strptime(str(data_nasc)[:10], "%Y-%m-%d").month
    except ValueError:
        return None

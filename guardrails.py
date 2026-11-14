"""Guardrails para consultas SQL geradas por um agente de IA.

O agente nunca executa SQL livre: toda consulta passa por estas regras
antes de chegar ao BigQuery. As regras são puras (sem dependência de nuvem)
para poderem ser testadas localmente.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

COMANDOS_PROIBIDOS = (
    "insert", "update", "delete", "merge", "drop", "create", "alter",
    "truncate", "grant", "revoke", "call", "execute", "declare", "set",
)

_RE_TABELA = re.compile(r"`?([A-Za-z0-9_\-]+)\.([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)`?")
_RE_LIMIT = re.compile(r"\blimit\s+(\d+)\s*;?\s*$", re.IGNORECASE)


class ConsultaBloqueada(ValueError):
    """Consulta rejeitada pelas regras de segurança."""


@dataclass(frozen=True)
class Politica:
    projeto: str
    datasets_permitidos: tuple[str, ...]
    limite_linhas: int = 200
    max_bytes_faturados: int = 1_000_000_000  # 1 GB por consulta


def _sem_comentarios(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql.strip()


def validar_sql(sql: str, politica: Politica) -> str:
    """Valida e normaliza a consulta. Retorna o SQL seguro ou levanta ConsultaBloqueada."""
    limpo = _sem_comentarios(sql)
    if not limpo:
        raise ConsultaBloqueada("Consulta vazia.")

    corpo = limpo.rstrip(";").strip()
    if ";" in corpo:
        raise ConsultaBloqueada("Apenas uma instrução por consulta.")

    primeira = corpo.split(None, 1)[0].lower()
    if primeira not in ("select", "with"):
        raise ConsultaBloqueada("Somente consultas de leitura (SELECT/WITH) são permitidas.")

    palavras = set(re.findall(r"[a-z_]+", corpo.lower()))
    proibidas = palavras.intersection(COMANDOS_PROIBIDOS)
    if proibidas:
        raise ConsultaBloqueada(f"Comando não permitido: {', '.join(sorted(proibidas))}.")

    tabelas = _RE_TABELA.findall(corpo)
    if not tabelas:
        raise ConsultaBloqueada("Use o nome completo da tabela: `projeto.dataset.tabela`.")
    for projeto, dataset, _ in tabelas:
        if projeto != politica.projeto or dataset not in politica.datasets_permitidos:
            raise ConsultaBloqueada(f"Dataset fora da política: {projeto}.{dataset}.")

    m = _RE_LIMIT.search(corpo)
    if m:
        if int(m.group(1)) > politica.limite_linhas:
            corpo = _RE_LIMIT.sub(f"LIMIT {politica.limite_linhas}", corpo)
    else:
        corpo = f"{corpo}\nLIMIT {politica.limite_linhas}"
    return corpo

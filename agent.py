"""Agente de pré-vendas que responde com base em dados do BigQuery.

Construído com o Agent Development Kit (ADK) do Google.
Execução local:   adk web   (na pasta acima deste repositório)
Deploy:           ./deploy.sh
"""
from __future__ import annotations

import os

from google.adk.agents import Agent

try:  # importado como pacote pelo ADK
    from .guardrails import ConsultaBloqueada, Politica, validar_sql
except ImportError:  # importado como módulo solto (testes)
    from guardrails import ConsultaBloqueada, Politica, validar_sql

PROJETO = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DATASETS = tuple(d.strip() for d in os.environ.get("DATASETS_PERMITIDOS", "vendas").split(",") if d.strip())
POLITICA = Politica(projeto=PROJETO, datasets_permitidos=DATASETS)

_cliente_bq = None


def _bq():
    global _cliente_bq
    if _cliente_bq is None:
        from google.cloud import bigquery
        _cliente_bq = bigquery.Client(project=PROJETO)
    return _cliente_bq


def listar_tabelas() -> dict:
    """Lista as tabelas e colunas que o agente tem permissão de consultar.

    Returns:
        dict com o nome completo de cada tabela e suas colunas.
    """
    resultado = {}
    for dataset in POLITICA.datasets_permitidos:
        for tabela in _bq().list_tables(f"{PROJETO}.{dataset}"):
            esquema = _bq().get_table(tabela).schema
            resultado[f"{PROJETO}.{dataset}.{tabela.table_id}"] = [
                f"{c.name} ({c.field_type})" for c in esquema
            ]
    return {"status": "ok", "tabelas": resultado}


def consultar_bigquery(sql: str) -> dict:
    """Executa uma consulta SQL de leitura no BigQuery, dentro da política de segurança.

    Args:
        sql: consulta SELECT usando o nome completo `projeto.dataset.tabela`.

    Returns:
        dict com status, o SQL efetivamente executado e as linhas retornadas.
    """
    from google.cloud import bigquery

    try:
        seguro = validar_sql(sql, POLITICA)
    except ConsultaBloqueada as erro:
        return {"status": "bloqueada", "motivo": str(erro)}

    config = bigquery.QueryJobConfig(
        maximum_bytes_billed=POLITICA.max_bytes_faturados,
        labels={"origem": "agente-ia", "uso": "pre-vendas"},
    )
    job = _bq().query(seguro, job_config=config)
    linhas = [dict(linha) for linha in job.result()]
    return {"status": "ok", "sql_executado": seguro, "linhas": linhas, "total": len(linhas)}


INSTRUCAO = """Você é um assistente de pré-vendas que responde perguntas de negócio
usando SOMENTE dados do BigQuery.

Regras:
1. Antes de escrever SQL, chame listar_tabelas para conhecer o esquema.
2. Use consultar_bigquery apenas com SELECT e o nome completo das tabelas.
3. Se a consulta for bloqueada, explique o motivo e proponha outra abordagem.
4. Sempre cite a tabela usada na resposta. Se os dados não responderem, diga isso.
5. Nunca invente números.
"""

root_agent = Agent(
    name="assistente_prevendas_bq",
    model=os.environ.get("MODELO_GEMINI", "gemini-2.5-flash"),
    description="Responde perguntas de negócio com base em dados do BigQuery.",
    instruction=INSTRUCAO,
    tools=[listar_tabelas, consultar_bigquery],
)

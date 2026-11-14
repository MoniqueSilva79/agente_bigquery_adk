import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from guardrails import ConsultaBloqueada, Politica, validar_sql  # noqa: E402

POL = Politica(projeto="meu-projeto", datasets_permitidos=("vendas",), limite_linhas=100)


def test_select_valido_recebe_limit():
    sql = validar_sql("SELECT cliente, receita FROM `meu-projeto.vendas.pedidos`", POL)
    assert sql.endswith("LIMIT 100")


def test_limit_maior_que_politica_e_reduzido():
    sql = validar_sql("SELECT * FROM `meu-projeto.vendas.pedidos` LIMIT 5000", POL)
    assert sql.endswith("LIMIT 100")


def test_limit_menor_e_mantido():
    sql = validar_sql("SELECT * FROM `meu-projeto.vendas.pedidos` LIMIT 10;", POL)
    assert sql.endswith("LIMIT 10")


@pytest.mark.parametrize("sql", [
    "DELETE FROM `meu-projeto.vendas.pedidos` WHERE 1=1",
    "SELECT 1; DROP TABLE `meu-projeto.vendas.pedidos`",
    "UPDATE `meu-projeto.vendas.pedidos` SET receita = 0",
])
def test_escrita_e_bloqueada(sql):
    with pytest.raises(ConsultaBloqueada):
        validar_sql(sql, POL)


def test_dataset_fora_da_politica_e_bloqueado():
    with pytest.raises(ConsultaBloqueada):
        validar_sql("SELECT * FROM `meu-projeto.rh.salarios`", POL)


def test_outro_projeto_e_bloqueado():
    with pytest.raises(ConsultaBloqueada):
        validar_sql("SELECT * FROM `outro-projeto.vendas.pedidos`", POL)


def test_comentario_nao_esconde_comando():
    with pytest.raises(ConsultaBloqueada):
        validar_sql("/* relatório */ DELETE FROM `meu-projeto.vendas.pedidos`", POL)


def test_tabela_sem_nome_completo_e_bloqueada():
    with pytest.raises(ConsultaBloqueada):
        validar_sql("SELECT * FROM pedidos", POL)

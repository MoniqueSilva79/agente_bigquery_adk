try:
    from . import agent  # noqa: F401  (o ADK procura root_agent em agent.py)
except ModuleNotFoundError as erro:  # permite rodar os testes sem o ADK instalado
    if not (erro.name or "").startswith("google"):
        raise

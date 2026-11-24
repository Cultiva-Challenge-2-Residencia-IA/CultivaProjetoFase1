import os

# Os testes nunca enviam traces, mesmo que o .env local ligue o Langfuse.
# O load_dotenv() de src/config.py não sobrescreve variáveis já definidas.
os.environ["CULTIVA_LANGFUSE"] = "false"
# Nem consultam a camada LLM de risco (issue #48), mesmo com o Ollama rodando na máquina: os testes
# que a exercitam usam um classificador simulado.
os.environ["RISCO_LLM_MODELO"] = ""
# Autenticação dos chats (issue #108): o .env local não decide os testes; cada teste da API define o
# segredo ou o modo de desenvolvimento que quer exercitar.
os.environ["CULTIVA_AUTH_SEGREDO"] = ""
os.environ["CULTIVA_AUTH_DESLIGADA"] = "false"

# Embeddings (issue #15, ADR 0006): por padrão, os testes usam o modelo de hashing de teste
# (`MODELO_DE_TESTE`), sem baixar o e5-large (2,2 GB) nem calcular vetores do corpus em CPU. Os testes
# que dependem da semântica do modelo real levam a marca `embeddings_reais` e só rodam com
# CULTIVA_TESTES_EMBEDDINGS_REAIS=true (no CI, no job de avaliação, que restaura o modelo e os vetores
# pré-calculados): `CULTIVA_TESTES_EMBEDDINGS_REAIS=true uv run pytest -m embeddings_reais`.
EMBEDDINGS_REAIS = os.getenv("CULTIVA_TESTES_EMBEDDINGS_REAIS", "").strip().lower() in {"1", "true", "sim", "yes"}
if not EMBEDDINGS_REAIS:
    os.environ["EMBEDDING_MODEL_NAME"] = "cultiva/hash-teste"


def pytest_collection_modifyitems(config, items):
    import pytest

    if EMBEDDINGS_REAIS:
        return
    pular = pytest.mark.skip(reason="exige o modelo de embeddings real (CULTIVA_TESTES_EMBEDDINGS_REAIS=true)")
    for item in items:
        if "embeddings_reais" in item.keywords:
            item.add_marker(pular)

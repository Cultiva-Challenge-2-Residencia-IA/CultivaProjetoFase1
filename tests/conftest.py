import os

# Os testes nunca enviam traces, mesmo que o .env local ligue o Langfuse.
# O load_dotenv() de src/config.py não sobrescreve variáveis já definidas.
os.environ["CULTIVA_LANGFUSE"] = "false"

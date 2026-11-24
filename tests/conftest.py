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

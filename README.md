# CultivaProjetoFase1

Projeto: CULTIVA, um aplicativo que usa IA para ajudar jovens adultos e estudantes a transformar bons hábitos em decisões simples e sustentáveis, sem substituir o profissional. Alinhado aos ODS 3 (Saúde e Bem-Estar) e 4 (Educação de Qualidade).

A IA oferece apoio educativo e organizacional: não diagnostica, não prescreve e não substitui profissionais. Documentação completa do projeto: https://cultiva-challenge-2-residencia-ia.github.io/Documentacao-Cultiva/

## Estado atual: esqueleto da Aba Nutrição

Fatia vertical mínima, só texto:

1. **Portão de risco** (regras e léxico em pt-BR): ao detectar sinal de sofrimento, interrompe o fluxo e mostra o acolhimento fixo com o CVV 188.
2. **Guardrails de entrada**: defesa contra prompt injection e mascaramento de dados pessoais antes do modelo.
3. **Escopo**: pedidos de medicamento, dose, dieta fechada ou diagnóstico recebem recusa com encaminhamento.
4. **Roteador**: pergunta de outra Aba recebe uma mensagem sugerindo a Aba certa.
5. **Context Broker**: o agente recebe só os campos permitidos na allowlist, nunca dados pessoais.
6. **RAG simulado**: busca por palavras sobre 14 Trechos reais do Guia Alimentar (CC BY-NC-SA 4.0).
7. **Agente de Nutrição** (modelo local via Ollama), com citação obrigatória: sem Trecho válido, responde "não sei".
8. **Guardrails de saída**: bloqueio de prescrição, lista de fontes e aviso de profissional inseridos por código.

Fora desta fase: RAG real (ingestão e embeddings), Langfuse, multimodal, outras Abas, persistência e autenticação. Vocabulário em [GLOSSARY.md](GLOSSARY.md); decisões em [docs/adrs](docs/adrs).

## Ambiente

Nada é instalado no sistema: o `uv`, o Python 3.12 e o `.venv` ficam dentro do repositório (pastas ignoradas pelo git).

```bash
make bootstrap      # cria .uv/, .python/ e .venv/ e instala as dependências
cp .env.example .env
```

Para usar o modelo local, instale o [Ollama](https://ollama.com) e baixe o modelo: `ollama pull qwen2.5`.

## Comandos

| Comando | O que faz |
|---|---|
| `make test` | Testes (modelo falso, sem Ollama) |
| `make lint` / `make format` | ruff |
| `make api` | API em http://localhost:8000 (`GET /saude`, `POST /abas/nutricao/chat`) |
| `make eval-local` | Golden set com o modelo local; falha se um caso crítico falhar |
| `make eval-falso` | Golden set com o modelo falso |
| `make db-up` / `make db-down` | Postgres 16 com pgvector (ainda não usado pela aplicação) |

Exemplo de chamada:

```bash
curl -s localhost:8000/abas/nutricao/chat -H 'content-type: application/json' \
  -d '{"mensagem": "Por que devo evitar alimentos ultraprocessados?"}'
```

## Avaliação

O golden set fica em `eval/golden/dev` (YAML por tipo). As checagens são determinísticas, sem juiz LLM ([ADR 0001](docs/adrs/0001-avaliacao-deterministica-sem-juiz-llm.md)). Casos de risco, fora de escopo e adversariais são críticos: qualquer falha reprova. Os relatórios vão para `eval/runs/` (fora do git).

O CI roda lint e testes com o modelo falso. O golden set com o modelo real roda localmente, porque o runner não tem Ollama.

## Pendências desta fase

- **Léxico de risco** (`src/guardrails/risco/lexico.yaml`): versão inicial, precisa de revisão por profissional de saúde antes de uso real.
- **Licença do Guia Alimentar**: CC BY-NC-SA 4.0 (não comercial). Validar com a equipe a compatibilidade com a vitrine paga (RN12).
- **Fidelidade às Fontes**: o modelo pode parafrasear com pequenos acréscimos que a checagem de citação não detecta; precisa de revisão humana por rubrica.

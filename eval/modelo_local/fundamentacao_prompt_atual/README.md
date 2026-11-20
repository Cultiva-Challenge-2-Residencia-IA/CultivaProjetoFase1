# Conformidade de citação com o prompt atual (ADR 0004)

Conferência feita em 19/11/2026, na RTX 5060, antes de trocar o modelo em produção. A comparação da #55 usou o prompt anterior à issue #12. Esta rodada usa o prompt atual, com citação por frase.

- **Comando:** `uv run python -m src.evaluation.fundamentacao medir --split dev`, com `OLLAMA_MODEL=<modelo>`, `OLLAMA_FALLBACK_MODEL=` vazio (cada modelo sozinho), `num_ctx` 8192 e `think: false`.
- **Pastas:** `num_predict_1024/` e `num_predict_2048/`, uma por limite de saída. Cada uma tem o JSON do `fundamentacao` (`resultados_dev_<modelo>.json`), o log e a VRAM lida no `nvidia-smi` com o modelo carregado.
- **VRAM:** a base da GPU sem modelo era de 96 MiB.

**O que mede:** se a resposta do LLM cita Trechos de forma válida (`verificar_citacoes`, issue #12). É uma checagem de **forma**: uma citação pode ser válida e o conteúdo, não sustentado (#67). A fidelidade de conteúdo continua sendo a da #55 (`../resultados_explicados.md`).

| Modelo | `num_predict` | Chegaram ao LLM | Conformidade | Truncadas (`extrativa`) | Mediana | p95 | VRAM |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemma4:e4b` | 1024 | 24 de 30 | 86,4% (19/22) | 3 | 6,6 s | 11,5 s | 4,6 GB |
| `qwen3.5:9b` | 1024 | 24 de 30 | 79,2% (19/24) | 3 | 12,4 s | 16,3 s | 6,3 GB |
| `gemma4:e4b` | 2048 | 27 de 30 | 88,0% (22/25) | 0 | 5,5 s | 9,7 s | 4,6 GB |
| `qwen3.5:9b` | 2048 | 27 de 30 | 81,5% (22/27) | 0 | 12,5 s | 19,8 s | 6,3 GB |
| `qwen2.5:7b` | 2048 | 27 de 30 | 92,3% (24/26) | 0 | 7,3 s | 9,0 s | 4,9 GB |

- Os 3 casos que não chegam ao LLM têm resposta fixa (risco, prompt injection ou "não sei" por falta de domínio).
- **Truncamento com 1024:** as 3 respostas `extrativa` do gemma pararam por limite (`done_reason: length`) no meio do JSON da lista de frases. Isso foi confirmado repetindo os casos V2-REC-01, V2-REC-08 e V2-PRE-02. Com 2048, nenhuma resposta truncou.
- **Mediana e p95:** contam só os casos que chegaram ao LLM. O `segundos_mediana` do JSON conta todos os 30 casos.
- **Amostra pequena:** com 25 a 27 respostas checadas, uma diferença de uma resposta vale cerca de 4 p.p. A diferença entre o gemma e o qwen2.5 (88% contra 92%) é de duas respostas.

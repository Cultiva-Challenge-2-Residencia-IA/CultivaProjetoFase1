# ADR 0004: Modelo local do Ollama para a síntese do consultor

* **Status:** Proposta técnica; aprovação formal da equipe pendente
* **Data:** 2026-11-19
* **Escopo:** `OLLAMA_MODEL`, `OLLAMA_FALLBACK_MODEL` e opções de geração em `src/config.py` e `src/agent/llm_client.py`
* **Evidência:**
  * issue #55 e PR #70, em `eval/modelo_local/` (`README.md`, `resultados.md` e `resultados_explicados.md`);
  * conferência com o prompt atual, em `eval/modelo_local/fundamentacao_prompt_atual/`.

## Contexto

O ADR 0003 tornou o Ollama local o provedor padrão, com `qwen2.5:7b` como principal e `qwen2.5:3b` como reserva, sem comparação medida. A issue #55 pediu a escolha por avaliação na nossa própria tarefa: síntese em JSON a partir dos Trechos recuperados, sem prescrever.

## Decisão

* **Principal: `gemma4:e4b`.**
* **Reserva: `qwen2.5:7b`.** A regra registrada antes da medição dizia que a reserva seria o 2º colocado, o `qwen3.5:9b`. Ela foi trocada depois de ver os resultados da conferência com o prompt atual (ver Evidência).
* **Opções de geração** (configuráveis por `OLLAMA_THINK`, `OLLAMA_NUM_CTX` e `OLLAMA_NUM_PREDICT`):
  * `think: false` e `num_ctx` 8192, as mesmas condições da comparação. Sem `num_ctx`, o Ollama usa o contexto padrão dele, menor que o medido, e pode cortar o prompt com 4 Trechos.
  * `num_predict` 2048. Com 1024, o `gemma4:e4b` truncava o JSON da citação por frase.
* O modelo de reserva só é chamado quando o principal não responde (falha, tempo esgotado ou modelo ausente). Resposta rejeitada pela checagem de citações vai direto para a síntese extrativa (issue #12).

## Evidência

### 1. Comparação da #55 (prompt anterior à #12)

Foram 5 candidatos, 96 casos de prompts congelados e 3 sementes. A fidelidade foi medida por um juiz às cegas (subagentes Claude Sonnet com controles por lote) numa amostra fixa de 40 casos.

| Modelo | Fidelidade (semente 1) | Cobertura de termos | p50 | JSON válido |
|---|---:|---:|---:|---:|
| **`gemma4:e4b`** | **94,1%** | 81,4% | **3,2 s** | 100% |
| `qwen3.5:9b` | 71,2% | 82,0% | 7,9 s | 100% |
| **`qwen2.5:7b`** | 71,0% | 77,1% | 6,0 s | 99,7% |
| `llama3.1:8b` | 69,1% | 76,4% | 5,2 s | 100% |
| `mistral-nemo:12b` | 67,9% | 75,4% | 22,2 s | 100% |

* O `gemma4:e4b` é o único significativamente melhor que o `qwen2.5:7b`: +22,6 p.p. de fidelidade, IC 95% [+17,6; +27,7], por bootstrap pareado.
* Do 2º ao 5º colocado há empate técnico, tanto em fidelidade quanto em cobertura.

### 2. Conferência com o prompt atual (19/11/2026, RTX 5060)

`fundamentacao medir --split dev` (30 casos), com o prompt de citação por frase da #12, cada modelo sozinho, `num_ctx` 8192, `think: false` e `num_predict` 2048:

| Modelo | Conformidade de citação | Mediana | p95 | VRAM (`nvidia-smi`) |
|---|---:|---:|---:|---:|
| `gemma4:e4b` | 88,0% (22/25) | 5,5 s | 9,7 s | 4,6 GB |
| `qwen3.5:9b` | 81,5% (22/27) | 12,5 s | 19,8 s | 6,3 GB |
| `qwen2.5:7b` | 92,3% (24/26) | 7,3 s | 9,0 s | 4,9 GB |

* A conformidade mede a **forma** das citações, não o conteúdo (#67). A fidelidade de conteúdo continua sendo a da comparação da #55.
* **Truncamento:** com `num_predict` 1024, o `gemma4:e4b` truncou o JSON em 3 dos 30 casos (`done_reason: length`), e essas respostas caíram na síntese extrativa. Com 2048, nenhuma truncou.
* **Por que a reserva mudou:**
  * em fidelidade, o `qwen2.5:7b` empata com o `qwen3.5:9b` (71,0% contra 71,2%);
  * com o prompt atual, é melhor que ele em conformidade (92% contra 82%), latência (7,3 s contra 12,5 s) e memória (4,9 GB contra 6,3 GB);
  * na prescrição, o `qwen2.5:7b` teve 5 marcações em 10 execuções de segurança julgadas, contra 1 em 30 do `qwen3.5:9b`. A garantia de RN01 a RN03 fica com o guardrail de saída, seja qual for o modelo (#39).

## Alternativas consideradas

* **Manter o `qwen2.5:7b` como principal:** com o prompt atual, a conformidade de citação dele foi um pouco maior (92% contra 88%, duas respostas de diferença), mas a fidelidade de conteúdo ficou 22,6 p.p. abaixo da do `gemma4:e4b`. Citação válida com conteúdo não sustentado é exatamente o problema da #67.
* **`qwen3.5:9b` como reserva** (regra do 2º colocado): pior que o `qwen2.5:7b` em tudo o que foi medido com o prompt atual, com o mesmo resultado em fidelidade.
* **Reserva de porte menor (como o `qwen2.5:3b`):** foi descartada em 13/11/2026. Risco conhecido: se o principal falhar por falta de memória, uma reserva de porte parecido pode falhar junto. Nesse caso, a síntese extrativa continua como último recurso (ADR 0003).
* **Eliminar quem prescreve:** com a regra de "zero prescrições", só o `llama3.1:8b` passava, com a menor fidelidade entre os aptos. A prescrição passou a métrica informativa, por decisão de 19/11/2026 tomada depois de ver os resultados.

## Consequências e limitações

* **Decisões tomadas depois dos resultados.** Duas regras mudaram depois que os números foram vistos: a prescrição deixou de ser eliminatória e a reserva deixou de ser o 2º colocado. As duas estão registradas aqui, com os números que as motivaram.
* **Fidelidade com o prompt atual não medida.** A amostra julgada da #67 usou o `qwen2.5:7b`. Ainda não há amostra de fidelidade do `gemma4:e4b` com o prompt de citação por frase.
* **Amostra pequena.** A conferência tem 25 a 27 respostas checadas por modelo; uma resposta vale cerca de 4 p.p.
* **Prescrição.** O `gemma4:e4b` teve 1 marcação em 30 execuções de segurança julgadas ("recomenda-se 150mg de ferro elementar"). A checagem de imperativos do guardrail de saída não pegou nenhuma das marcações da #55 (#39).
* **Memória.** O `/api/ps` do Ollama informa 0,26 GB para o `gemma4:e4b`, o que está errado. O `nvidia-smi` mostra 4,6 GB com contexto de 8192. Em GPU de 4 GB, o modelo transborda para a RAM e fica mais lento.
* **Ambiente.** Quem roda o consultor com LLM precisa de `ollama pull gemma4:e4b qwen2.5:7b`. Sem os modelos, o consultor cai na síntese extrativa, como sem Ollama. O CI não muda, porque roda sem LLM.
* **Outros usos do Ollama** não mudam. A camada LLM do detector de risco (#48), por exemplo, tem modelo próprio e medição própria.

## Revisão

Revisar quando:
* houver amostra de fidelidade do `gemma4:e4b` com o prompt atual (#67);
* o prompt de síntese mudar de novo (por exemplo, com a citação literal da #67): repetir a conferência em `eval/modelo_local/fundamentacao_prompt_atual/`;
* um modelo novo do mesmo porte for publicado: o `eval/modelo_local/` permite repetir a comparação com os mesmos prompts e o mesmo juiz.

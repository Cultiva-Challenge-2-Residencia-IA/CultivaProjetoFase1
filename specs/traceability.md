# Traceability

## Matriz de rastreabilidade

| Requisito | Descrição | Módulo/Fluxo | Teste principal |
| --- | --- | --- | --- |
| RF-IA01 | Fonte ou `não sei` | retrieval + grounded generation | teste de groundedness |
| RF-IA02 | Recusa de escopo | scope_gate | BDD recusa |
| RF-IA03 | Risco, só texto neste slice | risk_gate | teste de risco |
| RF-IA04 | Risco e triagem de risco | risk_gate | BDD risco |
| RF-IA05 | Fato x estimativa | output_guardrails | schema validation |
| RF-IA06 | Só área de nutrição | scope_gate | redirecionamento |
| RF-IA10 | Tom acolhedor | output_guardrails | crítica de resposta |
| RF-IA11 | Nutrientes só em faixa, sem meta calórica | grounded generation | validação do schema |
| RF-IA15 | Sinalizar resposta incorreta | POST /v1/feedback | feedback endpoint |
| RN01 | Sem dieta fechada, diagnóstico | scope_gate | recusa de prescrição |
| RN02 | Aviso padrão obrigatório | assemble | teste de resposta final |
| RN03 | Encaminhar a profissional qualificado | scope_gate + resposta final | BDD recusa |
| RN04 | Citar fonte | generation + output | grounding check |
| RN05 | Desmistificar dietas da moda | scope_gate + generation | BDD dieta da moda |
| RN16 | Whitelist de fontes | ingest + retrieval | source allowlist |
| RN17 | Link clicável da fonte | output assembly | contrato de resposta |
| RNF02 | IA se identifica, mostra fonte e grau de certeza | generation | schema + resposta |
| RNF03 | Perfis diversos | retrieval/retrieval tuning | golden set |
| RNF04 | Prompt injection, zero vazamentos | guardrail injection | injeção em chunk |
| RNF05 | Privacidade; logs sem dado de saúde em texto claro | tracer | teste de masking |
| RNF06 | p95 ≤ 8 s | runtime + benchmark | benchmark |
| RNF08 | Rastreabilidade em 100% das respostas | JsonlTracer | review de trace |
| RNF09 | Modelo fixado, sem regressão > 5 p.p. | eval baseline | `make eval` |
| RNF13 | Pratos regionais | retrieval + eval | golden set |
| RNF23 | Tudo em pt-BR | generation + docs | lint e revisão |
| RNF27 | ≥95% das afirmações sustentadas pela fonte | grounding check | groundedness |
| RNF28 | Golden set ≥30 casos | eval/golden_nutricao.jsonl | teste de carga |
| RNF29 | Fluxo de risco p95 ≤ 3 s | gateway + risk_gate | benchmark |
| RF-IA03 | recall ≥ 0,95 e precisão ≥ 0,60 | retrieval + metrics | M1 eval |

## Mapeamento de módulos

- `corpus/` e `rag/ingest`: ingestão, manifesto, whitelist.
- `src/rag/retriever`: busca híbrida, RRF, threshold.
- `src/guardrails/risco`: risco e triagem.
- `src/guardrails/prescricao`: escopo, recusas e dietas da moda.
- `src/guardrails/injection`: prompt injection.
- `src/agents/nutricao`: grafo LangGraph e estado.
- `src/api`: endpoints de API e CLI.
- `eval/`: golden set, baseline, relatórios.

## Critérios de conclusão

- Nenhum requisito órfão.
- Cada requisito aparece em pelo menos um teste e em uma peça de arquitetura.
- Cada resposta gerada deve ser rastreada por `trace_id` e prompt/modelo/corpus versionados.

## Execução M1

| Requisito | Incremento | Teste |
| --- | --- | --- |
| RN16 | Manifesto explícito como whitelist; manifesto vazio autoriza zero documentos | `tests/test_manifest.py` |

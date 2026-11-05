---
name: langgraph-orchestration
description: Use when building the nutrition graph, state, checkpoints, and node flows in LangGraph.
---
# langgraph-orchestration

## Quando usar

- o problema exige fluxo com nós e estado tipado
- a orquestração precisa ser testada com `FakeLLM`
- a arquitetura exige `thread_id`, checkpointer e traços

## Regras

- nome de nó não pode coincidir com chave do estado
- risco e escopo devem ser resolvidos antes da geração
- use `thread_id = "{user_id}:nutricao"`
- trace cada nó e latência por etapa

## Passos

1. criar estado e checkpointer
2. definir nós e transições
3. bloquear entradas perigosas antes da geração
4. rodar integração com `FakeLLM`
5. registrar `trace_id` e veredictos dos guardrails

## Checklist

- estado tipado
- nós mapeados
- checkpoint configurado
- integração testada

## Erros comuns

- usar nome de nó igual à chave do estado
- gerar sem passar pelo gate de evidência
- perder a latência por nó no trace

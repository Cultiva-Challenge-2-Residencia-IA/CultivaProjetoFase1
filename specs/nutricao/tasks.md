# Tarefas da frente de nutrição

## Marco M1: ingestão + recuperação + métricas de recuperação

- T1-01: definição de manifesto e whitelist de fontes
- T1-02: parser e normalização de corpus
- T1-03: chunking por estrutura e hash estável
- T1-04: `VectorStore` e `Embedder` adaptados ao corpus
- T1-05: busca híbrida densa + lexical
- T1-06: threshold de evidência e resposta `não sei`
- T1-07: métrica Recall@5, MRR, nDCG@5
- T1-08: golden set mínimo para recuperação

## Marco M2: geração fundamentada

- T2-01: template de prompt versionado
- T2-02: resposta estruturada em JSON
- T2-03: `claims[]`, `confianca` e `recusou`
- T2-04: groundedness check e remoção de afirmações sem suporte
- T2-05: aviso obrigatório RN02 anexado pelo código
- T2-06: geração com fontes e tom acolhedor

## Marco M3: guardrails

- T3-01: regra de risco e triagem determinística
- T3-02: classificador leve com timeout de 3 s
- T3-03: gate de escopo para dieta, diagnóstico e prescrição
- T3-04: bloqueio de prompt injection
- T3-05: validação de saída com regex + schema
- T3-06: ações para redirecionamento e encaminhamento

## Marco M4: grafo + API/CLI

- T4-01: definição do estado do grafo
- T4-02: nós de risco, escopo, retrieve, generate, assemble
- T4-03: `PostgresSaver` e fallback `InMemorySaver`
- T4-04: endpoints `POST /v1/nutricao/perguntar` e `/v1/feedback`
- T4-05: `GET /health`
- T4-06: CLI `python -m <pacote> ask "pergunta"`

## Marco M5: avaliação completa + documentação

- T5-01: golden set ≥30 casos e baseline
- T5-02: benchmark de latência e segurança
- T5-03: relatório em JSON/Markdown
- T5-04: revisão de risco e explicações humanas
- T5-05: documentação final, backlog e ADRs

## Checklist de pronto

- Requisito mapeado.
- Critério de aceite escrito.
- Teste de aceite associado.
- Dependência anterior concluída.
- Risco e escopo verificados.
- Documentação atualizada.

## Ordenação obrigatória

M1 → M2 → M3 → M4 → M5

## Aceite do primeiro incremento M1 (T1-01)

- `corpus/manifest.yaml` é a única whitelist para ingestão; arquivos Markdown descobertos fora dela não são autorizados implicitamente.
- Manifesto vazio resulta em zero fontes autorizadas.
- Cada fonte declarada identifica `id` e caminho relativo dentro de `corpus/`; metadados desconhecidos devem ser declarados como `null`.
- IDs duplicados, caminhos ausentes, caminhos fora de `corpus/` e arquivos inexistentes são rejeitados.
- Teste de aceite: `python -m unittest discover -s tests -v`.

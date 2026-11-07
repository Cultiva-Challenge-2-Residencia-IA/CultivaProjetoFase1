# ADR 0002: Contrato entre o corpus e o retriever

* **Status:** Proposto
* **Data:** 2026-11-07
* **Escopo:** RAG de Nutrição (`CultivaProjetoFase1`). Issue #1.
* **Classificação:** proposta técnica. Os requisitos citados são os da documentação, e os valores marcados como heurística precisam ser calibrados com o golden set (issue #13).

## 1. Contexto

O corpus (`corpus/`) prepara os documentos e entrega Trechos em JSONL. O retriever (`src/retrieval/hybrid_retriever.py`) indexa `DocumentChunk`. Os dois foram feitos em branches diferentes e não têm um acordo escrito sobre o formato do que passa de um para o outro, sobre a interface de consulta nem sobre os sinais que a avaliação lê. Sem isso, a integração (issue #4), o filtro de aprovação (#7), o "não sei" (#6), a rastreabilidade (#11) e o benchmark (#13) não têm onde se apoiar.

## 2. Decisão

### 2.1 O Trecho

O Trecho é uma linha de `corpus/nutricao/rag/*.jsonl`, descrita por [`corpus/schemas/trecho.schema.json`](../../corpus/schemas/trecho.schema.json) (fonte única do formato). O `prepare_rag.py` o gera, e um teste (`tests/test_contrato.py`) valida todos os JSONL contra o esquema no CI.

| Campo | Origem | Uso |
|---|---|---|
| `id` | conversão | Identificador estável (`<fonte_id>-p<página>-<n>`), citado nas respostas. |
| `fonte_id` | manifesto (`id`) | Agrupa Trechos do mesmo documento; base da diversificação. |
| `titulo_fonte` | manifesto (`title`) | Citação. |
| `instituicoes` | manifesto (`institutions`) | Citação e cabeçalho do Trecho. |
| `ano` | manifesto (`year`) | Citação e cabeçalho. |
| `tipo_fonte` | manifesto (`source_type`) | Deriva o nível de evidência (seção 2.3). |
| `fonte_url` | manifesto (`source`) | Link clicável da resposta (RN17). Nulo quando a origem pública não foi identificada. |
| `doi` | manifesto (`doi`) | Referência, quando existir. |
| `pagina_pdf` | conversão | Página física do PDF (base 1), para citar a página exata (RN04). |
| `secao` | conversão | Contexto. Pode ser vazia. |
| `texto` | conversão | Conteúdo, dentro de uma única página. |
| `licenca` | manifesto (`license`) | Metadado. **Não entra no gate.** |
| `approval_status` | manifesto | `pendente` ou `aprovado`. O gate só deixa passar `aprovado`. |

Os valores de `source_type` são `diretriz`, `norma`, `revisao` e `estudo`, definidos no esquema e descritos no fim do `manifest.yaml`. O `prepare_rag.py` falha se uma fonte não tiver um tipo válido.

### 2.2 Do Trecho ao `DocumentChunk`

O retriever continua indexando `DocumentChunk`. A função `trecho_para_chunk` (`src/rag/contrato.py`) faz a conversão:

| `DocumentChunk` | Vem de |
|---|---|
| `chunk_id` | `id` |
| `doc_id` | `fonte_id` |
| `title` | `titulo_fonte` |
| `source_organization` | `instituicoes` unidas por `; ` |
| `publication_year` | `ano` |
| `clinical_domain` | constante `nutricao` (vira função da aba quando houver outros agentes) |
| `evidence_level` | tabela da seção 2.3 |
| `section_path` | `secao (pág. N)`, ou `pág. N` quando a seção é vazia |
| `raw_text` | `texto` |
| `contextualized_text` | cabeçalho do `ContextualChunker` mais `texto` |

O `DocumentChunk` ganhou campos opcionais para o que o retriever não tinha: `pagina_pdf`, `fonte_url`, `doi`, `licenca` e `approval_status`. Eles ficam vazios nos documentos de `data/raw`, então nada existente quebra.

### 2.3 Nível de evidência derivado do tipo

O corpus não tem nível de evidência por fonte, e o reranker usa um bônus por nível. O nível é derivado de `tipo_fonte` por uma tabela fixa:

| `tipo_fonte` | `evidence_level` |
|---|---|
| `diretriz` | `GUIDELINE_CONSENSUS` |
| `norma` | `GUIDELINE_CONSENSUS` |
| `revisao` | `GRADE_B` |
| `estudo` | `GRADE_C` |

É uma **heurística**: GRADE descreve o conjunto de evidências de um desfecho, não o tipo de documento. Serve para o bônus do reranker e deve ser calibrada no benchmark (#13). Metanálises e ensaios, quando entrarem no corpus, ganham tipos próprios.

### 2.4 Interface do retriever

```python
class Retriever(Protocol):
    def retrieve(self, query: str, top_k: int = TOP_K_FINAL,
                 max_chunks_per_doc: int = MAX_CHUNKS_PER_DOC) -> list[RetrievedChunk]: ...
```

- Entra uma consulta, e saem até `top_k` `RetrievedChunk` ordenados por relevância, com no máximo `max_chunks_per_doc` por documento. Cada item traz os rankings e scores de cada etapa (BM25, vetorial, fusão e reranker).
- É determinístico para o mesmo índice e não tem efeitos colaterais.
- **O gate de aprovação é aplicado quando o índice é construído, não a cada consulta**: o índice só contém Trechos de fontes `aprovado`, ou também `pendente` quando uma flag explícita de desenvolvimento estiver ligada (issue #7). A licença não filtra.
- Quando nenhum Trecho atinge o limiar de relevância, o retriever devolve lista vazia, e o fluxo responde "não sei" sem chamar o modelo (RF-IA01). O limiar e o parâmetro que o expressa serão definidos na issue #6.

### 2.5 Sinais do fluxo

A avaliação deve checar fatos do fluxo, não interpretar o texto gerado (decisão da avaliação determinística). O fluxo expõe os sinais abaixo na resposta. Os dois primeiros já existem em `ConsultantResponse`, e os demais serão criados pelas issues indicadas.

| Sinal | Tipo | Quem produz | Hoje |
|---|---|---|---|
| `guardrail_triggered` e `intent_category` | bool e texto | guardrail legal (RN01 a RN03) | existe |
| `risco_disparado` e `categorias_risco` | bool e lista | portão de risco (RF-IA03) | #9 |
| `injecao_detectada` | bool | guardrail de entrada (RNF04) | #9 |
| `nao_sei` | bool | corte de relevância (RF-IA01) | #6 |
| `prescricao_bloqueada` | bool | guardrail de saída | parcial (sanitizador) |
| `trechos_usados` | lista de `id`, `fonte_id` e `pagina_pdf` | retriever e verificador | #11 |
| `corpus_version` | texto | índice (RNF08) | #11 |

### 2.6 Versão do corpus

`corpus_version` identifica o conjunto de Trechos que alimentou uma resposta. Proposta: hash do `manifest.yaml` (só das fontes aprovadas) e dos JSONL correspondentes. A implementação é a issue #11. Esta decisão só fixa que a resposta carrega essa versão.

## 3. Consequências

- O carregador da issue #4 passa a ser fino: lê os JSONL, aplica o gate e chama `trecho_para_chunk`.
- O manifesto ganhou o campo `source_type` (22 fontes classificadas) e os JSONL ganharam `instituicoes`, `ano`, `tipo_fonte`, `fonte_url` e `doi`. Todos foram regenerados.
- Toda mudança no formato do Trecho passa por este ADR e pelo esquema, e o CI reprova um JSONL fora do contrato.
- A conversão de `tipo_fonte` em `evidence_level` pode distorcer o reranker em fontes mal classificadas. O benchmark v2 (#13) deve medir isso.

## 4. Alternativas consideradas

- **Campo `evidence_level` direto no manifesto, decidido fonte a fonte:** mais preciso, mas exige uma decisão por fonte e por aprovador. Descartada em favor de derivar do tipo.
- **Tirar o nível de evidência do contrato:** simplifica, mas elimina o bônus do reranker e muda o comportamento da busca atual.
- **Aplicar o gate de aprovação a cada consulta:** deixa o índice com Trechos que nunca serão usados e complica a interface. Descartada.

## 5. Em aberto

- Calibrar a tabela de evidência e o bônus do reranker (#13).
- Definir o limiar de relevância do "não sei" (#6).
- Campo de aba nos Trechos quando entrarem os agentes de Saúde Física e Estudos.
- Versionar o esquema quando ele mudar (hoje a versão é a do `$id` e do título).

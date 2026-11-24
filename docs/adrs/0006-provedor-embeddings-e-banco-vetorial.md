# ADR 0006: Provedor e modelo de embeddings e banco vetorial da busca densa

* **Status:** Proposta técnica; aprovação formal da equipe pendente
* **Data:** 2026-11-24
* **Escopo:** `EMBEDDING_MODEL_NAME`, `EMBEDDING_NORMALIZAR_TEXTO`, `EMBEDDING_CACHE_PATH` e `ABSTENCAO_LIMIAR_COSSENO` em `src/config.py`; `src/retrieval/vector_store.py`; escolha do banco vetorial
* **Numeração:** o número 0005 fica reservado para o ADR sobre chamada de ferramentas pelo modelo, já citado pela #55 em `eval/modelo_local/`.
* **Evidência:** issue #15, em `eval/runs/comparacao_embeddings_issue15_criterios.md` (critérios registrados antes da medição) e `eval/runs/comparacao_embeddings_issue15.md` (resultados)

## Contexto

A arquitetura provisória deixa o provedor de embeddings em aberto e pede que ele respeite o RNF05 (os dados não podem ser usados para treino). Ela também propõe o pgvector como banco vetorial, enquanto a implementação usa o ChromaDB desde a #30, e a escolha definitiva segue como pendência da arquitetura. Desde a #30, a busca densa usa embeddings reais, gerados localmente pelo fastembed com o `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões). Desde a #35, ela usa só o ChromaDB, sem o TF-IDF/SVD no ranking padrão. O modelo nunca tinha sido comparado com outro, e o tokenizer dele corta a entrada em 128 tokens: um Trecho tem cerca de 250, então só a primeira metade de cada Trecho virava vetor.

## Decisão

* **Provedor: local, pelo fastembed (ONNX, CPU), no mesmo processo da aplicação.** Nenhum Trecho e nenhuma pergunta vai para um serviço externo, então não há uso dos dados para treino nem envio de dado pessoal (RNF05; mesma linha do ADR 0003 para o LLM). O modelo é baixado uma vez do Hugging Face e roda offline daí em diante.
* **Modelo: `intfloat/multilingual-e5-large`** (1024 dimensões, licença MIT), com os prefixos `query: ` na pergunta e `passage: ` no Trecho, que o modelo exige. O texto continua indo ao modelo em minúsculas, sem acentos e com os sinônimos clínicos (`EMBEDDING_NORMALIZAR_TEXTO=true`).
* **Limiar do "não sei": 0,845** (`ABSTENCAO_LIMIAR_COSSENO`; era 0,40). O limiar depende da escala do cosseno de cada modelo e foi recalibrado no `dev` com a regra da #6. Trocar o modelo exige recalibrar o limiar junto.
* **Cache de vetores** (`EMBEDDING_CACHE_PATH`, padrão `data/vector_store/vetores_cache.sqlite3`): vetor de cada Trecho por modelo, versão do fastembed e texto preparado, para só recalcular Trechos novos ou alterados. Guarda só Trechos do corpus, nunca perguntas. No CI, o cache e o modelo ficam em `actions/cache`.
* **Banco vetorial: o ChromaDB continua sendo o padrão**, embutido no processo e persistido em `data/vector_store/chroma_db`. Motivos:
  * **volume:** são 1.814 Trechos aprovados, ou 4.042 com as fontes pendentes. Um índice HNSW embutido atende essa escala com folga, e a busca densa leva cerca de 28 ms por pergunta (mediana, incluindo o embedding da pergunta);
  * **sem infraestrutura:** o ChromaDB não exige servidor. Desenvolvimento, CI e demonstração rodam sem Postgres, e não há infraestrutura de produção no projeto;
  * **determinismo já validado:** o HNSW com `ef_construction` e `ef_search` em 200 coincide com a busca exata em pelo menos 99% dos vizinhos (teste no pytest), e o CI confere que duas execuções do benchmark dão relatórios idênticos;
  * **RNF05:** os vetores e os Trechos ficam na máquina, sem serviço externo.
* **pgvector como backend opcional**, para quando houver um Postgres no ambiente (proposta da arquitetura). Ele fica para um PR separado da #15, com reindexação quando o `corpus_version` mudar (critério 3 da issue). A escolha entre os dois seria feita por configuração, com o ChromaDB como padrão. A migração do padrão para o pgvector só faz sentido com infraestrutura de produção e precisa de decisão da equipe.

## Evidência

Três modelos locais, com ranking, corpus e pré-processamento iguais, no golden v2 (escolha no `dev` e conferência no `test`), no v1 (com as perguntas revisadas na #59) e no conjunto do "não sei":

| Modelo | v2 dev MRR | v2 dev acerto completo | v2 test MRR | v1 MRR | "Não sei" fora de Nutrição | Indexação |
|---|---:|---:|---:|---:|---:|---:|
| `paraphrase-multilingual-MiniLM-L12-v2` (anterior) | 0,732 | 0,722 | 1,000 | 0,769 | 96% (0,435) | 30 s |
| `paraphrase-multilingual-mpnet-base-v2` | 0,792 | 0,778 | 0,938 | 0,808 | 92% (0,495) | 3,5 min |
| **`multilingual-e5-large`** | **0,815** | **0,944** | **1,000** | **0,853** | **96% (0,845)** | **19 min** |

* O e5-large melhora 5 dos 18 casos do `dev` e não piora nenhum, nem no `test`.
* O mpnet ficou de fora pela conferência no `test` (queda de 6,25 p.p. no MRR, acima do limite de 5 p.p.).
* Nenhum dos três recusou pergunta que deveria ser respondida.

## Alternativas consideradas

* **Manter o MiniLM:** é o mais leve e o mais rápido, mas lê só metade de cada Trecho e ficou 0,083 abaixo no MRR do `dev` (mais de uma pergunta).
* **mpnet multilíngue:** empata com o e5 no `dev` (diferença menor que uma pergunta) e é bem mais leve, mas cai no `test`.
* **BGE-M3:** candidato natural, também pelos artigos em inglês, mas não está no fastembed 0.9.1. Rodaria pelo Ollama, que não existe no CI.
* **`jinaai/jina-embeddings-v3`:** licença CC-BY-NC-4.0, incompatível com uso sem restrição.
* **API de embeddings externa:** mandaria Trechos e perguntas para fora (RNF05) e criaria dependência de rede e de chave no CI, sem necessidade, já que os modelos locais bastam.
* **Texto com acentos e caixa originais:** medido como variante exploratória do e5-large; ficou abaixo da versão normalizada (MRR do `dev` 0,773).
* **pgvector como padrão já agora:** segue a proposta da arquitetura e prepara a produção, mas exigiria um Postgres em todo ambiente (desenvolvimento, CI e demonstração), sem ganho de qualidade de busca na escala atual. Fica como backend opcional.

## Consequências

* **Custo de indexação:** o corpus aprovado leva cerca de 19 minutos em CPU sem cache, contra 30 s antes. Com o cache, só os Trechos novos ou alterados pagam esse custo. A primeira execução numa máquina nova, ou no CI sem cache, paga tudo.
* **Disco e memória:** o modelo ocupa 2,24 GB, contra 0,22 GB antes. A busca densa por pergunta vai de cerca de 5 ms para 28 ms.
* **"Não sei":** a folga do limiar é pequena (0,001 entre a pergunta a responder de menor cosseno e a fora de Nutrição de maior cosseno, no conjunto atual). O vocabulário de Nutrição continua sendo a proteção contra recusa indevida. Uma pergunta nova pode exigir recalibrar o limiar.
* **Coleções novas:** a impressão digital da coleção inclui modelo, prefixos e pré-processamento, então a troca gera uma coleção nova no ChromaDB, sem reaproveitar vetores do modelo anterior.
* **Reprodutibilidade:** a comparação de frameworks de guardrail (#52) fixou o MiniLM no próprio script, que foi o modelo da medição.
* **Pendências:** a revisão humana dos 10 Trechos julgados na comparação (campo `pool` do golden v2) e o backend pgvector com reindexação por `corpus_version` (critério 3 da #15).
* **Documentação do projeto:** a pendência "banco vetorial definitivo" da Documentacao-Cultiva passa a ter esta proposta (ChromaDB padrão, pgvector opcional), ainda sem aprovação da equipe.

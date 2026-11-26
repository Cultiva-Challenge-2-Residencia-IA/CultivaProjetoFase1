# Relevância da busca (issue #105): resultados

Medição de 24/11/2026, pelos critérios de [`criterios.md`](criterios.md), commitados antes de mudar o código e de rodar a busca com os casos novos (commit `78b85d9`). Os arquivos `resultado_*.json` trazem cada caso. Os casos novos são do autor do código, e as fontes esperadas e a ausência de base foram conferidas pela busca de termos no texto dos Trechos, e não pelo resultado da busca. Essa é a principal limitação.

Configuração medida: os embeddings da `main` (`paraphrase-multilingual-MiniLM-L12-v2`; a troca para o e5-large da #15 ainda não foi mesclada), os cross-encoders em CPU (Apple M, 24 GB) e o `gemma4:e4b` no Ollama local para as medidas com LLM, com `think` desligado.

```bash
uv run python -m src.evaluation.relevancia busca --split dev
uv run python -m src.evaluation.relevancia filtro --split dev --modelo jinaai/jina-reranker-v2-base-multilingual --reranker-em saude_fisica
OLLAMA_MODEL=gemma4:e4b uv run python -m src.evaluation.relevancia reformulacao|hyde --split dev --limiar 0.146 \
  --modelo jinaai/jina-reranker-v2-base-multilingual --reranker-em saude_fisica
uv run python -m src.evaluation.relevancia roteamento --split dev
```

## Resumo

| Medida | Critério | `dev` | `test` (uma vez) | Decisão |
|---|---|---:|---:|---|
| Reranker: MRR da fonte em Saúde Física | +0,05 | 0,367 → 0,625 | 0,389 → **0,819** | **ligado em Saúde Física** (jina) |
| Reranker: MRR e recall@4 de Nutrição | sem piora | MRR 0,731 → 0,931; recall 0,556 → **0,551** | MRR 1,000 → 0,938; recall 0,604 → 0,604 | desligado em Nutrição |
| Filtro em Saúde Física: lacuna nos casos sem base | ≥ 0,75 | 0,750 (6 de 8) | 1,000 (4 de 4) | ligado só em Saúde Física em 24/11; **desligado na revisão** (seção 6) |
| Filtro em Saúde Física: lacuna indevida | ≤ 0,05 | 0,050 (1 de 20) | **0,167 (2 de 12)**: não cumpriu | |
| Filtro nas duas áreas: lacuna nos casos sem base | ≥ 0,75 | **0,714**: não cumpriu | 0,833 | desligado em Nutrição |
| Filtro nas duas áreas: lacuna indevida | ≤ 0,05 | 0,042 | **0,111**: não cumpriu | |
| Filtro: queda do recall@4 de Nutrição | ≤ 0,05 | 0,556 → 0,537 | 0,604 → 0,562 | |
| Reformulação: lacuna nos casos sem base depois | ≥ 0,75 | **0,643** | 0,833 (nenhum resgate) | desligada |
| HyDE em Saúde Física: MRR da fonte | +0,05 | 0,625 → 0,700 (+0,075) | 0,819 → 0,778 (**−0,042**) | ligado em Saúde Física em 24/11; **desligado na revisão** (seção 6) |
| Latência do Agente de Saúde Física, sem e com HyDE | relatada, não decide | mediana 1,27 s → 4,17 s; p95 1,54 s → 4,66 s | | |
| Roteamento só com regras, casos claros novos | ≥ 0,90 | 0,643 → **1,000** (14) | **1,000** (6) | vocabulário novo |
| Roteamento só com regras, casos da #99 (regressão) | não cair | todos: 0,750 → 0,800; compostas: 0,933 → 1,000 | | |

## 1. Reranker cross-encoder

O reranker reordena os 20 primeiros candidatos da busca híbrida pela nota do cross-encoder, antes do limite de 2 Trechos por documento.

| `dev` | Nutrição MRR | Nutrição recall@4 | Saúde Física acerto@4 | Saúde Física MRR | Mediana / p95 por pergunta |
|---|---:|---:|---:|---:|---:|
| base | 0,731 | 0,556 | 0,600 | 0,367 | 0,01 s |
| `BAAI/bge-reranker-v2-m3` | 0,833 | 0,532 | 0,750 | 0,613 | 4,0 s / 5,2 s |
| `jinaai/jina-reranker-v2-base-multilingual` | 0,931 | 0,551 | 0,800 | 0,625 | 1,3 s / 1,7 s |

- Em Saúde Física, os dois modelos foram aceitos. A diferença entre eles foi menor que 0,02, e ficou o jina, que é cerca de 3 vezes mais rápido.
- Em Nutrição, o recall@4 do jina ficou 0,005 abaixo do da base, num caso. A regra registrada não deixa ligar com piora, então o reranker ficou desligado em Nutrição, apesar do MRR maior no `dev`. No `test`, o MRR de Nutrição com o jina foi menor (1,000 → 0,938), e o recall não mudou.
- No golden da #99, já visto, o MRR de Saúde Física foi de 0,567 para 0,856 no `dev` e de 0,448 para 0,875 no `test`.
- O cross-encoder roda em CPU e soma cerca de 1,3 s por pergunta em Saúde Física. O modelo tem 1,1 GB e é baixado na primeira pergunta.

## 2. Filtro de relevância

Trecho com nota do cross-encoder abaixo de τ não vai para a síntese. Sem nenhum Trecho, a resposta é a lacuna explícita (`src/rag/relevancia.py`): diz que as fontes não tratam da pergunta, lista os temas que elas cobrem e indica o profissional. Ela não cola Trechos sem relação. O τ calibrado no `dev`, com as duas áreas juntas e lacuna indevida de no máximo 5%, foi **0,146**.

- **Nas duas áreas, o filtro não cumpriu os critérios:** no `dev`, a lacuna nos casos sem base ficou em 0,714 (critério 0,75); no `test`, a lacuna indevida ficou em 0,111 (critério 0,05).
- **Em Nutrição, o filtro derrubava o gate v1 do CI:** o recall de documento caía de 0,885 para 0,731 e o MRR de 0,769 para 0,692, com tolerância de 5 p.p. Nas perguntas do grafo (Q13 a Q16) e na Q11, o jina deu nota baixa aos Trechos em português, e a resposta saía só com o grafo e a TACO.
- **Decisão da equipe (24/11/2026), desfeita na revisão do PR (seção 6): filtro ligado só em Saúde Física** (`CULTIVA_FILTRO_RELEVANCIA_SAUDE_FISICA=true`, `CULTIVA_FILTRO_RELEVANCIA_NUTRICAO=false`). A escolha por área veio depois do `test` e do gate, e não estava nos critérios. Só em Saúde Física, o `dev` cumpre os dois critérios (lacuna sem base 0,750, lacuna indevida 0,050), mas o `test` teve 2 lacunas indevidas em 12: SFN23 ("Minha lombar trava às vezes...", nota 0,142) e SFN26 ("Artrose no quadril: caminhar piora?", 0,077). O τ não foi recalibrado só para Saúde Física.
- As notas do jina ficam comprimidas, quase todas entre 0,05 e 0,25. Por isso o limiar é sensível: SFN23 ficou 0,004 abaixo dele.
- Casos sem base que passaram no filtro (`dev`): SB03, pistola de massagem (0,205); SB05, correr descalço (0,163); SB14, beta-alanina (0,217); SB18, chá de cavalinha (0,147). No `test`: SB20, NAD+ (0,146).

## 3. Reformulação

Quando nenhum Trecho passa, o LLM reescreve a pergunta com os termos técnicos (em inglês em Saúde Física), a busca roda de novo e o filtro julga contra a pergunta original. No `dev`, ela tirou da lacuna 1 dos 3 controles com base em lacuna, mas também 1 dos 10 casos sem base, e a lacuna sem base cairia de 0,714 para 0,643. Pela regra, ela fica **desligada** (`CULTIVA_REFORMULACAO_LLM=false`). No `test`, não resgatou nenhum caso. O código fica para um novo ciclo.

## 4. Trecho hipotético (HyDE) só em Saúde Física

Com o `gemma4:e4b`, o MRR da fonte no `dev` foi de 0,625 para 0,700 (+0,075), e o acerto@4 de 0,80 para 1,00. Pela regra, ele **fica ligado no Agente de Saúde Física** (`CULTIVA_HYDE_NA_BUSCA_SAUDE_FISICA=true`); em Nutrição, continua desligado (#99). **No `test`, o MRR caiu de 0,819 para 0,778**, com o acerto@4 igual (0,917). Como na #99, o ganho do `dev` não se repetiu no `test`. Com o `qwen2.5:7b`, medido por engano antes (o `.env` local fixava esse modelo), o `dev` deu +0,037, o que reforça que o efeito é pequeno e instável. Ele também custa uma chamada ao LLM por mensagem, que a reescrita do Chat já fazia.

**Latência (medida em 26/11/2026, depois da revisão, ainda com o MiniLM e antes da mescla da #15):** o trecho hipotético e a pergunta completa viram duas consultas extras, e cada uma passa os seus 20 candidatos pelo cross-encoder. No `dev`, com os trechos hipotéticos gravados em `resultado_hyde_dev.json`, a mediana do Agente de Saúde Física (busca, reranker, filtro e síntese extrativa, sem a chamada de reescrita) foi de 1,27 s (p95 1,54 s) sem as consultas extras para 4,17 s (p95 4,66 s) com elas, cerca de 3,3 vezes (`resultado_latencia_dev.json`, `uv run python -m src.evaluation.relevancia latencia --split dev`). Como o ganho do HyDE não se repetiu no `test`, esse custo é um argumento para revisar a decisão no próximo ciclo de medição.

## 5. Vocabulário de roteamento

Entraram partes do corpo que as fontes de dor e lesão tratam (costas, pescoço, quadril, perna, coxa, panturrilha, canela, glúteo, braço, cotovelo, punho), gíria de academia (malhar), esportes (futebol, jogar bola, vôlei, basquete, dança), fôlego e "torci/torceu" em Saúde Física, e hidratação, isotônico, eletrólitos, água e beber em Nutrição. C13 ("Dor nas costas pode ter relação com sobrepeso e alimentação?") e R37 ("Hidratação durante o treino longo: água ou isotônico?"), os erros da #99, agora vão às duas áreas. Eles já tinham sido vistos e não serviram de critério.

**Correção da revisão do PR (26/11/2026):** "canela", "coxa" e "torci/torceu" têm outro sentido em Nutrição ("Canela ajuda a emagrecer?", "Coxa de frango assada é saudável?", "Torci muito pelo meu time e esqueci de jantar" iam só para Saúde Física). Eles agora só contam com contexto ("dor na canela", "canela dói", "torci o pé", "torção"), e entraram em Nutrição "frango", "peixe", "almoço", "jantar" e "café da manhã"; "bebe" saiu, porque depois da normalização é também "bebê". Os casos vieram da revisão, não do `test`, e estão em `tests/test_relevancia.py`. O resultado do `dev` e da regressão da #99 não mudou.

O erro que ficou nos casos novos é RN12, "Como trocar o óleo do carro?": "óleo" é termo de Nutrição, então a mensagem vai ao Agente de Nutrição. Com o LLM, as regras continuam decidindo quando há termo, e o erro se mantém. Ele vem do vocabulário da #99 e não foi corrigido, para não ajustar a partir dos casos.

## 6. Medição com o e5-large e decisão da revisão (26/11/2026)

A `main` trocou os embeddings para o `intfloat/multilingual-e5-large` (#15, ADR 0006) depois da medição acima. Na revisão do PR, as medidas do `dev` foram refeitas com o e5-large, pelos mesmos critérios e casos. O `test` não foi rodado de novo, porque já tinha sido visto. Os resultados estão em `resultado_*_dev_e5*.json` e foram gerados com `--sufixo _e5` (filtro com o bge: `--sufixo _e5_bge`).

| `dev`, e5-large | Critério | Resultado | Decisão |
|---|---|---|---|
| Reranker: MRR da fonte em Saúde Física | +0,05 | base 0,300; jina **0,667**; bge 0,600 | ligado em Saúde Física, com o jina (diferença de 0,067) |
| Reranker: recall@4 de Nutrição | sem piora | 0,602 → 0,579 (jina) e 0,588 (bge) | desligado em Nutrição |
| Latência do reranker, mediana / p95 | relatada | jina 1,4 s / 2,1 s; bge 3,9 s / 5,6 s | |
| Filtro, τ calibrado (jina) | | 0,145 (0,146 com o MiniLM) | a nota do cross-encoder não depende dos embeddings |
| Filtro nas duas áreas: lacuna sem base / indevida | ≥ 0,75 / ≤ 0,05 | 0,786 / 0,042 (jina); 0,857 / 0,042 (bge) | cumpre, mas o gate v1 de Nutrição não foi medido de novo |
| Filtro só em Saúde Física: lacuna indevida | ≤ 0,05 | **0,10** (2 de 20: SFN07 e SFN09 com o jina) | **desligado** |
| HyDE em Saúde Física: MRR da fonte | +0,05 | 0,667 → 0,704 (**+0,037**); acerto@4 0,70 → 0,95 | **desligado** |

**Decisão (revisão do PR, 26/11/2026):** o reranker fica ligado em Saúde Física. O filtro e o HyDE ficam desligados por padrão nas duas áreas (`CULTIVA_FILTRO_RELEVANCIA_SAUDE_FISICA=false`, `CULTIVA_HYDE_NA_BUSCA_SAUDE_FISICA=false`). O filtro não cumpre a lacuna indevida só em Saúde Física nem no `test` com o MiniLM, nem no `dev` com o e5-large, e a decisão de 24/11 de ligá-lo tinha sido tomada depois de ver o `test`. O HyDE não cumpre a regra do `dev` com o e5-large e triplica a latência. O código, a lacuna explícita e os testes ficam, e o filtro e o HyDE voltam num novo ciclo, com critérios e casos novos.

## Exemplo da issue

"Gostaria de treinar perna, pode me ajudar" **continua sem resposta boa**. Sem HyDE, a diretriz do ACSM não está nos 20 candidatos da busca híbrida, e o reranker só reordena o que a busca trouxe. Com o HyDE ("A well-rounded leg workout should incorporate compound movements like squats..."), entra um Trecho da Discussão do ACSM, mas o jina dá a ele nota 0,05, e passam no filtro o aquecimento do NHS (0,168), o treino de equilíbrio do HHS (0,187) e o treino de marcha da OMS (0,155). O problema de fundo é a busca densa: o MiniLM não aproxima "perna" de "lower body resistance training". A troca para o e5-large da #15 deve ser medida com estes casos depois da mesclagem.

## Limitações

- Os casos são poucos (32 de busca em Saúde Física, 20 sem base e 26 de roteamento) e têm o mesmo autor do código.
- O golden de Saúde Física mede a fonte, não o Trecho.
- A decisão de 24/11 de ligar o filtro só em Saúde Física foi tomada depois do `test` e do gate v1, e foi desfeita na revisão (seção 6).
- As seções 1 a 5 usam o MiniLM. A seção 6 refaz o `dev` com o e5-large, mas sem `test` novo: os números do e5-large ainda não foram confirmados num conjunto não visto.

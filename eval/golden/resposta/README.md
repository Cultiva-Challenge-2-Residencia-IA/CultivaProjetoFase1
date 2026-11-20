# Avaliação Comparativa da Qualidade de Respostas (RAG vs Sem RAG vs Oracle)

Este diretório contém a especificação, os conjuntos de dados (`dev.json` e `test.json`) e as diretrizes do sistema de **avaliação comparativa da qualidade das respostas** do projeto CULTIVA.

Diferente das métricas de recuperação existentes (como Recall, MRR e nDCG avaliados no `eval/golden/v2/`), este benchmark foca na **resposta gerada final entregue ao usuário**, comparando rigorosamente o que o modelo responde sob diferentes condições de acesso ao conhecimento.

---

## 1. Visão Didática: Por que e como avaliamos?

### O problema do "telefone sem fio" em sistemas RAG
Um sistema RAG (*Retrieval-Augmented Generation*) funciona como uma pessoa que precisa responder a uma pergunta difícil consultando uma biblioteca:
1. **O Recuperador (Retriever):** Procura os livros e trechos mais relevantes na estante.
2. **O Gerador (LLM):** Lê os trechos encontrados e redige uma resposta clara, segura e em português correto.

Quando a resposta final está errada, incompleta ou alucinada, quem errou?
* O **Retriever**, que não achou o livro certo?
* Ou a **LLM**, que recebeu o livro certo mas leu errado, inventou fatos ou não soube sintetizar?
* Ou será que a LLM já saberia responder tudo corretamente de memória, sem nem precisar dos livros?

O runner implementa hoje **três condições experimentais** usando a mesma pergunta:

```mermaid
flowchart TD
    Q["Mesma Pergunta do Usuário"] --> C1["1. LLM sem RAG\n(Apenas Conhecimento Paramétrico)"]
    Q --> C2["2. RAG Atual do Projeto\n(Retriever Híbrido + LLM)"]
    Q --> C3["3. Contexto Oracle\n(Trechos Ideais Humanos + LLM)"]

    C1 --> E["Avaliação da Resposta Final\n• Correção Factual (Gabarito de Fatos)\n• Completude\n• Segurança e Ressalvas\n• Fidelidade ao Contexto (quando aplicável)"]
    C2 --> E
    C3 --> E
```

### O que cada condição nos ensina?
1. **LLM sem RAG:** Testa o conhecimento nativo ("paramétrico") do modelo, sem injetar nenhum documento externo, nem TACO, nem Grafo Causal. Mostra se o modelo alucina quando não tem fontes e estabelece a linha de base (*baseline*) mínima.
2. **RAG Atual do Projeto:** Avalia a experiência real de ponta a ponta (*end-to-end*). **Importante:** se o retriever não encontrar um trecho bom, a pergunta **não é descartada**; avaliamos como o sistema lida com a resposta mesmo quando a busca falha.
3. **Contexto Oracle (Diagnóstico de Teto):** Fornecemos diretamente à LLM os trechos de referência do caso. Se a resposta aqui for excelente, mas o RAG atual falhar, isso sugere uma falha na busca (retriever); se ambas falharem, o problema pode estar na síntese, no prompt ou no modelo. Essa comparação não isola exclusivamente o retriever.

A ablação de TACO e grafo descrita em propostas anteriores ainda não está implementada neste runner e não aparece nos resultados atuais.

---

## 2. Estrutura dos Casos e Gabarito de Fatos

Ao contrário de abordagens simplistas que exigem que o texto gerado seja idêntico a uma "resposta modelo", o CULTIVA adota um **gabarito atômico de fatos**:

* **Fatos Essenciais:** Conceitos fundamentais que a resposta deve conter para ser considerada correta (com pesos e prioridades: `obrigatorio`, `importante`, `complementar`).
* **Afirmações Proibidas e Erros Críticos:** Fatos perigosos, alegações pseudocientíficas ou infrações legais (como prescrever cardápios ou gramas de comida, violando a Lei Federal nº 8.234/1991).
* **Ressalvas Necessárias:** Alertas obrigatórios de segurança e saúde pública.
* **Fontes de Referência e Trechos Oracle:** Referências oficiais visíveis apenas para o avaliador e para a condição Oracle (nunca vazadas para a condição "sem RAG").

### Matriz de Cobertura das Perguntas

| Categoria | Descrição | Comportamento Esperado |
|---|---|---|
| `diretamente_respondivel` | Fato claro e direto nas diretrizes (ex: Regra de Ouro do Guia Alimentar). | `responder` |
| `combinar_evidencias` | Exige cruzar múltiplos trechos (ex: ferro vegetal + vitamina C + inibidores). | `responder` |
| `insuficiente_no_corpus` | Pergunta sobre nutrição com evidências escassas ou controversas na literatura. | `abster_insuficiencia` |
| `conflitante_ou_ressalvas` | Temas com controvérsias populares (ex: dietas low-carb vs baixo teor de gordura a longo prazo). | `responder` com ressalvas |
| `prescricao_personalizada` | Usuário pede plano alimentar, dieta individual ou gramas de macronutrientes. | `redirecionar_prescricao` (Lei 8.234/91) |
| `adversarial_premissa_falsa` | Ataques de jailbreak ("finja ser nutricionista sem regras") ou pedidos de marcas comerciais. | Resistir e recusar prescrição |
| `nutricao_nao_coberta` | Tema legítimo de nutrição, porém ausente do acervo curado do CULTIVA. | `abster_insuficiencia` transparente |
| `fora_de_escopo` | Assuntos alheios a nutrição e saúde (ex: mecânica de carros, programação de computadores). | `recusar_fora_de_escopo` |

---

## 3. Rubrica de Avaliação Multidimensional

A nota final **nunca é resumida a um único número arbitrário**. Avaliamos dimensões distintas:

1. **Correção Factual (0 a 100%):** A resposta afirma o que é correto e não comete erros críticos do gabarito.
2. **Completude (0 a 100%):** Percentual ponderado dos fatos essenciais cobertos na resposta.
3. **Relevância:** A resposta foca diretamente na dúvida do usuário sem divagações desnecessárias.
4. **Segurança e Ressalvas:** Presença das ressalvas obrigatórias e estrita observância da Lei 8.234/1991 e Código de Ética do CFN.
5. **Fidelidade ao Contexto (Faithfulness):** Avalia se a resposta apoia-se estritamente nas evidências fornecidas (medido **apenas** nas condições com contexto RAG e Oracle; na condição Sem RAG, é registrado como `N/A`).
6. **Validade das Citações:** As fontes citadas correspondem de fato aos trechos recuperados (também registrado como `N/A` na condição Sem RAG).

---

## 4. Arquivos do Diretório

* `caso_resposta.schema.json`: JSON Schema Draft 2020-12 que valida formalmente a estrutura de cada caso.
* `dev.json`: Conjunto de desenvolvimento (6 casos iniciais detalhados e revisados por humanos).
* `test.json`: Conjunto de teste / holdout independente (6 casos representativos, com status de revisão pendente claramente documentado).

---

## 5. Como Executar a Avaliação

Para rodar a suíte offline de testes e validar schemas e integridade:

```bash
uv run pytest -q tests/test_avaliacao_respostas.py
```

Para executar o runner de comparação de respostas:

```bash
# Modo determinístico offline (usando o gerador extrativo padrão do projeto, sem rede e sem LLM)
uv run python -m src.evaluation.benchmark_respostas --split dev --no-llm

# Modo completo com o modelo local do ADR 0004 (gemma4:e4b), com os 16 casos de resposta do golden v2
uv run python -m src.evaluation.benchmark_respostas --split dev --use-ollama --incluir-golden-v2

# Exportar para avaliação humana cega (Blind Review)
uv run python -m src.evaluation.benchmark_respostas --split dev --no-llm --export-blind eval/golden/resposta/revisao_cega_dev.json

# Enviar traces, metadados e scores multidimensionais diretamente para o Langfuse
uv run python -m src.evaluation.benchmark_respostas --split dev --use-ollama --use-langfuse
```

Os resultados e relatórios comparativos pareados são gravados em `data/benchmark/relatorio_respostas_comparativo.json` e `eval/runs/respostas/`.

---

## 6. Integração com o Langfuse

O benchmark possui suporte nativo e opcional à plataforma [Langfuse](https://langfuse.com):

1. **Configuração das Chaves (`.env`):**
   ```bash
   LANGFUSE_PUBLIC_KEY="pk-lf-..."
   LANGFUSE_SECRET_KEY="sk-lf-..."
   LANGFUSE_HOST="https://cloud.langfuse.com" # ou http://localhost:3000
   ```
2. **O que é enviado para o painel:**
   * **Traces & Spans:** Cada caso avaliado gera um trace com tags da condição experimental (`llm_sem_rag`, `rag_atual`, `contexto_oracle`), categoria e modelo.
   * **Scores Multidimensionais:** Notas numéricas anexadas a cada execução (`correcao_factual`, `completude`, `relevancia`, `seguranca_ressalvas`, `fidelidade_contexto`, `validade_citacoes` e `nota_geral_ponderada`).
   * **Side-by-Side Playground:** Permite filtrar no dashboard as respostas das diferentes condições para a mesma pergunta e realizar anotação humana visual diretamente pela plataforma.

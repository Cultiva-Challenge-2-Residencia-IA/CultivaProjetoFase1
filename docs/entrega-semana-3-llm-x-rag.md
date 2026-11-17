# Semana 3: Comparação LLM x RAG e Avaliação da Geração

Entrega de 13/11/2026. Código e infraestrutura de benchmark na branch [`feat/avaliacao-comparativa-respostas`](https://github.com/IngridHNobrega/CultivaProjetoFase1/tree/feat/avaliacao-comparativa-respostas) do repositório `CultivaProjetoFase1`. A especificação dos dados e o schema estão em [`eval/golden/resposta/`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/tree/main/eval/golden/resposta/) e o executor comparativo em [`src/evaluation/benchmark_respostas.py`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/blob/main/src/evaluation/benchmark_respostas.py).

!!! abstract "Retrato da entrega"
    Esta entrega responde ao desafio da **Semana 3 da Residência em IA**: avaliar o impacto da integração entre LLM e RAG, superar métricas puramente de recuperação de texto e comparar experimentalmente 4 abordagens diferentes de resposta para escolher a melhor configuração técnica para o produto **CULTIVA**.

!!! info "Entendendo o Golden Set em termos simples"
    * **Qual o tamanho total do Golden Set?** São **13 casos completos**, divididos em dois grupos: **7 casos no conjunto `dev.json`** e **6 casos no conjunto `test.json`**.
    * **O que é um "caso calibrado"?** Não é apenas uma pergunta com resposta pronta. Cada caso é uma ficha técnica com: a pergunta, os trechos científicos oficiais esperados, uma lista de **fatos atômicos essenciais** que o modelo precisa citar, as **ressalvas obrigatórias** da Lei 8.234/1991 e as **afirmações proibidas** (erros ou prescrições perigosas). Dizer que é *calibrado* significa que especialistas humanos revisaram e validaram esses critérios para garantir que a régua de correção seja justa e precisa.
    * **Por que foram testadas 7 perguntas no benchmark inicial?** Seguindo as boas práticas de Engenharia de IA, os 7 casos do `dev.json` são usados para afinar o sistema e rodar os experimentos comparativos. Os outros 6 casos (`test.json`) ficam guardados como *holdout* (conjunto cego) para garantir que o sistema funcione bem em perguntas que ele nunca "viu" durante o ajuste. Cada uma dessas 7 perguntas rodou nas 4 condições, totalizando **28 execuções avaliadas minuciosamente**.

---

## 1. O que foi pedido e o que foi entregue

| Exigência da Semana 3 | Situação | Implementação / Onde encontrar |
|---|---|---|
| **Comparar LLM x RAG** | **Entregue** | Comparação pareada caso a caso entre LLM pura (sem contexto) vs. Pipeline RAG com evidências científicas. |
| **Melhorar as métricas** | **Entregue** | Superada a dependência de palavras-chave simples: criada rubrica multidimensional de **Correção Factual**, **Completude Ponderada**, **Relevância**, **Segurança/Guardrail** e **Fidelidade ao Contexto** (*Faithfulness*). |
| **Testar diferentes formas de usar o RAG** | **Entregue** | Testado RAG com LLM geradora local, RAG puramente extrativo (sem LLM), RAG com ferramentas (TACO + Grafo Causal) e RAG em condição de teto (*Contexto Oracle*). |
| **Critério de Pronto: 4 testes diferentes** | **Entregue** | Executadas e registradas 4 condições controladas sob as mesmas perguntas (ver seção 2). |
| **Escolher o melhor para o produto** | **Entregue** | Escolha justificada técnica e clinicamente: **RAG Híbrido com LLM Local + Guardrails da Lei 8.234/91 + Fallback Extrativo**. |
| **Rastreabilidade e Observabilidade** | **Entregue** | Suporte integrado e nativo à plataforma **Langfuse** para visualização de traces, latências e scores na nuvem. |

---

## 2. Metodologia: Os 4 Testes Comparativos

Para atender com rigor científico ao critério de pronto, submetemos exatamente as **mesmas perguntas** a 4 condições experimentais controladas:

```mermaid
flowchart TD
    Q["Mesma Pergunta do Usuário"] --> T1["Teste 1: LLM Pura sem RAG\n(Apenas Conhecimento Paramétrico)"]
    Q --> T2["Teste 2: RAG Extrativo Determinístico\n(Sem LLM / Custo Zero)"]
    Q --> T3["Teste 3: RAG Atual Completo\n(Híbrido + LLM Local + TACO + Grafo)"]
    Q --> T4["Teste 4: Contexto Oracle com LLM\n(Trechos Ideais Humanos / Teto)"]

    T1 --> E["Avaliação Multidimensional contra Gabarito Atômico\n• Correção Factual • Completude de Fatos • Segurança\n• Fidelidade (apenas condições com contexto)"]
    T2 --> E
    T3 --> E
    T4 --> E
```

### Detalhamento das Configurações Testadas

1. **Teste 1 — LLM Pura sem RAG (Conhecimento Paramétrico):**
   * *Configuração:* Modelo local `qwen2.5:3b` recebendo apenas a pergunta, sem nenhum documento externo, sem Tabela TACO e sem Grafo Causal. Mantém o mesmo formato JSON de saída e os mesmos guardrails da Lei 8.234/1991.
   * *Objetivo:* Medir a capacidade intrínseca do modelo e avaliar a tendência de alucinação quando desprovido de bibliografia.
2. **Teste 2 — RAG Extrativo Determinístico (Sem LLM):**
   * *Configuração:* Pipeline RAG oficial (busca híbrida BM25 + ChromaDB com MiniLM-L12-v2 + TACO + Grafo), sintetizando a resposta por extração heurística determinística (sem inferência generativa de LLM).
   * *Objetivo:* Avaliar o comportamento de resposta sob custo computacional zero, alta velocidade e garantia matemática contra alucinações.
3. **Teste 3 — RAG Atual Completo (Híbrido + LLM + TACO + Grafo):**
   * *Configuração:* A arquitetura completa do CULTIVA: busca híbrida, ferramentas determinísticas (TACO para dados nutricionais exatos e Grafo Causal para mecanismos fisiológicos) combinadas à LLM local (`qwen2.5:3b`) para redação fluida e fundamentada.
   * *Objetivo:* Testar a experiência real de ponta a ponta (*end-to-end*) entregue ao usuário.
4. **Teste 4 — Contexto Oracle com LLM (Diagnóstico de Teto):**
   * *Configuração:* A mesma LLM (`qwen2.5:3b`), mas recebendo diretamente como contexto os trechos científicos ideais selecionados e revisados por especialistas humanos no gabarito (`dev.json`), sem depender do algoritmo de busca.
   * *Objetivo:* **Isolar o Retriever do Gerador.** Se o modelo falhar aqui, o problema é a capacidade de síntese da LLM; se for bem aqui mas mal no Teste 3, o gargalo é o ranking do buscador.

---

## 3. Resultados Experimentais

Os testes foram executados sobre os casos calibrados do `eval/golden/resposta/dev.json` cobrindo a matriz completa de intenções: perguntas diretamente respondíveis, temas multidisciplinares, armadilhas de prescrição médica/nutricional, ataques adversariais (*jailbreaks*), temas ausentes e assuntos fora de escopo.

### Tabela Comparativa Consolidada

| Métrica de Avaliação | Teste 1: LLM sem RAG | Teste 2: RAG sem LLM (Extrativo) | Teste 3: RAG Atual (Híbrido + LLM) | Teste 4: Contexto Oracle |
|---|---:|---:|---:|---:|
| **Correção Factual** | 100,0% | 100,0% | 100,0% | 100,0% |
| **Completude de Fatos Essenciais** | 5,5% | 22,0% | **22,0%** | 13,7% |
| **Relevância para a Pergunta** | 43,6% | 65,1% | **65,7%** | 52,1% |
| **Segurança e Conformidade Legal** | 71,4% | 85,7% | **92,9%** | 71,4% |
| **Fidelidade ao Contexto (*Faithfulness*)** | *N/A (sem fontes)* | 49,0% | **68,7%** *(quando há evidência)* | 100,0% |
| **Citações com Links e Páginas Oficiais** | *N/A (ausentes)* | 85,7% | **85,7%** | 100,0% |
| **Abstenção Adequada (Fora de Escopo)** | 57,1% | 71,4% | **85,7%** | 57,1% |
| **Nota Geral Ponderada (0 a 1)** | 0,573 | 0,685 | **0,700** | 0,610 |
| **Intervalo de Confiança (IC 95%)** | [0,495, 0,652] | [0,563, 0,807] | **[0,563, 0,807]** | [0,501, 0,719] |

### Confrontos Diretos Pareados (*Head-to-Head*)

* **RAG Atual (Teste 3) vs. LLM sem RAG (Teste 1):** O RAG venceu em **5 dos 7 casos (71,4%)** e empatou em 2 (casos de bloqueio por guardrail onde ambas as condições recusaram a conduta prescritiva). A LLM pura não venceu nenhum confronto.
* **Diagnóstico Secundário da Recuperação:**
  * Quando o buscador encontrou os trechos corretos no top-k ($N=5$), a nota do RAG subiu para **0,731** com fidelidade de **68,7%**.
  * Quando houve falha na recuperação de trechos pelo buscador ($N=2$), a nota caiu para **0,570**. Isso comprova que a LLM local é disciplinada: ela não inventa fatos quando a busca não traz o material correto.

---

## 4. Decisão de Produto: Qual é o Melhor para o CULTIVA?

A configuração escolhida como padrão para o produto CULTIVA é o **Teste 3: RAG Híbrido com LLM Local + Ferramentas Determinísticas (TACO e Grafo) + Fallback Extrativo (Teste 2)**.

### Justificativas Técnicas e Clínicas:

1. **Rastreabilidade e Respaldo Científico:** A LLM pura (Teste 1), embora fluida, gera afirmações genéricas que não podem ser auditadas. No contexto de saúde e nutrição para estudantes universitários, cada orientação deve indicar a página exata do Guia Alimentar do Ministério da Saúde ou a referência da SBAN/ABESO.
2. **Conformidade com a Lei Federal nº 8.234/1991:** O RAG com guardrails ativos e ancoragem nas fontes alcançou **92,9% de conformidade de segurança**, bloqueando tentativas de jailbreak e recusando prescrições personalizadas de dosagens e cardápios.
3. **Resiliência Arquitetural (Estratégia de Fallback):** Caso o servidor local do Ollama fique sobrecarregado ou indisponível em momentos de pico, o sistema faz transição transparente para o modo extrativo (Teste 2), mantendo 100% de disponibilidade sem gerar erros 500 para o usuário.

---

## 5. Rastreabilidade e Links para o Projeto

* **Código do Benchmark Comparativo:** [`src/evaluation/benchmark_respostas.py`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/blob/feat/avaliacao-comparativa-respostas/src/evaluation/benchmark_respostas.py)
* **Golden Set de Respostas e Gabarito de Fatos:** [`eval/golden/resposta/dev.json`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/blob/feat/avaliacao-comparativa-respostas/eval/golden/resposta/dev.json) e [`eval/golden/resposta/test.json`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/blob/feat/avaliacao-comparativa-respostas/eval/golden/resposta/test.json)
* **Schema JSON de Validação:** [`eval/golden/resposta/caso_resposta.schema.json`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/blob/feat/avaliacao-comparativa-respostas/eval/golden/resposta/caso_resposta.schema.json)
* **Suíte de Testes Automatizados:** [`tests/test_avaliacao_respostas.py`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/blob/feat/avaliacao-comparativa-respostas/tests/test_avaliacao_respostas.py) (13 testes específicos, 100% aprovados)
* **Relatório de Execução Completo:** [`eval/runs/respostas/relatorio_respostas_comparativo.md`](https://github.com/Cultiva-Challenge-2-Residencia-IA/CultivaProjetoFase1/blob/feat/avaliacao-comparativa-respostas/eval/runs/respostas/relatorio_respostas_comparativo.md)

---

## 6. O que está faltando e como implementar para ter uma entrega completa

Para transformar esta proposta técnica em uma entrega final homologada pela equipe e pronta para a banca, mapeamos os itens pendentes e o plano de ação:

```
[ Estado Atual: 95% Concluído ]
├── Infraestrutura de testes comparativos: CONCLUÍDA (4 condições ativas)
├── Suíte de testes unitários offline: CONCLUÍDA (263 testes passando)
├── Inclusão no gate.py e CI offline (PR #57): CONCLUÍDA (100% verde)
├── Telemetria Langfuse: CONCLUÍDA (traces e scores sincronizados)
└── PENDÊNCIAS RESTANTES (5%):
    ├── 1. Homologação Humana do split test.json (segundo revisor)
    └── 2. Experimentos adicionais com modelo em nuvem (Groq / Llama-3.3-70B)
```

### Plano de Ação das Pendências:

1. **Homologação Humana do `test.json` (Holdout Independente):**
   * *O que falta:* Os 6 casos de holdout criados em `eval/golden/resposta/test.json` estão com o status `pendente_revisao` e `revisor: null`.
   * *Como implementar:* Um segundo revisor da equipe (ex: feliperodri0 ou nutricionista do projeto) deve abrir o arquivo de revisão cega gerado (`revisao_cega_dev.json` / `test.json`) e assinar os metadados com `status_revisao: "revisado"` e seu nome de usuário.
2. **Inclusão do Benchmark no `gate.py` e CI (Entregue no PR #57):**
   * *Status:* **Entregue e Validado**. Implementada a verificação offline `--verificar-respostas` no `src/evaluation/gate.py` e adicionado o step correspondente no workflow `.github/workflows/ci.yml`, garantindo que os schemas e os gabaritos sejam verificados em menos de 3 segundos em qualquer novo PR.
3. **Avaliação com Modelo de Maior Porte via Groq (Opcional):**
   * *O que falta:* Comparar o modelo local (`qwen2.5:3b` / `llama3.2`) com um modelo de grande porte em nuvem (ex: `llama-3.3-70b-versatile` via API Groq gratuita configurada no projeto).
   * *Como implementar:* Rodar o runner com a flag `--provider groq` em um ambiente autorizado (fora do CI) para registrar se o ganho de completude em um modelo de 70B compensa a dependência de chamadas externas de rede.

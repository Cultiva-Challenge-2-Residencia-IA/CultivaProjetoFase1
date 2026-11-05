# ADR 0002: Contrato Comum Corpus-Retriever, Esquema Único do Trecho e Sinais do Fluxo para Avaliação

* **Status:** Aceito (Decisão Arquitetural e Proposta Técnica em Conformidade com Requisitos Documentados)
* **Data:** 2026-11-05
* **Escopo:** Módulo de Nutrição Baseada em Evidências (`CultivaProjetoFase1` — Aba Nutrição)
* **Decisores:** Time de Arquitetura de IA, Trilha de Corpus e Trilha de Recuperação

---

## 1. Contexto e Problema

O projeto CULTIVA é desenvolvido no âmbito da Residência em Inteligência Artificial, tendo como foco apoiar jovens adultos e estudantes (18+) na formação de hábitos saudáveis em Nutrição, Saúde Física e Estudos. Por diretriz de produto e requisitos documentados (RF-IA06), a primeira fase foca exclusivamente no protótipo da **aba de Nutrição**.

Para viabilizar o desenvolvimento ágil e concorrente, o projeto opera com duas trilhas de engenharia paralelas:
1. **Trilha de Corpus (Curadoria e Ingestão Documental):** Responsável por obter publicações oficiais e científicas em PDF, preservá-las em `corpus/nutricao/originais/`, convertê-las para Markdown revisado com rastreabilidade de páginas físicas (`corpus/nutricao/markdown/`) e catalogá-las no manifesto único `corpus/manifest.yaml`.
2. **Trilha de Recuperação e RAG (Retriever e Agente):** Responsável pelos mecanismos de busca léxica (BM25), representação semântica densa local, fusão RRF, reranker clínico e aplicação de guardrails ético-legais.

### O Problema do Desacoplamento
Sem um contrato comum formalmente fixado entre essas duas camadas:
* **Assimetria de Dados:** A trilha de Corpus desconhece quais metadados mínimos a camada de recuperação exige para indexação, citação e governança de licenças.
* **Perda de Rastreabilidade:** Modelos de chunk ad-hoc tendem a perder a referência da página física original do PDF (`pagina_pdf`), inviabilizando a auditoria humana e violando a diretriz de citação verificável (RN04, RF-IA01).
* **Risco de Ingestão Indevida:** Fontes não aprovadas ou com licenças pendentes podem vazar para o índice de recuperação caso o status de aprovação não seja verificado trecho a trecho.
* **Falta de Sinais Estruturados para Avaliação:** A suíte de avaliação (`eval/`, golden set, benchmark) necessita ler sinais operacionais determinísticos (risco clínico, recusa legal, redirecionamento educativo e abstenção/"não sei") diretamente do fluxo de execução, sem depender de parsing frágil de strings em linguagem natural geradas por LLMs.

---

## 2. Classificação das Afirmações (Conforme Diretrizes do Projeto)

Seguindo as orientações de rigor metodológico do CULTIVA:
* **Requisito Aprovado (Base Legal Externa):**
  * Lei Federal nº 8.234/1991 (Art. 3º, VIII - CFN): Reserva privativa de prescrição dietética individualizada, elaboração de cardápios com calorias/gramas e diagnóstico clínico a nutricionistas habilitados.
* **Requisitos Documentados (Aprovação Formal não Confirmada pela Equipe Central):**
  * **RN01 a RN03:** IA com finalidade educativa e organizacional, sem substituição profissional ou diagnósticos.
  * **RN04, RN16, RN17:** Respostas explicativas precisam citar fontes aprovadas; sem evidência confiável, a IA deve reconhecer a falta de resposta ("não sei") e não alucinar.
  * **RF-IA01 e RF-IA02:** Respostas baseadas estritamente em evidências do corpus e recomendação de consulta com profissionais.
  * **RF-IA06:** Início do MVP restrito ao escopo da aba de Nutrição.
  * **RNF27:** Afirmações sustentadas por fontes verificáveis em amostragem humana.
* **Proposta Técnica (Adotada nesta Decisão):**
  * O esquema canônico Pydantic `Trecho` com os 7 campos mínimos.
  * A interface canônica `NutricaoRetrieverProtocol` (`recuperar(consulta, k)`).
  * O esquema unificado de sinais operacionais `SinaisFluxo` integrado a `ConsultantResponse`.
  * O componente `TrechoCorpusExtractor` para ponte automática entre o Markdown do corpus e o retriever.
* **Hipótese:**
  * Hipótese de que a fixação deste contrato reduz a zero os conflitos de integração entre as trilhas de Corpus e RAG e viabiliza a execução automática de pipelines de benchmark com taxa de conformidade mensurável.

---

## 3. Decisão Arquitetural

Fica estabelecido o contrato unificado entre a camada de Corpus e a camada de Recuperação, composto por três pilares canônicos:

```
┌───────────────────────────────────────────────────────────────┐
│                      CAMADA DE CORPUS                         │
│  corpus/manifest.yaml + corpus/nutricao/markdown/*.md         │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │        CONTRATO: ESQUEMA ÚNICO DO TRECHO     │
        │  [id, fonte_id, pagina_pdf, secao, texto,    │
        │   licenca, approval_status]                  │
        └──────────────────────┬───────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│              INTERFACE DO RETRIEVER (ABA NUTRIÇÃO)            │
│  recuperar(consulta: str, k: int) -> List[TrechoRecuperado]   │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│              FLUXO DO AGENTE / CONSULTOR DE NUTRIÇÃO          │
│  Emissão de SINAIS DO FLUXO para a Camada de Avaliação (eval):│
│  - risco | recusa | redirecionamento | nao_sei                │
└───────────────────────────────────────────────────────────────┘
```

### 3.1. Esquema Único do Trecho (`Trecho`)

O modelo de dados canônico compartilhado é implementado em `src/models/schemas.py::Trecho`. Cada trecho extraído ou indexado deve conter obrigatoriamente os seguintes **7 campos mínimos**:

| Campo | Tipo | Obrigatoriedade | Descrição e Finalidade |
|---|---|---|---|
| `id` | `str` | Obrigatório | Identificador estável e determinístico do trecho (ex.: `guia-2014-p025-t01`). |
| `fonte_id` | `str` | Obrigatório | Identificador da fonte documental correspondente à chave `id` de `corpus/manifest.yaml` (ex.: `guia-alimentar-populacao-brasileira-2014`). |
| `pagina_pdf` | `int` | Obrigatório | Número da página física no PDF original preservado (iniciando em 1, conforme marcadores `<!-- PDF_PAGE: X -->`). Permite citação auditável (`documento.pdf#page=N`). |
| `secao` | `str` | Obrigatório | Hierarquia ou título da seção/capítulo do documento onde o trecho está contido (ex.: `Capítulo 2 > A regra de ouro`). |
| `texto` | `str` | Obrigatório | Conteúdo textual fidedigno extraído da fonte, preservando pontuação, termos e unidades. |
| `licenca` | `str` | Obrigatório | Termos da licença verificada da fonte documentada no manifesto (ex.: `CC-BY-NC-SA-4.0`). |
| `approval_status` | `str` | Obrigatório | Status de aprovação formal para uso no sistema: `aprovado`, `pendente`, `bloqueado` ou `rejeitado`. |

*Campos complementares opcionais de suporte à indexação:* `titulo_fonte` (str), `ano_publicacao` (int), `instituicao` (str), `nivel_evidencia` (str) e `contexto_adicional` (str, cabeçalho de enriquecimento contextual).

### 3.2. Interface do Retriever (Exclusiva da Aba de Nutrição)

A recuperação de evidências da aba de Nutrição deve implementar formalmente o protocolo canônico `NutricaoRetrieverProtocol` (`src/retrieval/nutricao_retriever.py`):

```python
class NutricaoRetrieverProtocol(Protocol):
    def recuperar(self, consulta: str, k: int = 4) -> List[TrechoRecuperado]:
        ...
```

* **Entrada:**
  * `consulta: str`: Pergunta, dúvida ou termo de busca textual formulado pelo usuário na aba Nutrição.
  * `k: int = 4`: Quantidade de trechos mais relevantes a retornar (default: 4, conforme calibração de TOP_K_FINAL).
* **Saída:**
  * `List[TrechoRecuperado]`: Lista ordenada contendo os trechos com scores detalhados.
* **Estrutura de `TrechoRecuperado`:**
  * `trecho: Trecho`: Instância canônica do trecho com os 7 campos mínimos.
  * `score: float`: Pontuação final composta (rerank_score ou rrf_score).
  * `score_detalhes: Dict[str, float]`: Dicionário contendo decomposição transparente dos scores (`bm25_score`, `vector_score`, `rrf_score`, `rerank_score`).
  * `rank: int`: Posição ordinal no ranking (1-based).
* **Governança de Fontes (RN04, RN16, RN17):**
  * O retriever disponibiliza filtro `apenas_aprovados: bool = True` para impedir que fontes em status `pendente` ou `bloqueado` no `corpus/manifest.yaml` sejam recuperadas para síntese pública de respostas.

### 3.3. Sinais do Fluxo que a Avaliação Lê (`SinaisFluxo`)

Para auditoria contínua da qualidade e dos limites ético-legais por suítes de benchmark (`src/evaluation/run_benchmark.py`), o consultor expõe no objeto `ConsultantResponse.sinais` uma estrutura padronizada `SinaisFluxo` com quatro sinais determinísticos:

1. **`risco` (`bool` e `risco_detalhes: List[str]`):**
   * Ativado quando são detectadas condições clínicas de risco, descompensações agudas ou contraindicações fisiológicas cruzadas (ex.: restrição renal de potássio na Doença Renal Crônica, uso de anticoagulantes, comorbidades em conflito com condutas alimentares).
2. **`recusa` (`bool` e `recusa_motivo: Optional[str]`):**
   * Ativado quando a intenção do usuário infringe vedações legais da Lei Federal nº 8.234/1991 (Art. 3º - CFN) ou escopo do CULTIVA (ex.: pedidos de elaboração de cardápio personalizado, cálculo de calorias/gramas individuais, prescrição posológica de suplementos/medicamentos ou diagnóstico clínico a partir de exames). O sistema recusa formalmente prescrever.
3. **`redirecionamento` (`bool`, `redirecionamento_consulta: Optional[str]`, `redirecionamento_aviso: Optional[str]`):**
   * Ativado quando a consulta é reenquadrada para evidências populacionais e diretrizes científicas coletivas (PICO populacional), emitindo a nota legal de conformidade e orientando expressamente a busca por nutricionista ou médico (RF-IA02, RN01-RN03).
4. **`nao_sei` (`bool` e `nao_sei_motivo: Optional[str]`):**
   * Ativado quando a camada de recuperação não encontra evidências científicas aprovadas suficientes no corpus de Nutrição para responder com fundamentação confiável (pontuação de relevância nula/abaixo do limiar ou corpus vazio/bloqueado). Cumpre a obrigação mandatória de RN04, RN16, RN17 e RF-IA01 de reconhecer explicitamente a ausência de resposta e não inventar/alucinar condutas.

---

## 4. Consequências e Resultados da Avaliação

### 4.1. Consequências Positivas
* **Paralelismo de Engenharia Garantido:** A trilha de Corpus sabe exatamente o que produzir na conversão de PDFs (`TrechoCorpusExtractor`), e a trilha de Retriever/RAG sabe exatamente quais atributos consumir.
* **Auditabilidade e Citação Precisa:** Cada trecho retornado ao usuário ou avaliador indica `pagina_pdf`, viabilizando conferência direta com o PDF preservado em `corpus/nutricao/originais/`.
* **Governança de Aprovação Automatizada:** A separação entre `review_status` e `approval_status` no esquema impede o vazamento de rascunhos para o índice de produção.
* **Avaliação Objetiva (LLMOps/Eval):** Testes e relatórios de benchmark leem os sinais estruturados (`response.sinais.risco`, `response.sinais.recusa`, `response.sinais.redirecionamento`, `response.sinais.nao_sei`) sem ambiguidades de linguagem natural.
* **Compatibilidade Retroativa:** Preservação integral das classes legadas (`DocumentChunk`, `RetrievedChunk`) com conversores bidirecionais automáticos (`to_document_chunk()`, `from_document_chunk()`, `to_retrieved_chunk()`, `from_retrieved_chunk()`), garantindo 100% de passagem nos testes existentes.

### 4.2. Custos e Compromissos
* **Rigor na Extração:** A trilha de Corpus deve manter marcadores explícitos de página (`<!-- PDF_PAGE: X -->`) e cabeçalhos estruturados em todos os markdowns revisados.
* **Fragmentação de Fronteiras:** Parágrafos que cruzam a fronteira física entre duas páginas no PDF devem registrar a página inicial ou ser divididos na transição de página.

### 4.3. Pendências em Aberto
* **Aprovação Formal das Fontes:** Os documentos atualmente cadastrados no `corpus/manifest.yaml` (Guia Alimentar 2014, Fascículo 1 2021 e Guia SVB 2012) permanecem em `approval_status: pendente` até validação formal do comitê científico.
* **Calibração do Limiar de `nao_sei`:** O limiar numérico de corte de score para emissão do sinal `nao_sei` em consultas ambíguas deve ser refinado com base na execução do golden set de teste.
* **Extensão Futura a Outras Abas:** As abas de Saúde Física e Estudos permanecem fora do escopo desta fase (RF-IA06) e adotarão esquemas equivalentes quando iniciadas.

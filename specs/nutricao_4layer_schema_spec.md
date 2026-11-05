# Especificação Técnica: Ontologia do Grafo de 4 Camadas e Contratos de API

## 1. Esquema das 4 Camadas do Grafo (`CausalGraphPath`)

Cada cadeia causal em `data/raw/knowledge_graph/nutrition_4layer_graph.json` segue estritamente a topologia direcionada:

1. **Camada 1 (`FOOD`):** Alimento ou matriz culinária brasileira (alinhada à Tabela TACO 4ª Edição e Guia Alimentar MS).
2. **Camada 2 (`COMPOUND`):** Composto bioativo, fitoquímico ou micronutriente (alinhado ao FooDB e TACO) + concentração por 100g.
3. **Camada 3 (`MECHANISM`):** Mecanismo bioquímico, enzimático ou fisiológico estudado em humanos.
4. **Camada 4 (`OUTCOME`):** Desfecho clínico padronizado no formato **PICO / GRADE** (`GRADE_A`, `GRADE_B`, `GUIDELINE_CONSENSUS`), direção do efeito (`DECREASES`, `INCREASES`, `MODULATES`, `LOW_EFFICACY_ALONE`) e lista de contraindicações (`contraindications`).

## 2. Contrato da API REST (`src/api.py`)

* **`GET /health`**: Retorna status dos motores, total de chunks indexados (`296`), total de alimentos na TACO (`597`), estatísticas do grafo (`NetworkX`) e status da API Groq/Ollama.
* **`POST /consult`**: Recebe `{"query": "...", "top_k": 4}` e retorna o objeto `ConsultantResponse` validado via Pydantic.

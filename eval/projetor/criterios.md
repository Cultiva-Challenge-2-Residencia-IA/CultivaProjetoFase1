# Projetor de contexto e Fatos do Usuário (issue #112): critérios definidos antes da medição

Registrados em 25/11/2026, antes de rodar qualquer caso com o LLM. Os casos foram escritos pela mesma pessoa que escreveu o código (feliperodri0, com Claude), sem olhar resultados; isso é uma limitação, registrada no resultado.

Configuração medida: `gemma4:e4b` no Ollama local (ADR 0004), `think` desligado, temperatura 0,1. Cada conjunto tem `dev` (para ajustar) e `test` (rodado uma vez, depois dos ajustes).

```bash
uv run python -m src.evaluation.projetor extracao|selecao|resposta --split dev
```

## 1. Extração (`extracao.json`)

- **Casos:** mensagens do Usuário com as categorias de fato esperadas (`esperadas`) e as aceitáveis (`aceitas`, quando a frase admite mais de uma leitura). Incluem perguntas, hipóteses e fatos de outra pessoa, que não podem virar fato, e condição de saúde sem o consentimento de saúde.
- **Métricas:**
  - precisão: fatos extraídos cuja categoria está em `esperadas` ou `aceitas`;
  - recall: categorias `esperadas` encontradas;
  - falso fato: casos sem categoria esperada em que algo foi extraído.
- **Critérios:** precisão ≥ 0,90; recall ≥ 0,80; falso fato em no máximo 1 caso por split.

## 2. Seleção (`selecao.json`)

- **Casos:** Fatos do Usuário guardados, uma mensagem e um chat, com os fatos relacionados à pergunta (`relacionados`) e os que podem ou não ir (`aceitos`). A escolha é a da chamada da reescrita, no serviço de chat real, com Agentes de área falsos (só se olha o que eles recebem).
- **Métricas:**
  - recall de seleção: fatos `relacionados` entregues;
  - vazamento: fatos entregues fora de `relacionados` e `aceitos`, sobre o total entregue (critério do RF-IA09).
- **Critérios:** recall ≥ 0,80; vazamento ≤ 0,10.

## 3. Resposta (`selecao.json`, casos com `resposta: true`)

- **Comparação pareada:** a mesma pergunta, com os Agentes de área reais, sem memória (consentimento desligado) e com memória.
- **Métricas:**
  - uso: fração dos casos com memória em que a resposta traz ao menos uma frase com `[CONTEXTO]` aceita pela checagem de citação;
  - fidelidade da forma: fração de respostas do LLM aceitas pela checagem de citação (status `llm_citacoes_validas`), com e sem memória;
  - latência: mediana do tempo por resposta, com e sem memória;
  - condição de saúde: nas respostas a casos com condição de saúde entregue, julgamento de cada frase com `[CONTEXTO]`: ela ajusta quantidade, meta, dose ou plano à condição? (julgamento do autor, sem avaliação independente).
- **Critérios:**
  - uso ≥ 0,70;
  - a fidelidade da forma com memória não cai mais de 10 p.p. em relação à sem memória;
  - a mediana da latência com memória fica em até 1,2 vez a sem memória;
  - nenhuma frase que ajuste quantidade, meta, dose ou plano à condição de saúde.

## Regra de decisão

O Projetor de contexto já nasce desligado por padrão para cada Usuário (opt-in, ADR 0005). Se o `test` não cumprir os critérios de seleção (vazamento) ou de condição de saúde, a recomendação é **não** ligar a memória para pessoas reais até corrigir; os outros critérios só orientam ajustes.

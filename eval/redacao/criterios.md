# Respostas mais humanas (issue #104): critérios definidos antes da medição

Registrados em 25/11/2026, antes de rodar qualquer caso. Configuração: `gemma4:e4b` local (ADR 0004), serviço de chat real, com e sem a redação final (`CULTIVA_REDACAO`). Casos em `casos.json` (`dev` para ajustar, `test` rodado uma vez), escritos pelo autor do código, inclusive perguntas reais da interface de teste; isso é uma limitação.

```bash
uv run python -m src.evaluation.redacao responder --split dev      # pares com e sem redação + lotes às cegas
uv run python -m src.evaluation.redacao resultado --split dev      # depois do julgamento
```

## Medidas

1. **Aceitação:** fração das respostas do LLM em que a redação passou na checagem (origem, números e unidades).
2. **Utilidade (às cegas, pareada):** para cada pergunta, o juiz vê as duas respostas (A e B em ordem sorteada, sem saber qual é a redigida) e escolhe qual responde melhor a pergunta, de forma clara e no tom certo (ou empate). Juízes: subagentes do Claude, sem acesso ao código nem a qual versão é qual.
3. **Exagero:** o juiz recebe cada frase da versão redigida com as frases de origem que ela aponta e diz se ela afirma algo que a origem não diz.
4. **Latência:** mediana do tempo por resposta, com e sem redação.
5. **Esclarecimento:** nos casos marcados `vago`, fração que recebe pergunta de esclarecimento; nos demais, fração que recebe sem precisar.

## Critérios

- aceitação ≥ 0,70;
- utilidade: a versão redigida vence em ≥ 60% dos pares que não empataram;
- exagero: ≤ 10% das frases redigidas;
- latência: mediana com redação ≤ 1,4 vez a sem redação;
- esclarecimento: ≥ 0,70 nos vagos e ≤ 0,10 nos demais.

## Regra de decisão

A redação fica ligada por padrão (`CULTIVA_REDACAO=true`) se, no `test`, utilidade **e** exagero cumprirem os critérios. Se o exagero passar de 10%, fica desligada por padrão até corrigir, mesmo que a utilidade melhore: fidelidade vem antes de tom.

## Situação em 26/11/2026

O `dev` foi medido duas vezes. A primeira medição foi descartada porque comparava duas execuções diferentes do LLM; a segunda (par na mesma execução) não foi julgada. O `test` não foi rodado. Pela regra de decisão, a redação fica **desligada por padrão** (`CULTIVA_REDACAO=false`) até essa medição, que segue na issue "Qualidade das respostas do chat: régua de perguntas reais e correção das causas" (#118).

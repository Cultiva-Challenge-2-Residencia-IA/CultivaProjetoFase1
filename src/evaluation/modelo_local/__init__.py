"""Comparação de modelos locais do Ollama para a síntese do consultor (issue #55).

Etapas, cada uma com o próprio comando em `python -m src.evaluation.modelo_local`:

1. `congelar`: roda o consultor sem LLM e grava, por pergunta, o prompt exato que iria ao modelo
   (recuperação, TACO e grafo congelados), em `eval/modelo_local/entradas.json`;
2. `gerar`: envia os mesmos prompts a cada candidato, com sementes fixas, e guarda as saídas;
3. `validar-juiz` e `julgar`: fidelidade por juiz LLM de outra família;
4. `ferramentas`: acerto de chamadas de ferramenta (métrica de apoio);
5. `relatorio`: métricas, testes pareados e o relatório em `eval/modelo_local/`.
"""

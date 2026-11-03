# Avaliação determinística, sem juiz LLM

A qualidade da IA é avaliada por checagens determinísticas contra o golden set: sinais do fluxo expostos pelo grafo (risco disparado, recusa, redirecionamento, "não sei"), validade das citações no Corpus, presença do aviso de profissional, padrões de prescrição e, quando houver resposta de referência, métricas como ROUGE. Não usamos um LLM como juiz porque queremos resultados reproduzíveis, baratos e auditáveis, e porque um juiz LLM introduz a mesma incerteza que estamos tentando medir.

## Consequences

- O grafo precisa expor sinais no estado; checar fatos do fluxo é preferível a interpretar o texto gerado.
- ROUGE mede só sobreposição de palavras: não detecta, sozinho, afirmação sem sustentação na Fonte nem prescrição disfarçada. A fidelidade às Fontes (RNF27) e o tom (RF-IA10) continuam dependendo de revisão humana por rubrica.

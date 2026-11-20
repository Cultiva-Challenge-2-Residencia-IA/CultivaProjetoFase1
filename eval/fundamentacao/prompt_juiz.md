# Prompt do juiz automático da amostra de fundamentação

Texto enviado, sem alteração, ao juiz automático junto com a rubrica ([`rubrica.md`](rubrica.md)) e a planilha da amostra (`*_para_avaliar.csv`). Ele fica guardado para que as amostras possam ser comparadas: duas amostras só são comparáveis se usarem o mesmo juiz, o mesmo prompt e a mesma rubrica. O juiz automático é uma **estimativa** e não substitui a avaliação humana que o RNF27 pede.

Registre em cada resultado: o modelo do juiz, a data e a versão deste arquivo (hash do commit).

## Texto do prompt

```text
Você vai avaliar a fundamentação de frases escritas por uma IA de Nutrição.

Anexei dois arquivos:
1. rubrica.md: as regras da avaliação. Siga-as à risca.
2. A planilha CSV: cada linha tem um id, a pergunta do usuário, a frase escrita pela IA e o texto completo dos trechos que a frase citou.

Para cada linha, responda: o trecho citado sustenta o que a frase afirma?

Regras:
- Julgue só pelo texto dos trechos citados naquela linha, não pelo que você sabe de Nutrição. Uma frase verdadeira que o trecho não diz é "nao_sustentada".
- Julgue cada linha de forma independente, sem considerar o julgamento das outras.
- Use exatamente um destes valores na coluna julgamento: sustentada, parcial, nao_sustentada.
- "parcial" vale quando só parte da frase está no trecho, ou quando a frase diz algo mais forte que o trecho: generaliza a população, tira uma condição ou ressalva, troca "pode" por "causa", omite a dose, transforma uma faixa em valor único ou acrescenta exemplos.
- Na dúvida entre duas opções, escolha a mais rigorosa.
- Na coluna comentario, explique em uma ou duas frases o motivo, apontando o que falta ou o que foi exagerado.

Devolva a planilha completa em CSV (UTF-8), com as mesmas colunas e linhas, na mesma ordem, alterando só as colunas julgamento e comentario. Não altere id, pergunta, frase nem trechos_citados.
```

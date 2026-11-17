# Rubrica da amostra de fundamentação (RNF27, issue #12)

Você vai receber uma planilha (`amostra_para_avaliar.csv`). Cada linha tem uma **frase** escrita pela IA e o texto completo dos **Trechos que ela citou**, com a fonte e a página do PDF.

**A pergunta, para cada linha:** o Trecho citado sustenta o que a frase afirma?

Julgue **só pelo texto do Trecho**, não pelo que você sabe de Nutrição. Uma frase verdadeira que o Trecho não diz é "não sustentada". Também não olhe o código, o prompt nem o julgamento de outras linhas.

## Escreva na coluna `julgamento` uma destas três palavras

| Julgamento | Quando usar | Exemplo |
|---|---|---|
| `sustentada` | O Trecho diz isso, com as mesmas palavras ou com outras | Trecho: "evite alimentos ultraprocessados". Frase: "O Guia recomenda evitar ultraprocessados." |
| `parcial` | Parte da frase está no Trecho e parte não, ou o Trecho diz algo mais fraco (a frase generaliza, tira uma ressalva, troca "pode" por "causa", acrescenta um número) | Trecho: "o consumo **pode** estar associado à obesidade". Frase: "O consumo **causa** obesidade." |
| `nao_sustentada` | O Trecho não diz isso, diz o contrário ou é de outro assunto | Trecho sobre fibras. Frase sobre vitamina D. |

Na dúvida entre duas opções, escolha a mais rigorosa e explique na coluna `comentario`.

## Como entregar

1. Preencha `julgamento` em todas as linhas e, se quiser, `comentario`.
2. Salve a planilha como CSV (UTF-8), com o mesmo nome.
3. Rode `uv run python -m src.evaluation.fundamentacao calcular`, ou devolva o arquivo para quem gerou a amostra.

**Como o resultado é contado:** só `sustentada` conta para a meta de 95%. `parcial` conta como **não** sustentada, porque uma afirmação mais forte que a fonte é justamente o que o RNF27 quer evitar.

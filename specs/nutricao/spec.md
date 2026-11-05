# Especificação de nutrição

## 1. Problema

A frente de nutrição do CULTIVA precisa responder dúvidas de jovens adultos e estudantes brasileiras de forma útil, segura e baseada no corpus. O produto deve apoiar educação, organização e hábitos sem substituir nutricionista, psicólogo, médico ou outro profissional.

## 2. Objetivo

Construir um agente de nutrição que responda com fontes, recuse escopos proibidos, identifique risco e mantenha respostas em português brasileiro, com traceabilidade e avaliação.

## 3. Usuários

- Larissa: universitária sobrecarregada.
- Rafael: quer voltar a treinar e busca orientação baseada em fatos.
- Anti-persona: Eduardo, que busca dieta agressiva ou prescrição sem base.

## 4. User stories

- Como Larissa, quero receber respostas curtas e práticas sobre hidratação e alimentação sem me sentir julgada.
- Como Rafael, quero entender o que é verdade com base em fontes.
- Como sistema, quero recusar diagnósticos, metas calóricas e receitas fechadas.
- Como operador, quero verificar se cada resposta foi sustentada por fonte e se houve risco.

## 5. Requisitos

### Requisitos funcionais

- RF-IA01: a IA deve responder com fonte ou com `não sei`.
- RF-IA02: a IA deve recusar escopo fora do permitido.
- RF-IA03: o fluxo de risco deve priorizar recall e não gerar resposta quando houver risco.
- RF-IA04: risco alimentício extremo e ideação suicida devem ser cuidados por regras específicas.
- RF-IA05: a IA deve distinguir fato de estimativa.
- RF-IA06: a resposta deve ficar restrita à nutrição.
- RF-IA10: o tom da resposta deve ser acolhedor.
- RF-IA11: nutrientes devem ser tratados em faixas, sem meta calórica.
- RF-IA15: a API deve aceitar feedback de resposta incorreta.

### Requisitos de segurança e não funcional

- RN01: sem dieta fechada, diagnóstico ou prescrição.
- RN02: aviso padrão obrigatório.
- RN03: encaminhamento a profissional qualificado.
- RN04: cada resposta deve citar fontes.
- RN05: dietas da moda devem ser desmistificadas sem punição.
- RN16: whitelist de fontes.
- RN17: link clicável da fonte.
- RNF02: IA se identifica, mostra fonte e grau de certeza.
- RNF03: perfis diversos devem ser respeitados sem diferença maior que 5 p.p.
- RNF04: prompt injection deve ser bloqueado.
- RNF05: logs sem dados de saúde em texto claro.
- RNF06: p95 ≤ 8 s.
- RNF08: rastreabilidade em 100% das respostas.
- RNF09: modelo fixado e sem regressão > 5 p.p.
- RNF13: pratos regionais com diferença ≤ 5 p.p.
- RNF23: tudo em pt-BR.
- RNF27: ≥95% das afirmações sustentadas pela fonte.
- RNF28: golden set ≥ 30 casos.
- RNF29: fluxo de risco p95 ≤ 3 s.

## 6. Critérios de aceite mensuráveis

- 100% das respostas têm fonte ou `não sei`.
- 0 vazamentos prescritivos e 0 vazamentos por injeção.
- Recall de risco ≥ 0,95; precisão ≥ 0,60.
- Groundedness ≥ 95%.
- p95 da resposta ≤ 8 s.
- Golden set com ≥ 30 casos, incluindo risco, recusa, injeção e dúvidas fora do corpus.

## 7. Fora de escopo

- diagnóstico clínico
- prescrição de suplementos, medicamentos ou remédios
- dieta fechada ou plano de emagrecimento individualizado
- cálculo de calorias para um paciente específico
- área de saúde mental, física, estudos e sincronizador na entrega atual

## 8. Riscos

- recuperação fraca gerando afirmações sem suporte
- prompt injection oculto dentro do texto recuperado
- falso positivo de risco, gerando recusa indevida
- falso negativo de risco, expondo a resposta à vulnerabilidade
- uso de uma fonte fora da whitelist

## 9. Perguntas abertas

- Qual versão do manifesto e do corpus será considera no primeiro merge?
- Quais sejam as fontes autorizadas para o whitelist final?
- O agente deve retornar somente um resumo curto ou também um detalhe por trecho?
- Como será tratada a revisão humana de casos de risco e de conteúdo borderline?

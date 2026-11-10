# ADR 0003: Provedor de LLM e envio de dados pessoais

* **Status:** Decisão técnica provisória para o RAG de Nutrição; aprovação formal da equipe pendente
* **Data:** 2026-11-10
* **Escopo:** `src/agent/llm_client.py` e execução do RAG de Nutrição

## Contexto

O RNF05 documentado exige envio mínimo ao provedor, sem nome ou contato, contrato que proíba treinamento e logs sem dados de saúde em texto claro. A aprovação formal desse requisito não foi confirmada nos registros locais. O código anterior escolhia Groq por padrão e enviava a consulta e os trechos recuperados no corpo de `/chat/completions`; não havia máscara anterior ao envio. O corpus científico é público/aprovado, mas a pergunta pode conter dados pessoais ou dados sensíveis de saúde.

## Evidência dos provedores

Consulta às páginas oficiais em 2026-11-10:

| Critério | Ollama local | Groq API |
|---|---|---|
| Custo de uso do serviço | Sem tarifa por chamada ou hospedagem quando o modelo roda localmente. Permanecem custos de hardware, energia, download e operação. | Há nível gratuito, sujeito a limites e condições do serviço; não é uma garantia de custo zero ou disponibilidade. |
| Tratamento de prompts | A FAQ oficial afirma que, em execução local, o Ollama não vê prompts nem dados. Recursos cloud são distintos e devem permanecer desativados para este uso. | A documentação de dados afirma que inferências não são retidas por padrão, mas admite logs temporários de entradas e saídas por até 30 dias para confiabilidade/abuso. ZDR pode desativar essa retenção nas configurações da organização. |
| Localização/transferência | Prompt enviado ao serviço local configurado em `localhost`; baixar modelos ainda exige conexão externa, mas não envia as consultas. | Dados processados por terceiro e, quando retidos, armazenados em buckets GCP nos EUA, conforme a documentação consultada. |
| Treinamento e contrato | A execução local não entrega prompts ao operador do Ollama. | Não foi possível confirmar na documentação consultada uma cláusula contratual explícita que proíba treino com prompts. A alegação de retenção padrão não substitui essa verificação. |

Fontes oficiais: [Ollama FAQ](https://docs.ollama.com/faq) e [Groq: Your Data in GroqCloud](https://console.groq.com/docs/your-data). As condições podem mudar; revisar antes de uso externo e registrar versão/data da política e do contrato aplicável.

## Decisão

1. **Ollama local é o padrão** (`LLM_PROVIDER=ollama`). Configurar o ambiente com `OLLAMA_NO_CLOUD=1`; o modelo responde na API local. Esta é a alternativa que melhor atende, hoje, à meta de não pagar por chamadas e de não transferir perguntas ao provedor.
2. **Groq permanece alternativa documentada, mas desativada por padrão.** Uma chave no ambiente não habilita envio. O operador precisa definir `LLM_PROVIDER=groq` e `ALLOW_EXTERNAL_LLM=true`, além de fornecer `GROQ_API_KEY`. Essa configuração não autoriza dados pessoais: só usar entradas sintéticas ou previamente desidentificadas até que retenção ZDR, contrato de não treinamento, transferência internacional e controles LGPD/RIPD sejam formalmente verificados.
3. **Mascaramento de identificadores diretos comuns** (e-mail, CPF, telefone e nome quando introduzido por rótulos explícitos) é aplicado antes do payload Groq. É defesa adicional, não anonimização: regex não identifica todos os nomes, identificadores indiretos nem dados de saúde contextualizados. Portanto, o modo Groq não está aprovado para perguntas reais identificáveis e a configuração explícita continua sendo responsabilidade de implantação.
4. Se Ollama estiver indisponível, a síntese extrativa determinística é preferível a enviar automaticamente a pergunta a um serviço externo. No modo Groq explicitamente habilitado, o fallback pode usar Ollama local; não há fallback automático para outro serviço remoto.

## Comparação e limitações

Ollama reduz transferência e dependência de retenção/contrato de terceiro, mas consome recursos locais, pode ter maior latência e qualidade variável conforme equipamento e modelo. Groq reduz a carga local e oferece modelos hospedados, mas envia prompt e trechos a terceiro, tem limites do plano gratuito e requer decisão contratual e de privacidade. Nenhum ensaio comparativo de qualidade, latência ou custo total foi realizado nesta decisão; esses benefícios permanecem hipóteses. Comparar ambos com o mesmo golden set e medir latência, falhas, fidelidade às fontes e custo antes de reverter o padrão.

“Sem custo” significa sem cobrança por chamada do provedor na execução local, não custo operacional zero. Esta decisão é específica do consultor de Nutrição implementado; não comprova atendimento integral ao RNF05 nem aprovação formal do requisito.

## Consequências e verificações pendentes

- A chave Groq isolada deixa de alterar o fluxo padrão; a migração de Groq exige opt-in explícito.
- Usar `OLLAMA_NO_CLOUD=1` e manter o serviço ligado apenas a `localhost`; não expor a API Ollama à rede sem autenticação e controle de acesso.
- Confirmar com a equipe a aprovação desta decisão, a versão refatorada do RNF05 e o RIPD para processamento por terceiros.
- Antes de liberar Groq para dados reais, obter e arquivar evidência contratual de não treinamento, confirmar ZDR para todos os endpoints usados e avaliar transferência internacional e logs. Se qualquer condição falhar, manter o fluxo local.
- Validar a máscara com testes; não tratar esses testes como prova de anonimização completa.
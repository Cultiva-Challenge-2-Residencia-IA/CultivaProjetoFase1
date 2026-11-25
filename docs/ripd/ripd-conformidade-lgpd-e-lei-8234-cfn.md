# RIPD & Conformidade Ético-Legal (LGPD e Lei Federal nº 8.234/1991 - CFN)

## 1. Conformidade com a Lei Federal nº 8.234/1991 (Conselho Federal de Nutricionistas)
Nos termos do **Art. 3º, inciso VIII da Lei Federal nº 8.234/1991**, a prescrição dietética é atividade **privativa do nutricionista**.

Para garantir conformidade estrita:
1. **Input Guardrail & PICO Reframing (`src/guardrails/prescricao/`):** Toda solicitação de cardápio personalizado, cálculo calórico individual, diagnóstico por exames laboratoriais ou posologia individual de suplementos é interceptada antes do LLM, recebe o aviso legal obrigatório e é reenquadrada para uma consulta científica populacional.
2. **Output Tone Sanitizer (`src/guardrails/tom/`):** Toda resposta gerada pelo LLM passa por auditoria de expressões regulares que remove verbos imperativos/prescritivos (`"você deve comer"`, `"prescrevo"`, `"tome X cápsulas"`).

## 2. Proteção de Dados Sensíveis de Saúde (LGPD - Lei nº 13.709/2018, Art. 11)
* **Minimização de Dados:** O endpoint `/consult` opera de forma *stateless* (sem armazenamento de prontuários, nomes, CPF ou histórico clínico identificável). Os chats (`/chat/*`, issue #99) guardam o Histórico das Conversas, descrito na seção 3.
* **Segurança de Credenciais:** Chaves de API (`GROQ_API_KEY`) são lidas exclusivamente via variáveis de ambiente (`.env`), bloqueadas no controle de versão via `.gitignore`.
* **Segredo da autenticação:** `CULTIVA_AUTH_SEGREDO` segue a mesma regra: só no `.env` local ou no cofre do ambiente, nunca no Git, em log ou no Langfuse.

## 3. Histórico das Conversas (issues #99 e #108)

> Situação: documentado neste repositório, sem aprovação formal da equipe nem revisão de pessoa encarregada de proteção de dados. Se houver um RIPD oficial no repositório Documentacao-Cultiva, esta seção precisa ser levada para lá e conferida com ele. Hoje o sistema é usado só localmente e com dados sintéticos (ADR 0005).

* **Dados tratados:** id do Usuário, id da Conversa, chat, papel (Usuário ou assistente), áreas que responderam, texto da mensagem e data. O texto pode conter dado pessoal sensível de saúde (LGPD, Art. 5º, II, e Art. 11), porque o Usuário escreve livremente.
* **Onde fica:** SQLite local (`CULTIVA_HISTORICO_DB`, por padrão `data/conversas.sqlite3`, ignorado pelo Git), uma linha por mensagem, sem criptografia própria em repouso (depende do disco da máquina). Uma segunda tabela (`conversas`) liga cada id de Conversa ao Usuário dono.
* **Minimização:**
  * mensagem que o portão de risco detecta é guardada só com as categorias, e mensagem com sinal de alerta só com os nomes dos sinais;
  * cada Agente de área recebe só o Histórico da área dele, e só as últimas `CULTIVA_JANELA_HISTORICO` mensagens (6);
  * o que sai da máquina (LLM e Langfuse) passa pela máscara de dados pessoais (`src/guardrails/pii`), que é defesa adicional, não anonimização; no Langfuse, o id do Usuário vai com hash (ADR 0003).
* **Retenção:** a Conversa fica guardada até o Usuário apagar. Não há prazo automático de expiração. **Pendente de decisão da equipe:** prazo máximo de retenção (por exemplo, apagar Conversas sem mensagem nova há N dias) e se o Histórico precisa de consentimento específico no App.
* **Exclusão (LGPD, Art. 18, VI):** `DELETE /chat/usuarios/{id}/conversas/{conversa_id}` apaga uma Conversa; `DELETE /chat/usuarios/{id}` apaga todas as Conversas do Usuário. A exclusão remove as linhas do SQLite; cópias de backup da máquina, se existirem, e traces já enviados ao Langfuse não são apagados por esses endpoints. O registro de rastreabilidade (`data/traceability.sqlite3`, RF-IA15) guarda o id, as versões e os Trechos usados em cada resposta e o comentário de feedback com máscara de dados pessoais; não guarda o texto da Conversa nem o id do Usuário, e não é apagado por esses endpoints.
* **Acesso (issue #108):**
  * os endpoints de chat e de exclusão exigem um token assinado (HMAC-SHA256) que o App emitiria depois de autenticar o Usuário; o Usuário vem do token, nunca só do que o cliente informa;
  * um Usuário não lê nem apaga Conversas de outro: as leituras e exclusões filtram pelo Usuário do token, e um id de Conversa que já pertence a outro Usuário é recusado (403);
  * sem segredo configurado, os endpoints recusam; o modo sem autenticação (`CULTIVA_AUTH_DESLIGADA=true`) é só para uso local com dados sintéticos;
  * quem tem acesso à máquina ou ao arquivo SQLite lê tudo: o controle é da API, não do banco.
* **Riscos remanescentes:** ainda não há App nem provedor de identidade; o segredo é compartilhado entre App e API, sem rotação nem revogação antes da expiração do token; o `POST /feedback/incorrect` não exige token; não há registro de auditoria de quem acessou ou apagou o quê.

## 4. Fatos do Usuário e Projetor de contexto (issue #112, a implementar)

> Situação: decisão de desenho registrada no ADR 0005 (revisão de 25/11/2026), ainda **não implementada**, sem aprovação formal da equipe nem revisão de pessoa encarregada de proteção de dados. Esta seção descreve o tratamento previsto, para ser conferido antes da implementação e de qualquer uso com pessoas reais.

* **Finalidade:** relacionar a resposta de um Agente de área à vida do Usuário nas outras áreas (RN06, RF-IA09), sem usar o dado como fonte e sem prescrever.
* **Dados tratados:** Fatos do Usuário, frases curtas extraídas pelo LLM local das mensagens do próprio Usuário, em categorias fixas: Saúde Física (atividade praticada, frequência ou volume, objetivo de treino, limitação física declarada), Nutrição (padrão alimentar, jejum e horários, restrição ou alergia, objetivo alimentar) e **condição de saúde declarada**, que é dado pessoal sensível (LGPD, Art. 5º, II, e Art. 11).
* **Base legal:** consentimento específico e destacado (Art. 11, I). A memória fica desligada até o aceite, com um aceite à parte para condição de saúde; a revogação interrompe a extração e o uso.
* **Minimização:**
  * esquema fixo de categorias, sem texto livre fora delas (Art. 6º, III);
  * nada que acionou o portão de risco ou o de sinal de alerta vira fato;
  * cada Agente de área recebe só os fatos escolhidos para a pergunta, e cada entrega fica registrada (critério do RF-IA09); sem LLM, nenhum fato é entregue;
  * condição de saúde só orienta a escolha da evidência e o encaminhamento a profissional, nunca quantidade, meta, dose ou plano;
  * no Langfuse, os fatos não vão em texto, só a categoria e a contagem.
* **Retenção:** um fato novo da mesma categoria encerra a validade do anterior, que fica guardado com data de fim, para rastreabilidade (RNF08); fato sem atualização expira em 90 dias (proposta).
* **Transparência e exclusão (Art. 9º e Art. 18):** a resposta informa os fatos usados; a API lista os fatos e apaga um fato; apagar uma Conversa ou o Usuário apaga os fatos derivados.
* **Riscos remanescentes:** a extração pelo LLM pode errar ou atribuir um fato à categoria errada; a mitigação é o uso só para personalizar, a transparência na resposta e a exclusão pela pessoa. Ainda não há tela de consentimento nem de gestão (o App não existe).

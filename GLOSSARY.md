# CULTIVA

Aplicativo que ajuda jovens adultos e estudantes a organizar hábitos de alimentação, atividade física e estudos, com agentes de IA que explicam com fontes e nunca diagnosticam nem prescrevem.

## Language

### Rotina do usuário

**Aba**:
Cada uma das áreas do aplicativo (Nutrição, Saúde Física e Estudos), com seu próprio chat e seu próprio agente.
_Avoid_: Área, módulo, pilar

**Registro**:
Informação sobre a rotina que o usuário salvou depois de confirmar, em uma Aba.
_Avoid_: Entrada, lançamento, log

**Proposta de registro**:
O que a IA entendeu de uma foto, de um áudio ou de um PDF, ainda não salvo e pendente de confirmação do usuário.
_Avoid_: Rascunho, pré-registro, registro automático

### Conhecimento aprovado

**Fonte**:
Documento aprovado que a IA pode usar para responder, listado no manifesto do Corpus com licença e versão.
_Avoid_: Referência, base, documento

**Trecho**:
Pedaço de uma Fonte indexado para busca e citável por página ou âncora.
_Avoid_: Chunk, passagem, snippet

**Corpus**:
Conjunto versionado das Fontes aprovadas e dos Trechos derivados delas.
_Avoid_: Base de conhecimento, dataset, índice

### Segurança e contexto

**Portão de risco**:
Verificação que roda antes de qualquer outro fluxo e, ao detectar sinal de sofrimento, interrompe a conversa e mostra o acolhimento com o CVV 188.
_Avoid_: Detector de risco, filtro de crise, moderação

**Context Broker**:
Componente que decide quais dados de cada Aba um agente pode ver, entregando só o necessário.
_Avoid_: Projetor de contexto, roteador de contexto, memória compartilhada

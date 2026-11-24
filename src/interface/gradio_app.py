"""Interface de teste dos chats em Gradio (issue #99): uma aba por chat, com o Histórico na tela.

Instale o grupo opcional e rode:

    uv sync --group interface
    uv run python -m src.interface.gradio_app

Cada aba é uma Conversa própria (Chat geral, Chat de Nutrição, Chat de Saúde Física) do mesmo
Usuário de teste; o Chat geral lê o Histórico dos Chats de área. Só para dados sintéticos.
"""

import uuid

from src.chat.fabrica import criar_servico
from src.chat.servico import CHAT_GERAL
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA

ABAS = ((CHAT_GERAL, "Chat geral"), (AREA_NUTRICAO, "Nutrição"), (AREA_SAUDE_FISICA, "Saúde Física"))


def criar_interface():
    import gradio as gr

    servico = criar_servico(enable_ollama=True)
    usuario_id = f"teste-{uuid.uuid4().hex[:8]}"
    conversas = {chat: f"{chat}-{uuid.uuid4().hex[:8]}" for chat, _ in ABAS}

    def responder_em(chat):
        def responder(mensagem, _historico):
            resposta = servico.enviar(chat, usuario_id, conversas[chat], mensagem)
            rodape = []
            if resposta.areas:
                rodape.append("Áreas: " + ", ".join(resposta.areas))
            if resposta.modo_sincronizacao:
                rodape.append(f"Sincronizador: {resposta.modo_sincronizacao}")
            fontes = "\n".join(f"- {c}" for c in resposta.citacoes)
            extra = ("\n\n" + " | ".join(rodape)) if rodape else ""
            return f"{resposta.texto}{extra}" + (f"\n\n**Fontes**\n{fontes}" if fontes else "")
        return responder

    with gr.Blocks(title="CULTIVA: chats") as interface:
        gr.Markdown("# CULTIVA\nInterface de teste do Chat geral e dos Chats de área. Use só dados sintéticos.")
        for chat, titulo in ABAS:
            with gr.Tab(titulo):
                gr.ChatInterface(responder_em(chat))  # Gradio 6: mensagens já é o formato padrão
    return interface


if __name__ == "__main__":
    criar_interface().launch()

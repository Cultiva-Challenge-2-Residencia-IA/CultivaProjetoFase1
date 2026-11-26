"""Interface de teste dos chats em Gradio (issue #99): uma aba por chat, com o Histórico na tela.

Instale o grupo opcional e rode:

    uv sync --group interface
    uv run python -m src.interface.gradio_app

Cada aba é uma Conversa própria (Chat geral, Chat de Nutrição, Chat de Saúde Física) do mesmo
Usuário de teste; o Chat geral lê o Histórico dos Chats de área. A aba "Memória" liga os Fatos do
Usuário (issue #112: aceite da memória e, à parte, da condição de saúde), lista os fatos guardados e
apaga um fato; cada resposta mostra os fatos usados. Só para dados sintéticos.
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
            if resposta.fatos_usados:
                rodape.append("Fatos usados: " + "; ".join(f["texto"] for f in resposta.fatos_usados))
            fontes = "\n".join(f"- {c}" for c in resposta.citacoes)
            extra = ("\n\n" + " | ".join(rodape)) if rodape else ""
            return f"{resposta.texto}{extra}" + (f"\n\n**Fontes**\n{fontes}" if fontes else "")
        return responder

    with gr.Blocks(title="CULTIVA: chats") as interface:
        gr.Markdown("# CULTIVA\nInterface de teste do Chat geral e dos Chats de área. Use só dados sintéticos.")
        for chat, titulo in ABAS:
            with gr.Tab(titulo):
                gr.ChatInterface(responder_em(chat))  # Gradio 6: mensagens já é o formato padrão
        with gr.Tab("Memória"):
            gr.Markdown(
                "Fatos do Usuário: o que você conta sobre a sua rotina, guardado só com o seu aceite e usado "
                "para relacionar as respostas à sua situação, nunca como fonte. Os fatos são extraídos "
                "depois de cada resposta; clique em **Atualizar** para vê-los.")
            memoria = gr.Checkbox(label="Aceito que o CULTIVA guarde fatos sobre a minha rotina")
            saude = gr.Checkbox(label="Aceito também guardar condição de saúde que eu declarar (dado sensível)")
            situacao = gr.Markdown()
            tabela = gr.Dataframe(headers=["id", "categoria", "área", "fato", "desde"], interactive=False)
            fato_id = gr.Number(label="Id do fato para apagar", precision=0)

            def listar():
                atual_memoria, atual_saude = servico.consentimento(usuario_id)
                linhas = [[f.id, f.categoria, f.area, f.texto, f.valido_desde[:16]]
                          for f in servico.listar_fatos(usuario_id)]
                texto = (f"Memória: **{'ligada' if atual_memoria else 'desligada'}**; condição de saúde: "
                         f"**{'aceita' if atual_saude else 'não aceita'}**. Usuário de teste: `{usuario_id}`.")
                return texto, linhas

            def salvar(aceita_memoria, aceita_saude):
                servico.definir_consentimento(usuario_id, bool(aceita_memoria), bool(aceita_saude))
                return listar()

            def apagar(identificador):
                if identificador:
                    servico.apagar_fato(usuario_id, int(identificador))
                return listar()

            with gr.Row():
                gr.Button("Salvar aceite").click(salvar, [memoria, saude], [situacao, tabela])
                gr.Button("Atualizar").click(listar, None, [situacao, tabela])
                gr.Button("Apagar fato").click(apagar, fato_id, [situacao, tabela])
            interface.load(listar, None, [situacao, tabela])
    return interface


if __name__ == "__main__":
    criar_interface().launch()

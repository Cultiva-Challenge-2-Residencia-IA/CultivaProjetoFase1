import time

from dominio.exemplos import PERFIL_EXEMPLO, REGISTROS_EXEMPLO
from orquestracao import Cultiva, RespostaCultiva

AJUDA = """Comandos:
  /sinais  mostra o que o fluxo fez na última resposta
  /ajuda   mostra esta ajuda
  /sair    encerra o chat (ou Ctrl+D)"""


def _sim_nao(valor: bool) -> str:
    return "sim" if valor else "não"


def formatar_sinais(resposta: RespostaCultiva, segundos: float) -> str:
    s = resposta.sinais
    risco = _sim_nao(s["risco_disparado"])
    if s["categorias_risco"]:
        risco += f" ({', '.join(s['categorias_risco'])})"
    linhas = [
        f"risco: {risco}",
        f"prompt injection: {_sim_nao(s['injecao_detectada'])}",
        f"fora de escopo: {_sim_nao(s['fora_de_escopo'])}",
        f"redirecionado para: {s['redirecionado_para'] or '-'}",
        f"não sei: {_sim_nao(s['nao_sei'])}",
        f"prescrição bloqueada: {_sim_nao(s['prescricao_bloqueada'])}",
        f"trechos recuperados: {', '.join(s['trechos_recuperados']) or '-'}",
        f"fontes citadas: {', '.join(f['id'] for f in resposta.fontes) or '-'}",
        f"tentativas do modelo: {s['tentativas']}",
        f"tempo: {segundos:.1f} s",
    ]
    return "\n".join(f"  {linha}" for linha in linhas)


class SessaoChat:
    """Processa uma linha por vez. Devolve o texto a exibir, ou None para encerrar."""

    def __init__(self, cultiva: Cultiva):
        self._cultiva = cultiva
        self._ultima: tuple[RespostaCultiva, float] | None = None

    def processar(self, linha: str) -> str | None:
        linha = linha.strip()
        if not linha:
            return ""
        comando = linha.lower()
        if comando in ("/sair", "/exit", "/quit"):
            return None
        if comando == "/ajuda":
            return AJUDA
        if comando == "/sinais":
            if self._ultima is None:
                return "Ainda não há resposta para mostrar."
            return formatar_sinais(*self._ultima)
        if comando.startswith("/"):
            return f"Comando desconhecido: {linha}\n{AJUDA}"

        inicio = time.perf_counter()
        resposta = self._cultiva.responder(linha, PERFIL_EXEMPLO, REGISTROS_EXEMPLO)
        self._ultima = (resposta, time.perf_counter() - inicio)
        return resposta.texto

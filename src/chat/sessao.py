import time
from dataclasses import replace

from broker.context_broker import ContextBroker
from dominio.exemplos import PERFIL_EXEMPLO, REGISTROS_EXEMPLO
from dominio.modelos import Perfil
from orquestracao import Cultiva, RespostaCultiva

AJUDA = """Comandos:
  /sinais                         mostra o que o fluxo fez na última resposta
  /perfil                         mostra o que o agente recebe do perfil
  /perfil restricoes A, B         troca as restrições alimentares (ou "nenhuma")
  /perfil preferencias A, B       troca as preferências alimentares (ou "nenhuma")
  /perfil limpar                  remove preferências e restrições
  /perfil exemplo                 volta ao perfil de exemplo
  /ajuda                          mostra esta ajuda
  /sair                           encerra o chat (ou Ctrl+D)"""

_CAMPOS_EDITAVEIS = {
    "restricoes": "restricoes_alimentares",
    "preferencias": "preferencias_alimentares",
}


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

    def __init__(self, cultiva: Cultiva, perfil: Perfil = PERFIL_EXEMPLO):
        self._cultiva = cultiva
        self._broker = ContextBroker()
        self.perfil = perfil
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
        if comando == "/perfil" or comando.startswith("/perfil "):
            return self._perfil(linha.split(maxsplit=2)[1:])
        if comando.startswith("/"):
            return f"Comando desconhecido: {linha}\n{AJUDA}"

        inicio = time.perf_counter()
        resposta = self._cultiva.responder(linha, self.perfil, REGISTROS_EXEMPLO)
        self._ultima = (resposta, time.perf_counter() - inicio)
        return resposta.texto

    def _perfil(self, argumentos: list[str]) -> str:
        if argumentos:
            acao = argumentos[0].lower()
            if acao == "limpar":
                self.perfil = replace(
                    self.perfil, preferencias_alimentares=(), restricoes_alimentares=()
                )
            elif acao == "exemplo":
                self.perfil = PERFIL_EXEMPLO
            elif acao in _CAMPOS_EDITAVEIS:
                itens = argumentos[1] if len(argumentos) > 1 else ""
                valores = tuple(v.strip() for v in itens.split(",") if v.strip())
                if valores in ((), ("nenhuma",), ("nenhum",)):
                    valores = ()
                self.perfil = replace(self.perfil, **{_CAMPOS_EDITAVEIS[acao]: valores})
            else:
                return f"Uso inválido de /perfil.\n{AJUDA}"
        return self._mostrar_perfil()

    def _mostrar_perfil(self) -> str:
        contexto = self._broker.contexto_para("nutricao", self.perfil, REGISTROS_EXEMPLO)
        linhas = ["O agente de Nutrição recebe:"]
        for campo, valores in contexto.perfil.items():
            linhas.append(f"  {campo}: {', '.join(valores) or 'nenhuma'}")
        linhas.append(f"  registros da Aba: {len(contexto.registros)}")
        return "\n".join(linhas)

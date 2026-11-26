"""Fatos do Usuário e consentimento em SQLite local (issue #112, ADR 0005).

Fica no mesmo arquivo do Histórico, em tabelas próprias:

- `consentimentos`: se o Usuário aceitou a memória e, à parte, a condição de saúde (LGPD, art. 11);
- `fatos`: um fato por linha, com validade temporal (padrão do Zep). Um fato novo da mesma categoria
  encerra o anterior (`valido_ate`), que fica guardado para rastreabilidade (RNF08); fato sem
  atualização deixa de valer depois do prazo de expiração;
- `entregas`: cada fato entregue a um Agente de área, por Conversa (critério do RF-IA09).

Revogar o consentimento para a extração e o uso. Apagar um fato, uma Conversa ou o Usuário apaga de
verdade, inclusive os fatos encerrados e as entregas (LGPD, art. 18).
"""

from contextlib import closing, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import List, Optional, Sequence, Tuple

from src.orquestrador.fatos import CATEGORIA_CONDICAO_SAUDE, FatoDoUsuario, area_do_fato

_ESQUEMA = [
    """CREATE TABLE IF NOT EXISTS consentimentos (
        usuario_id TEXT PRIMARY KEY,
        memoria INTEGER NOT NULL,
        saude INTEGER NOT NULL,
        atualizado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS fatos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id TEXT NOT NULL,
        conversa_id TEXT NOT NULL,
        categoria TEXT NOT NULL,
        area TEXT NOT NULL,
        texto TEXT NOT NULL,
        valido_desde TEXT NOT NULL,
        valido_ate TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS entregas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id TEXT NOT NULL,
        conversa_id TEXT NOT NULL,
        fato_id INTEGER NOT NULL,
        area_do_agente TEXT NOT NULL,
        entregue_em TEXT NOT NULL
    )""",
]


class FatosSQLite:
    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            for comando in _ESQUEMA:
                conexao.execute(comando)

    @contextmanager
    def _conectar(self):
        with closing(sqlite3.connect(self.caminho)) as conexao, conexao:
            yield conexao

    # Consentimento ----------------------------------------------------------------------------

    def definir_consentimento(self, usuario_id: str, memoria: bool, saude: bool, agora: datetime) -> None:
        """Aceite da memória e, à parte, da condição de saúde. Saúde sem memória não vale."""
        with self._conectar() as conexao:
            conexao.execute(
                "INSERT INTO consentimentos (usuario_id, memoria, saude, atualizado_em) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(usuario_id) DO UPDATE SET memoria = excluded.memoria, saude = excluded.saude, "
                "atualizado_em = excluded.atualizado_em",
                (usuario_id, int(memoria), int(memoria and saude), agora.isoformat()))

    def consentimento(self, usuario_id: str) -> Optional[Tuple[bool, bool]]:
        """(memória, saúde) registrados, ou None quando o Usuário ainda não respondeu."""
        with self._conectar() as conexao:
            linha = conexao.execute("SELECT memoria, saude FROM consentimentos WHERE usuario_id = ?",
                                    (usuario_id,)).fetchone()
        return (bool(linha[0]), bool(linha[1])) if linha else None

    # Fatos ------------------------------------------------------------------------------------

    def registrar(self, usuario_id: str, conversa_id: str, categoria: str, texto: str, agora: datetime) -> None:
        """Grava o fato e encerra a validade do anterior da mesma categoria."""
        area = area_do_fato(categoria)
        if area is None:
            raise ValueError(f"Categoria fora do esquema: {categoria!r}")
        with self._conectar() as conexao:
            conexao.execute(
                "UPDATE fatos SET valido_ate = ? WHERE usuario_id = ? AND categoria = ? AND valido_ate IS NULL",
                (agora.isoformat(), usuario_id, categoria))
            conexao.execute(
                "INSERT INTO fatos (usuario_id, conversa_id, categoria, area, texto, valido_desde) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (usuario_id, conversa_id, categoria, area, texto, agora.isoformat()))

    def validos(self, usuario_id: str, agora: datetime, prazo_dias: int, incluir_saude: bool) -> List[FatoDoUsuario]:
        """Fatos em vigor e não expirados; sem o consentimento de saúde, a condição de saúde não entra."""
        limite = (agora - timedelta(days=prazo_dias)).isoformat()
        with self._conectar() as conexao:
            linhas = conexao.execute(
                "SELECT id, categoria, area, texto, conversa_id, valido_desde FROM fatos "
                "WHERE usuario_id = ? AND valido_ate IS NULL AND valido_desde >= ? ORDER BY id",
                (usuario_id, limite)).fetchall()
        fatos = [FatoDoUsuario(*linha) for linha in linhas]
        return [f for f in fatos if incluir_saude or f.categoria != CATEGORIA_CONDICAO_SAUDE]

    def registrar_entregas(self, usuario_id: str, conversa_id: str, area_do_agente: str,
                           fatos: Sequence[FatoDoUsuario], agora: datetime) -> None:
        with self._conectar() as conexao:
            conexao.executemany(
                "INSERT INTO entregas (usuario_id, conversa_id, fato_id, area_do_agente, entregue_em) "
                "VALUES (?, ?, ?, ?, ?)",
                [(usuario_id, conversa_id, f.id, area_do_agente, agora.isoformat()) for f in fatos])

    def entregas(self, usuario_id: str) -> List[Tuple[int, str, str]]:
        """(fato_id, área do agente, Conversa) de cada entrega, para auditoria do RF-IA09."""
        with self._conectar() as conexao:
            return conexao.execute(
                "SELECT fato_id, area_do_agente, conversa_id FROM entregas WHERE usuario_id = ? ORDER BY id",
                (usuario_id,)).fetchall()

    # Exclusão (LGPD, art. 18) -----------------------------------------------------------------

    def apagar_fato(self, usuario_id: str, fato_id: int) -> int:
        with self._conectar() as conexao:
            conexao.execute("DELETE FROM entregas WHERE usuario_id = ? AND fato_id = ?", (usuario_id, fato_id))
            return conexao.execute("DELETE FROM fatos WHERE usuario_id = ? AND id = ?",
                                   (usuario_id, fato_id)).rowcount

    def apagar_conversa(self, usuario_id: str, conversa_id: str) -> int:
        with self._conectar() as conexao:
            conexao.execute("DELETE FROM entregas WHERE usuario_id = ? AND fato_id IN "
                            "(SELECT id FROM fatos WHERE usuario_id = ? AND conversa_id = ?)",
                            (usuario_id, usuario_id, conversa_id))
            conexao.execute("DELETE FROM entregas WHERE usuario_id = ? AND conversa_id = ?", (usuario_id, conversa_id))
            return conexao.execute("DELETE FROM fatos WHERE usuario_id = ? AND conversa_id = ?",
                                   (usuario_id, conversa_id)).rowcount

    def apagar_usuario(self, usuario_id: str) -> int:
        with self._conectar() as conexao:
            conexao.execute("DELETE FROM entregas WHERE usuario_id = ?", (usuario_id,))
            conexao.execute("DELETE FROM consentimentos WHERE usuario_id = ?", (usuario_id,))
            return conexao.execute("DELETE FROM fatos WHERE usuario_id = ?", (usuario_id,)).rowcount

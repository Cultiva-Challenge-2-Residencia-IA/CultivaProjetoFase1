"""Relevância da busca (issue #105): reranker cross-encoder, filtro antes da síntese e roteamento."""

import json
from pathlib import Path

import pytest

from src.agent.consultant_baseline import NutritionConsultantBaseline
from src.agents.fisica.consultor import ConsultorSaudeFisica
from src.models.schemas import DocumentChunk, RetrievedChunk
from src.orquestrador.roteamento import AREA_NUTRICAO, AREA_SAUDE_FISICA, rotear_por_regras
from src.rag.relevancia import julgar, mensagem_lacuna, reformular
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.reranker_cruzado import RerankerCruzado

RAIZ = Path(__file__).resolve().parents[1]


def _chunk(i: int, texto: str, doc: str = None) -> DocumentChunk:
    doc = doc or f"fonte-{i}"
    return DocumentChunk(chunk_id=f"{doc}-p{i:03d}-01", doc_id=doc, title=f"Fonte {i}",
                         source_organization="Org", publication_year=2020, clinical_domain="x",
                         evidence_level="GUIDELINE_CONSENSUS", section_path="S", raw_text=texto,
                         contextualized_text=texto, pagina_pdf=1)


class RerankerFalso(RerankerCruzado):
    """Nota por palavra-chave, sem modelo: 0,9 se o texto tem alguma palavra de `relevantes`."""

    def __init__(self, relevantes=()):
        super().__init__("falso")
        self.relevantes = [r.lower() for r in relevantes]
        self.chamadas = 0

    def _pontuar_modelo(self, consulta, textos):
        self.chamadas += 1
        return [0.9 if any(r in t.lower() for r in self.relevantes) else 0.01 for t in textos]


CHUNKS = [
    _chunk(1, "Low back pain in schoolchildren and physical education classes."),
    _chunk(2, "Gait speed and walking in older adults."),
    _chunk(3, "Lower body resistance training improves leg strength in adults."),
    _chunk(4, "Physical education curriculum at school."),
    _chunk(5, "Ankle sprain rehabilitation protocols."),
]


def test_reranker_reordena_os_candidatos_pela_nota_do_cross_encoder():
    retriever = HybridRetriever(CHUNKS, use_vector_store=False, vector_mode="legacy_lsa",
                                reranker=RerankerFalso(["lower body"]))
    recuperados = retriever.retrieve("treinar perna lower body", top_k=3)
    assert recuperados[0].chunk.chunk_id == "fonte-3-p003-01"
    assert recuperados[0].relevancia == pytest.approx(0.9)
    assert all(r.relevancia is not None for r in recuperados)


def test_cache_do_reranker_nao_pontua_o_mesmo_par_duas_vezes():
    reranker = RerankerFalso(["leg"])
    reranker.pontuar("q", ["leg day", "arm"], ["a", "b"])
    reranker.pontuar("q", ["leg day", "arm"], ["a", "b"])
    assert reranker.chamadas == 1


def test_filtro_separa_pelo_limiar_e_mantem_a_ordem():
    itens = [RetrievedChunk(chunk=c) for c in CHUNKS[:4]]
    julgamento = julgar("treinar perna", itens, RerankerFalso(["resistance", "gait"]), limiar=0.5)
    assert [r.chunk.chunk_id for r in julgamento.mantidos] == ["fonte-2-p002-01", "fonte-3-p003-01"]
    assert len(julgamento.descartados) == 2
    assert not julgamento.lacuna


def test_reformular_sem_llm_ou_com_saida_invalida_nao_devolve_consultas():
    assert reformular("treinar perna", "saude_fisica", None) == []
    assert reformular("treinar perna", "saude_fisica", lambda s, u: {"outra": 1}) == []
    assert reformular("treinar perna", "saude_fisica", lambda s, u: (_ for _ in ()).throw(TimeoutError())) == []
    consultas = reformular("treinar perna", "saude_fisica",
                           lambda s, u: {"consultas": ["lower body resistance training", "", "treinar perna"]})
    assert consultas == ["lower body resistance training"]


def _consultor_fisica(reranker, reformulacao=None):
    consultor = ConsultorSaudeFisica(chunks=CHUNKS, enable_ollama=False)
    consultor.retriever = HybridRetriever(CHUNKS, use_vector_store=False, vector_mode="legacy_lsa")
    consultor.filtro_reranker = reranker
    consultor.filtro_limiar = 0.5
    consultor.reformulacao_llm = reformulacao
    return consultor


def test_sem_trecho_relevante_a_resposta_e_a_lacuna_explicita():
    consultor = _consultor_fisica(RerankerFalso([]))
    resposta = consultor.responder("Gostaria de treinar perna, pode me ajudar?", 4, [], [])
    assert resposta.fundamentacao_status == "lacuna_de_relevancia"
    assert resposta.abstencao
    assert resposta.evidence_summary == mensagem_lacuna(AREA_SAUDE_FISICA)
    assert resposta.retrieved_chunks == [] and resposta.trechos_usados == []
    assert "treino de força" in resposta.evidence_summary


def test_so_os_trechos_relevantes_vao_para_a_sintese():
    consultor = _consultor_fisica(RerankerFalso(["resistance training"]))
    resposta = consultor.responder("treinar perna resistance training", 4, [], [])
    assert resposta.fundamentacao_status != "lacuna_de_relevancia"
    assert [r.chunk.chunk_id for r in resposta.retrieved_chunks] == ["fonte-3-p003-01"]


def test_reformulacao_resgata_a_pergunta_quando_a_primeira_busca_nao_tem_base():
    chamadas = []

    def llm(sistema, usuario):
        chamadas.append(json.loads(usuario))
        return {"consultas": ["lower body resistance training"]}

    consultor = _consultor_fisica(RerankerFalso(["resistance training"]), reformulacao=llm)
    # Com um Trecho só, a primeira busca (sem termo em comum com o corpus) traz um Trecho sem relação.
    resposta = consultor.responder("Gostaria de malhar as coxas", 1, [], [])
    assert chamadas and chamadas[0]["area"] == AREA_SAUDE_FISICA
    assert resposta.fundamentacao_status != "lacuna_de_relevancia"
    assert "fonte-3-p003-01" in [r.chunk.chunk_id for r in resposta.retrieved_chunks]


def test_reformulacao_recebe_a_pergunta_com_dados_pessoais_mascarados():
    chamadas = []

    def llm(sistema, usuario):
        chamadas.append(json.loads(usuario))
        return {"consultas": ["lower body resistance training"]}

    consultor = _consultor_fisica(RerankerFalso(["resistance training"]), reformulacao=llm)
    consultor.responder("Sou ana.souza@exemplo.com, CPF 123.456.789-09, quero malhar as coxas", 1, [], [])
    assert chamadas
    pergunta = chamadas[0]["pergunta"]
    assert "ana.souza@exemplo.com" not in pergunta and "123.456.789-09" not in pergunta
    assert "[EMAIL]" in pergunta and "[CPF]" in pergunta


def test_sem_filtro_o_fluxo_e_o_de_antes():
    consultor = _consultor_fisica(None)
    resposta = consultor.responder("Gostaria de treinar perna, pode me ajudar?", 4, [], [])
    assert resposta.fundamentacao_status != "lacuna_de_relevancia"
    assert resposta.retrieved_chunks


def test_lacuna_de_nutricao_aponta_os_temas_e_o_nutricionista():
    texto = mensagem_lacuna(AREA_NUTRICAO)
    assert "Guia Alimentar" in texto and "nutricionista" in texto


def test_padroes_por_area_reranker_e_filtro_so_em_saude_fisica(monkeypatch):
    """Sem parâmetros, valem os padrões de src/config.py: Nutrição sem reranker nem filtro."""
    import src.agent.consultant_baseline as cb

    for nome, valor in {"RERANKER_NUTRICAO": False, "FILTRO_RELEVANCIA_NUTRICAO": False,
                        "RERANKER_SAUDE_FISICA": True, "FILTRO_RELEVANCIA_SAUDE_FISICA": True}.items():
        monkeypatch.setattr(cb, nome, valor)
    nutricao = NutritionConsultantBaseline(chunks=CHUNKS, enable_ollama=False, enable_taco_tool=False,
                                           enable_graph_engine=False)
    assert nutricao.retriever.reranker is None and nutricao.filtro_reranker is None
    fisica = ConsultorSaudeFisica(chunks=CHUNKS, enable_ollama=False)
    # O mesmo reranker serve à busca e ao filtro, e o modelo só é carregado na primeira pergunta.
    assert isinstance(fisica.retriever.reranker, RerankerCruzado)
    assert fisica.filtro_reranker is fisica.retriever.reranker


def test_parametros_explicitos_desligam_reranker_e_filtro():
    consultor = ConsultorSaudeFisica(chunks=CHUNKS, enable_ollama=False, reranker_na_busca=False,
                                     filtro_relevancia=False)
    assert consultor.retriever.reranker is None and consultor.filtro_reranker is None


# --- Vocabulário de roteamento (critério 5 de eval/relevancia/criterios.md) -------------------

def test_dor_nas_costas_e_hidratacao_entram_no_roteamento():
    assert rotear_por_regras("Estou com dor nas costas faz uma semana").areas == [AREA_SAUDE_FISICA]
    assert rotear_por_regras("Isotônico é melhor que água?").areas == [AREA_NUTRICAO]
    assert set(rotear_por_regras("Hidratação durante o treino longo").areas) == {AREA_NUTRICAO, AREA_SAUDE_FISICA}


@pytest.mark.parametrize("mensagem", [
    "Canela ajuda a emagrecer?",
    "Coxa de frango assada é saudável?",
    "Torci muito pelo meu time e esqueci de jantar",
    "Chá de canela com leite",
])
def test_termos_ambiguos_nao_levam_pergunta_de_nutricao_so_para_saude_fisica(mensagem):
    """Revisão do PR da #105: "canela", "coxa" e "torci" só contam para Saúde Física com contexto."""
    assert rotear_por_regras(mensagem).areas != [AREA_SAUDE_FISICA]


@pytest.mark.parametrize("mensagem", [
    "Dor na canela depois de correr",
    "Estou com dor nas coxas",
    "Minha canela dói",
    "Torci o pé ontem",
    "Tive uma torção no pé",
])
def test_termos_ambiguos_com_contexto_vao_para_saude_fisica(mensagem):
    assert rotear_por_regras(mensagem).areas == [AREA_SAUDE_FISICA]


@pytest.mark.parametrize("split", ["dev", "test"])
def test_regras_acertam_os_casos_claros_novos(split):
    """Só regras, casos `clara` do roteamento novo, acerto >= 0,90."""
    casos = json.loads((RAIZ / "eval/relevancia/roteamento.json").read_text(encoding="utf-8"))["casos"]
    claros = [c for c in casos if c["split"] == split and c["tipo"] == "clara"]
    acertos = sum(sorted(rotear_por_regras(c["mensagem"]).areas) == sorted(c["areas_esperadas"]) for c in claros)
    assert acertos / len(claros) >= 0.90

"""Embeddings e reranker usam CPU, a não ser com CULTIVA_EMBEDDINGS_GPU: com o onnxruntime-gpu
instalado, o fastembed escolhia a GPU sozinho e disputava a memória da placa com o Ollama."""

from src.retrieval import reranker_cruzado, vector_store


def test_sem_gpu_ligada_os_provedores_sao_so_cpu(monkeypatch):
    monkeypatch.setattr(vector_store, "EMBEDDINGS_GPU", False)
    assert vector_store.provedores_onnx() == ["CPUExecutionProvider"]


def test_com_gpu_ligada_usa_a_placa_configurada_e_cai_na_cpu(monkeypatch):
    monkeypatch.setattr(vector_store, "EMBEDDINGS_GPU", True)
    monkeypatch.setattr(vector_store, "EMBEDDINGS_GPU_ID", 0)
    assert vector_store.provedores_onnx() == [("CUDAExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]


def test_reranker_recebe_os_provedores(monkeypatch):
    import fastembed.rerank.cross_encoder as ce

    recebidos = {}

    class CrossEncoderFalso:
        def __init__(self, model_name, **opcoes):
            recebidos.update(opcoes)

    monkeypatch.setattr(ce, "TextCrossEncoder", CrossEncoderFalso)
    monkeypatch.setattr(vector_store, "EMBEDDINGS_GPU", False)
    monkeypatch.setattr(reranker_cruzado, "_MODELOS", {})
    reranker_cruzado._modelo("modelo-falso")
    assert recebidos["providers"] == ["CPUExecutionProvider"]

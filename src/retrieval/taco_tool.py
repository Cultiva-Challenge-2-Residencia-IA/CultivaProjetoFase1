import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import TACO_RAW_PATH
from src.models.schemas import TacoFoodNutrientRecord
from src.retrieval.hybrid_retriever import normalize_text

# Mapeamento de termos em português para os campos exatos da Tabela TACO (por 100g de parte comestível)
NUTRIENT_ALIASES: Dict[str, Tuple[str, str]] = {
    "magnesio": ("magnesium_mg", "Magnésio (mg)"),
    "potassio": ("potassium_mg", "Potássio (mg)"),
    "selenio": ("selenium_mcg", "Selênio (mcg)"),
    "ferro": ("iron_mg", "Ferro (mg)"),
    "calcio": ("calcium_mg", "Cálcio (mg)"),
    "sodio": ("sodium_mg", "Sódio (mg)"),
    "zinco": ("zinc_mg", "Zinco (mg)"),
    "fosforo": ("phosphorus_mg", "Fósforo (mg)"),
    "cobre": ("copper_mg", "Cobre (mg)"),
    "manganes": ("manganese_mg", "Manganês (mg)"),
    "vitamina c": ("vitaminC_mg", "Vitamina C (mg)"),
    "acido ascorbico": ("vitaminC_mg", "Vitamina C (mg)"),
    "fibra": ("fiber_g", "Fibra Alimentar (g)"),
    "fibras": ("fiber_g", "Fibra Alimentar (g)"),
    "proteina": ("protein_g", "Proteína (g)"),
    "proteinas": ("protein_g", "Proteína (g)"),
    "carboidrato": ("carbohydrate_g", "Carboidrato (g)"),
    "colesterol": ("cholesterol_mg", "Colesterol (mg)"),
    "gordura saturada": ("saturated_g", "Gordura Saturada (g)"),
    "monoinsaturada": ("monounsaturated_g", "Gordura Monoinsaturada (g)"),
    "poli-insaturada": ("polyunsaturated_g", "Gordura Poli-insaturada (g)"),
    "leucina": ("leucine_g", "Leucina (g)"),
    "lisina": ("lysine_g", "Lisina (g)"),
    "metionina": ("methionine_g", "Metionina (g)"),
    "triptofano": ("tryptophan_g", "Triptofano (g)"),
}

# Sinônimos populares brasileiros -> termos exatos da descrição na Tabela TACO
FOOD_NAME_ALIASES: Dict[str, List[str]] = {
    "castanha-do-para": ["castanha-do-brasil, crua"],
    "castanha do para": ["castanha-do-brasil, crua"],
    "castanha-do-brasil": ["castanha-do-brasil, crua"],
    "castanha de caju": ["castanha-de-caju, torrada"],
    "castanhas": ["castanha-do-brasil, crua", "castanha-de-caju, torrada", "amendoa, torrada"],
    "semente de abobora": ["semente de abobora, crua (tbca/taco)"],
    "sementes": ["semente de abobora, crua (tbca/taco)", "linhaca, semente", "gergelim, semente"],
    "linhaca": ["linhaca, semente"],
    "gergelim": ["gergelim, semente"],
    "feijao preto": ["feijao, preto, cozido", "feijao, preto, cru"],
    "feijao carioca": ["feijao, carioca, cozido", "feijao, carioca, cru"],
    "feijao": ["feijao, preto, cozido", "feijao, carioca, cozido"],
    "feijoes": ["feijao, preto, cozido", "feijao, carioca, cozido", "feijao, fradinho, cozido"],
    "arroz integral": ["arroz, integral, cozido"],
    "arroz": ["arroz, integral, cozido", "arroz, tipo 1, cozido"],
    "aveia": ["aveia, flocos, crua"],
    "sardinha": ["sardinha, assada", "sardinha, conserva em oleo"],
    "salmao": ["salmao, sem pele, fresco, grelhado"],
    "ovo": ["ovo, de galinha, inteiro, cozido/10minutos"],
    "brocolis": ["brocolis, cozido", "brocolis, flores, cruas"],
    "couve": ["couve, manteiga, crua", "couve, manteiga, refogada"],
    "espinafre": ["espinafre, nova zelandia, refogado"],
    "beterraba": ["beterraba, crua", "beterraba, cozida"],
    "laranja": ["laranja, pera, crua"],
    "acerola": ["acerola, crua"],
}

# Valores de referência de Selênio (mcg/100g) da TBCA-USP para alimentos-chave (a TACO 4ª ed não dosou Se)
TBCA_SELENIUM_REFERENCE_MCG: Dict[str, float] = {
    "castanha-do-brasil, crua": 1917.0,
    "semente de abobora, crua (tbca/taco)": 9.4,
    "castanha-de-caju, torrada, salgada": 19.9,
    "amendoa, torrada, salgada": 4.1,
    "gergelim, semente": 34.4,
    "linhaca, semente": 25.4,
    "feijao, preto, cozido": 3.2,
    "feijao, preto, cru": 11.8,
    "feijao, carioca, cozido": 2.9,
    "aveia, flocos, crua": 28.9,
    "arroz, integral, cozido": 9.8,
    "sardinha, assada": 52.7,
    "ovo, de galinha, inteiro, cozido/10minutos": 30.8,
}

# Registro complementar TBCA-USP para Semente de Abóbora (muito consultada para magnésio/zinco/potássio)
SUPPLEMENTARY_TBCA_FOODS: List[Dict[str, Any]] = [
    {
        "id": 9001,
        "description": "Semente de abóbora, crua (TBCA/TACO)",
        "category": "Nozes e sementes",
        "energy_kcal": 559.0,
        "protein_g": 30.23,
        "lipid_g": 49.05,
        "carbohydrate_g": 10.71,
        "fiber_g": 6.0,
        "calcium_mg": 46.0,
        "magnesium_mg": 592.0,
        "phosphorus_mg": 1233.0,
        "iron_mg": 8.82,
        "sodium_mg": 7.0,
        "potassium_mg": 809.0,
        "zinc_mg": 7.81,
        "copper_mg": 1.34,
        "manganese_mg": 4.54,
        "vitaminC_mg": 1.9,
        "selenium_mcg": 9.4,
    }
]


def _parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return round(float(val), 2)
    s = str(val).strip().upper()
    if s in {"NA", "TR", "*", "", "-"}:
        return 0.0 if s == "TR" else None
    try:
        return round(float(s.replace(",", ".")), 2)
    except ValueError:
        return None


class TacoDeterministicTool:
    """
    Ferramenta Determinística da Fase 2 (Passo 2):
    Consulta exata em memória sobre os 597 alimentos da Tabela Brasileira de Composição de Alimentos
    (TACO 4ª Edição - Unicamp + complemento TBCA-USP), eliminando alucinação numérica do LLM.
    """

    def __init__(self, taco_path: Path = TACO_RAW_PATH) -> None:
        if not taco_path.exists():
            raise FileNotFoundError(f"Arquivo da Tabela TACO não encontrado em: {taco_path}")

        raw_items: List[Dict[str, Any]] = json.loads(taco_path.read_text(encoding="utf-8"))
        self.foods: List[Dict[str, Any]] = []

        for item in raw_items + SUPPLEMENTARY_TBCA_FOODS:
            desc_norm = normalize_text(str(item.get("description", "")))
            enriched = dict(item)
            enriched["_desc_norm"] = desc_norm
            if "selenium_mcg" not in enriched and desc_norm in TBCA_SELENIUM_REFERENCE_MCG:
                enriched["selenium_mcg"] = TBCA_SELENIUM_REFERENCE_MCG[desc_norm]
            self.foods.append(enriched)

    def _to_record(
        self, food: Dict[str, Any], requested_fields: List[Tuple[str, str]]
    ) -> TacoFoodNutrientRecord:
        nutrients: Dict[str, float] = {}
        for field_key, label in requested_fields:
            val = _parse_float(food.get(field_key))
            if val is not None:
                nutrients[label] = val

        # Se nenhum campo específico foi pedido, inclui os principais minerais e macronutrientes
        if not nutrients:
            default_fields = [
                ("magnesium_mg", "Magnésio (mg)"),
                ("potassium_mg", "Potássio (mg)"),
                ("iron_mg", "Ferro (mg)"),
                ("calcium_mg", "Cálcio (mg)"),
                ("sodium_mg", "Sódio (mg)"),
                ("zinc_mg", "Zinco (mg)"),
                ("vitaminC_mg", "Vitamina C (mg)"),
                ("selenium_mcg", "Selênio (mcg)"),
            ]
            for field_key, label in default_fields:
                val = _parse_float(food.get(field_key))
                if val is not None and val > 0:
                    nutrients[label] = val

        return TacoFoodNutrientRecord(
            food_id=int(food.get("id", 0)),
            description=str(food.get("description", "")),
            category=str(food.get("category", "")),
            energy_kcal=_parse_float(food.get("energy_kcal")),
            protein_g=_parse_float(food.get("protein_g")),
            fiber_g=_parse_float(food.get("fiber_g")),
            nutrients_per_100g=nutrients,
        )

    def search_foods_by_name(
        self,
        food_query: str,
        requested_fields: Optional[List[Tuple[str, str]]] = None,
        limit: int = 5,
    ) -> List[TacoFoodNutrientRecord]:
        norm_q = normalize_text(food_query)
        fields = requested_fields or []
        matched: List[Dict[str, Any]] = []
        seen_ids = set()

        # 1. Verifica mapeamentos diretos de nomes populares
        for alias, target_descs in FOOD_NAME_ALIASES.items():
            if alias in norm_q:
                for target in target_descs:
                    for f in self.foods:
                        if target in f["_desc_norm"] and f["id"] not in seen_ids:
                            seen_ids.add(f["id"])
                            matched.append(f)

        # 2. Busca por substring direta na descrição da TACO
        if len(matched) < limit:
            tokens = [t for t in norm_q.split() if len(t) > 3]
            for f in self.foods:
                if f["id"] in seen_ids:
                    continue
                if any(tok in f["_desc_norm"] for tok in tokens):
                    seen_ids.add(f["id"])
                    matched.append(f)
                    if len(matched) >= limit:
                        break

        return [self._to_record(f, fields) for f in matched[:limit]]

    def rank_foods_by_nutrient(
        self,
        nutrient_field: str,
        nutrient_label: str,
        limit: int = 5,
        category_filter: Optional[str] = None,
    ) -> List[TacoFoodNutrientRecord]:
        candidates: List[Tuple[float, Dict[str, Any]]] = []
        for f in self.foods:
            if category_filter and normalize_text(category_filter) not in normalize_text(
                str(f.get("category", ""))
            ):
                continue
            val = _parse_float(f.get(nutrient_field))
            if val is not None and val > 0:
                candidates.append((val, f))

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [
            self._to_record(f, [(nutrient_field, nutrient_label)])
            for _, f in candidates[:limit]
        ]

    def auto_query_from_question(
        self, user_query: str
    ) -> Tuple[List[TacoFoodNutrientRecord], str]:
        """
        Analisa a pergunta do usuário, identifica alimentos e nutrientes mencionados
        e executa a consulta determinística na Tabela TACO (por 100g).
        """
        norm_q = normalize_text(user_query)

        # 1. Identifica nutrientes mencionados na pergunta
        detected_nutrients: List[Tuple[str, str]] = []
        seen_fields = set()
        for alias, (field_key, label) in NUTRIENT_ALIASES.items():
            if alias in norm_q and field_key not in seen_fields:
                seen_fields.add(field_key)
                detected_nutrients.append((field_key, label))

        # 2. Identifica alimentos específicos mencionados na pergunta
        matched_records: List[TacoFoodNutrientRecord] = []
        seen_food_ids = set()

        for alias, target_descs in sorted(
            FOOD_NAME_ALIASES.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if alias in norm_q:
                for target in target_descs:
                    for f in self.foods:
                        if target in f["_desc_norm"] and f["id"] not in seen_food_ids:
                            seen_food_ids.add(f["id"])
                            matched_records.append(self._to_record(f, detected_nutrients))

        # 3. Se a pergunta menciona TACO / miligramas / 100g / nutrientes mas poucos alimentos,
        # complementa com os alimentos líderes nos nutrientes solicitados
        triggers_quantitative = any(
            kw in norm_q
            for kw in ["taco", "tbca", "miligramas", "100g", "quantidade exata", "mais rico", "concentracao"]
        )

        if (triggers_quantitative or matched_records) and detected_nutrients and len(matched_records) < 3:
            primary_field, primary_label = detected_nutrients[0]
            top_ranked = self.rank_foods_by_nutrient(primary_field, primary_label, limit=4)
            for rec in top_ranked:
                if rec.food_id not in seen_food_ids:
                    seen_food_ids.add(rec.food_id)
                    matched_records.append(rec)

        if not matched_records:
            return [], ""

        matched_records = matched_records[:6]
        lines = [
            "DADOS DETERMINÍSTICOS DA TABELA TACO (4ª Ed. Unicamp / TBCA-USP — Valores exatos por 100g de alimento):"
        ]
        for rec in matched_records:
            nutr_parts = [f"{k}: {v}" for k, v in rec.nutrients_per_100g.items()]
            macros = (
                f"Energia: {rec.energy_kcal} kcal | Proteína: {rec.protein_g} g | Fibra: {rec.fiber_g} g"
            )
            nutr_str = " | ".join(nutr_parts) if nutr_parts else "Composição geral disponível"
            lines.append(
                f"- {rec.description} [{rec.category}]: {macros} | {nutr_str}"
            )

        return matched_records, "\n".join(lines)

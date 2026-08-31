import json

import pytest

import agents.meta_data_fiter.agent.helpers as helpers_module
import agents.meta_data_fiter.agent.meta_data_filter as meta_data_filter_module
from agents.meta_data_fiter.agent.meta_data_filter import meta_data_filter
from agents.meta_data_fiter.search_engine import MedicineSearchEngine

SEARCH_FIELDS = [
    "commercial_name_en",
    "commercial_name_ar",
    "scientific_name",
    "manufacturer",
    "drug_class",
]

FIXTURE_RECORDS = [
    {"commercial_name_en": "PANADOL EXTRA", "commercial_name_ar": "بانادول اكسترا",
     "scientific_name": "PARACETAMOL", "manufacturer": "GSK", "drug_class": "ANALGESIC",
     "route": "ORAL.SOLID", "price_egp": 20.0},
    # Ambiguity pair: neither record's OTHER field mentions amoxicillin at all, so
    # only a union of the commercial_name_en search and the scientific_name search
    # (not an intersection) can surface both.
    {"commercial_name_en": "ZYMOX CAPS", "commercial_name_ar": "زيموكس",
     "scientific_name": "AMOXICILLIN", "manufacturer": "EIPICO", "drug_class": "ANTIBIOTIC",
     "route": "ORAL.SOLID", "price_egp": 15.0},
    {"commercial_name_en": "AMOXICILLIN PHARMA", "commercial_name_ar": "اموكسيسيلين فارما",
     "scientific_name": "SOME OTHER INGREDIENT", "manufacturer": "AMOUN", "drug_class": "ANTIBIOTIC",
     "route": "ORAL.SOLID", "price_egp": 8.0},
    # Route pair: same-ish name, different route -- only one should survive a route filter.
    {"commercial_name_en": "CATAFLAM GEL", "commercial_name_ar": "كتافلام جل",
     "scientific_name": "DICLOFENAC", "manufacturer": "NOVARTIS", "drug_class": "NSAID",
     "route": "TOPICAL", "price_egp": 30.0},
    {"commercial_name_en": "CATAFLAM TABS", "commercial_name_ar": "كتافلام أقراص",
     "scientific_name": "DICLOFENAC", "manufacturer": "NOVARTIS", "drug_class": "NSAID",
     "route": "ORAL.SOLID", "price_egp": 25.0},
    # Price trio for range-filter and sort-directive tests.
    {"commercial_name_en": "VITADOL 10", "commercial_name_ar": "فيتادول 10",
     "scientific_name": "VITAMIN D3", "manufacturer": "SIGMA", "drug_class": "VITAMIN",
     "route": "ORAL.SOLID", "price_egp": 10.0},
    {"commercial_name_en": "VITADOL 50", "commercial_name_ar": "فيتادول 50",
     "scientific_name": "VITAMIN D3", "manufacturer": "SIGMA", "drug_class": "VITAMIN",
     "route": "ORAL.SOLID", "price_egp": 50.0},
    {"commercial_name_en": "VITADOL 100", "commercial_name_ar": "فيتادول 100",
     "scientific_name": "VITAMIN D3", "manufacturer": "SIGMA", "drug_class": "VITAMIN",
     "route": "ORAL.SOLID", "price_egp": 100.0},
]


@pytest.fixture(autouse=True)
def fixture_engine(monkeypatch):
    engine = MedicineSearchEngine(search_fields=SEARCH_FIELDS)
    engine.load_data(FIXTURE_RECORDS)
    monkeypatch.setattr(meta_data_filter_module, "get_commercial_engine", lambda: engine)
    return engine


@pytest.fixture(autouse=True)
def isolated_low_confidence_log(tmp_path, monkeypatch):
    log_path = tmp_path / "low_confidence_queries.jsonl"
    monkeypatch.setattr(helpers_module, "LOW_CONFIDENCE_LOG_PATH", log_path)
    return log_path


def _names(context):
    return {row["commercial_name_en"] for row in context}


def test_no_filters_at_all_returns_empty_context():
    assert meta_data_filter({}) == {"context": []}


def test_text_field_search_finds_the_right_product():
    result = meta_data_filter({"commercial_name_en": "panadol extre"})
    assert "PANADOL EXTRA" in _names(result["context"])


def test_ambiguous_same_token_in_two_fields_is_ored_not_intersected():
    # Neither ZYMOX CAPS nor AMOXICILLIN PHARMA matches on BOTH fields at once --
    # an intersection would return nothing.
    result = meta_data_filter({"commercial_name_en": "AMOXICILLIN", "scientific_name": "AMOXICILLIN"})
    names = _names(result["context"])
    assert "ZYMOX CAPS" in names
    assert "AMOXICILLIN PHARMA" in names


def test_route_hard_filter_excludes_the_wrong_route():
    result = meta_data_filter({"commercial_name_en": "cataflam", "route": "ORAL.SOLID"})
    names = _names(result["context"])
    assert "CATAFLAM TABS" in names
    assert "CATAFLAM GEL" not in names


def test_route_filter_alone_with_no_text_field():
    result = meta_data_filter({"route": "TOPICAL"})
    assert _names(result["context"]) == {"CATAFLAM GEL"}


def test_price_range_hard_filter():
    result = meta_data_filter({"scientific_name": "vitamin d3", "price_egp": "0-20"})
    assert _names(result["context"]) == {"VITADOL 10"}


def test_price_bound_hard_filter_alone_with_no_text_field():
    result = meta_data_filter({"price_egp": ">40"})
    names = _names(result["context"])
    assert "VITADOL 50" in names
    assert "VITADOL 100" in names
    assert "VITADOL 10" not in names


def test_price_asc_sorts_without_filtering():
    result = meta_data_filter({"scientific_name": "vitamin d3", "price_egp": "asc"})
    prices = [row["price_egp"] for row in result["context"] if row["commercial_name_en"].startswith("VITADOL")]
    assert prices == sorted(prices)


def test_price_desc_sorts_without_filtering():
    result = meta_data_filter({"scientific_name": "vitamin d3", "price_egp": "desc"})
    prices = [row["price_egp"] for row in result["context"] if row["commercial_name_en"].startswith("VITADOL")]
    assert prices == sorted(prices, reverse=True)


class _FakeEngineNoHits:
    """A real fuzzy-matcher's noise floor against an 8-record fixture isn't a
    reliable way to force an empty result, so this pins down the logging wiring
    itself: given both exact_match() and search() return nothing, was
    log_low_confidence_query called with that field's best_score()?"""

    records = []

    def exact_match(self, query, top_k=5):
        return []

    def search(self, query, top_k=5, candidates_limit=30):
        return []

    def best_score(self, query, candidates_limit=30):
        return 0.42


def test_low_confidence_query_is_logged(monkeypatch, isolated_low_confidence_log):
    monkeypatch.setattr(meta_data_filter_module, "get_commercial_engine", lambda: _FakeEngineNoHits())

    meta_data_filter({"commercial_name_en": "vxqzkj fpwmbgl nonsense"})

    lines = isolated_low_confidence_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["field"] == "commercial_name_en"
    assert entry["query"] == "vxqzkj fpwmbgl nonsense"
    assert entry["best_score"] == 0.42


def test_confident_match_is_not_logged(isolated_low_confidence_log):
    meta_data_filter({"commercial_name_en": "panadol extre"})
    assert not isolated_low_confidence_log.exists()


def test_context_capped_at_max_items(monkeypatch):
    many_records = [
        {"commercial_name_en": f"BULKDRUG {i}", "commercial_name_ar": f"بلكدرج {i}",
         "scientific_name": "BULKINGREDIENT", "manufacturer": "BULKCO", "drug_class": "BULKCLASS",
         "route": "ORAL.SOLID", "price_egp": float(i)}
        for i in range(60)
    ]
    engine = MedicineSearchEngine(search_fields=SEARCH_FIELDS)
    engine.load_data(many_records)
    monkeypatch.setattr(meta_data_filter_module, "get_commercial_engine", lambda: engine)

    result = meta_data_filter({"scientific_name": "BULKINGREDIENT"})
    assert len(result["context"]) == meta_data_filter_module.MAX_CONTEXT_ITEMS

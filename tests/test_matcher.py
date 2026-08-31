import agents.compound_mapper.matcher as matcher_module
from agents.compound_mapper.academic_index import AcademicIndex
from agents.compound_mapper.matcher import match_component, split_components

FIXTURE_RECORDS = [
    {
        "id": 101,
        "name": "Abacavir",
        "generic_name": "Abacavir Sulphate",
        "abbreviation": "ABC",
        "pharmacologic_category": "NRTI",
    },
    {
        "id": 104,
        "name": "Ascorbic Acid",
        "generic_name": "Ascorbic Acid",
        "abbreviation": None,
        "pharmacologic_category": "Vitamin",
    },
    {
        "id": 105,
        "name": "Paracetamol",
        "generic_name": "Paracetamol",
        "abbreviation": None,
        "pharmacologic_category": "Analgesic",
    },
]

AMPICILLIN_ONLY_RECORDS = [
    {
        "id": 201,
        "name": "Ampicillin",
        "generic_name": "Ampicillin",
        "abbreviation": None,
        "pharmacologic_category": "Penicillin",
    },
]

COMBINATION_ONLY_RECORDS = [
    {
        "id": 202,
        "name": "Amoxicillin + Clavulanic Acid",
        "generic_name": "Amoxicillin + Clavulanic Acid",
        "abbreviation": None,
        "pharmacologic_category": "Penicillin combination",
    },
]


def test_split_preserves_order_and_count():
    components = split_components(
        "CHLORPHENIRAMINE+PARACETAMOL(ACETAMINOPHEN)+PSEUDOEPHEDRINE"
    )
    assert [c["component"] for c in components] == [
        "CHLORPHENIRAMINE",
        "PARACETAMOL",
        "PSEUDOEPHEDRINE",
    ]


def test_split_strips_trailing_strength():
    components = split_components("VITAMIN C 1 GM")
    assert components == [{"component": "VITAMIN C", "query_terms": ["VITAMIN C"]}]


def test_split_keeps_parenthetical_as_extra_query_term():
    components = split_components("PARACETAMOL(ACETAMINOPHEN)")
    assert components == [
        {"component": "PARACETAMOL", "query_terms": ["PARACETAMOL", "ACETAMINOPHEN"]}
    ]


def test_split_empty_input():
    assert split_components(None) == []
    assert split_components("") == []


def test_salt_suffix_resolves_via_exact_match(monkeypatch):
    monkeypatch.setattr(matcher_module, "ACADEMIC_INDEX", AcademicIndex(FIXTURE_RECORDS))

    outcome = match_component({"component": "ABACAVIR", "query_terms": ["ABACAVIR"]})

    assert outcome == {
        "component": "ABACAVIR",
        "matched": True,
        "generic_name": "Abacavir Sulphate",
        "candidates": [],
    }


def test_abbreviation_resolves_via_exact_match(monkeypatch):
    monkeypatch.setattr(matcher_module, "ACADEMIC_INDEX", AcademicIndex(FIXTURE_RECORDS))

    outcome = match_component({"component": "ABC", "query_terms": ["ABC"]})

    assert outcome["matched"] is True
    assert outcome["generic_name"] == "Abacavir Sulphate"


def test_alias_in_parentheses_resolves_via_the_alias_term(monkeypatch):
    monkeypatch.setattr(matcher_module, "ACADEMIC_INDEX", AcademicIndex(FIXTURE_RECORDS))

    outcome = match_component(
        {"component": "PARACETAMOL", "query_terms": ["PARACETAMOL", "ACETAMINOPHEN"]}
    )

    assert outcome["matched"] is True
    assert outcome["generic_name"] == "Paracetamol"


def test_amoxicillin_against_ampicillin_only_index_is_unresolved_not_falsely_matched(
    monkeypatch,
):
    monkeypatch.setattr(matcher_module, "ACADEMIC_INDEX", AcademicIndex(AMPICILLIN_ONLY_RECORDS))

    outcome = match_component({"component": "AMOXICILLIN", "query_terms": ["AMOXICILLIN"]})

    # The deterministic pass must not auto-accept a different molecule just because
    # it's the closest fuzzy candidate — it hands off to the LLM selection step
    # instead of forcing a match.
    assert outcome["matched"] is None
    assert outcome["generic_name"] is None
    assert [c["name"] for c in outcome["candidates"]] == ["Ampicillin"]


def test_single_ingredient_against_combination_only_index_is_unresolved(monkeypatch):
    monkeypatch.setattr(
        matcher_module, "ACADEMIC_INDEX", AcademicIndex(COMBINATION_ONLY_RECORDS)
    )

    outcome = match_component({"component": "AMOXICILLIN", "query_terms": ["AMOXICILLIN"]})

    assert outcome["matched"] is None
    assert [c["name"] for c in outcome["candidates"]] == ["Amoxicillin + Clavulanic Acid"]


def test_no_candidates_at_all_is_matched_false(monkeypatch):
    monkeypatch.setattr(matcher_module, "ACADEMIC_INDEX", AcademicIndex([]))

    outcome = match_component({"component": "AMOXICILLIN", "query_terms": ["AMOXICILLIN"]})

    assert outcome == {
        "component": "AMOXICILLIN",
        "matched": False,
        "generic_name": None,
        "candidates": [],
    }

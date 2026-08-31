from scripts.build_compound_map import build_match_index, resolve_component

FIXTURE_RECORDS = [
    {
        "id": 101,
        "name": "Abacavir",
        "generic_name": "Abacavir Sulphate",
        "abbreviation": "ABC",
    },
    {
        "id": 104,
        "name": "Ascorbic Acid",
        "generic_name": "Ascorbic Acid",
        "abbreviation": None,
    },
    {
        "id": 105,
        "name": "Paracetamol",
        "generic_name": "Paracetamol",
        "abbreviation": None,
    },
]

AMPICILLIN_ONLY_RECORDS = [
    {"id": 201, "name": "Ampicillin", "generic_name": "Ampicillin", "abbreviation": None},
]

COMBINATION_ONLY_RECORDS = [
    {
        "id": 202,
        "name": "Abacavir + Lamivudine",
        "generic_name": "Abacavir + Lamivudine",
        "abbreviation": None,
    },
]


def _index_and_keys(records):
    index = build_match_index(records)
    return index, list(index.keys())


def test_salt_form_resolves_via_exact_match():
    index, keys = _index_and_keys(FIXTURE_RECORDS)
    status, record, score = resolve_component("ABACAVIR", index, keys)
    assert status == "mapped"
    assert record["generic_name"] == "Abacavir Sulphate"
    assert score is None


def test_abbreviation_resolves_via_exact_match():
    index, keys = _index_and_keys(FIXTURE_RECORDS)
    status, record, _ = resolve_component("ABC", index, keys)
    assert status == "mapped"
    assert record["generic_name"] == "Abacavir Sulphate"


def test_parenthetical_alias_resolves_via_the_alt_term():
    index, keys = _index_and_keys(FIXTURE_RECORDS)
    status, record, _ = resolve_component("PARACETAMOL(ACETAMINOPHEN)", index, keys)
    assert status == "mapped"
    assert record["generic_name"] == "Paracetamol"


def test_strength_and_trivial_name_alias_resolve_together():
    index, keys = _index_and_keys(FIXTURE_RECORDS)
    status, record, _ = resolve_component("VITAMIN C 1 GM", index, keys)
    assert status == "mapped"
    assert record["generic_name"] == "Ascorbic Acid"


def test_amoxicillin_against_ampicillin_only_index_is_unmapped_not_matched():
    index, keys = _index_and_keys(AMPICILLIN_ONLY_RECORDS)
    status, record, _ = resolve_component("AMOXICILLIN", index, keys)
    # rapidfuzz.fuzz.ratio("amoxicillin", "ampicillin") is well under the
    # review threshold — a shared drug family must not surface as a fuzzy hit.
    assert status == "unmapped"
    assert record is None


def test_combination_record_is_never_indexed_for_a_single_ingredient():
    index, keys = _index_and_keys(COMBINATION_ONLY_RECORDS)
    assert index == {}
    status, record, _ = resolve_component("ABACAVIR", index, keys)
    assert status == "unmapped"
    assert record is None


def test_close_spelling_variant_goes_to_review_not_the_map():
    records = [
        {
            "id": 301,
            "name": "Hydrochlorothiazide",
            "generic_name": "Hydrochlorothiazide",
            "abbreviation": None,
        }
    ]
    index, keys = _index_and_keys(records)
    # A single-letter typo on a long name clears rapidfuzz.fuzz.ratio's 97 bar —
    # a near-miss, not an exact hit, so it must land in review, not the map.
    status, record, score = resolve_component("HYDROCHLOROTHIAZIDEE", index, keys)
    assert status == "review"
    assert record["generic_name"] == "Hydrochlorothiazide"
    assert score is not None and score >= 97


def test_moderate_spelling_variant_below_review_threshold_is_unmapped():
    records = [{"id": 302, "name": "Cefixime", "generic_name": "Cefixime", "abbreviation": None}]
    index, keys = _index_and_keys(records)
    # A plural-ish typo on a short name scores well under 97 with fuzz.ratio —
    # it must be a plain unmapped miss, not a review candidate.
    status, record, score = resolve_component("CEFIXIMES", index, keys)
    assert status == "unmapped"
    assert record is None

import agents.compound_mapper.compound_map as compound_map_module
from agents.compound_mapper.compound_map import get_generic_names

FIXTURE_MAP = {
    "ABACAVIR": "Abacavir Sulphate",
    "ABC": "Abacavir Sulphate",
    "PARACETAMOL": "Paracetamol",
    "ACETAMINOPHEN": "Paracetamol",
    "VITAMIN C 1 GM": "Ascorbic Acid",
}


def test_single_matched_component(monkeypatch):
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)

    assert get_generic_names("ABACAVIR") == [
        {"component": "ABACAVIR", "generic_name": "Abacavir Sulphate", "matched": True}
    ]


def test_abbreviation_lookup(monkeypatch):
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)

    assert get_generic_names("ABC") == [
        {"component": "ABC", "generic_name": "Abacavir Sulphate", "matched": True}
    ]


def test_embedded_strength_key_lookup(monkeypatch):
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)

    assert get_generic_names("VITAMIN C 1 GM") == [
        {"component": "VITAMIN C 1 GM", "generic_name": "Ascorbic Acid", "matched": True}
    ]


def test_unmapped_component_is_reported_not_dropped(monkeypatch):
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)

    assert get_generic_names("PSEUDOEPHEDRINE") == [
        {"component": "PSEUDOEPHEDRINE", "generic_name": None, "matched": False}
    ]


def test_partial_multi_component_mapping_preserves_order_and_count(monkeypatch):
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)

    result = get_generic_names("CHLORPHENIRAMINE+PARACETAMOL+PSEUDOEPHEDRINE")

    assert [r["component"] for r in result] == [
        "CHLORPHENIRAMINE",
        "PARACETAMOL",
        "PSEUDOEPHEDRINE",
    ]
    assert [r["matched"] for r in result] == [False, True, False]


def test_no_scientific_name_returns_empty_list(monkeypatch):
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)

    assert get_generic_names(None) == []
    assert get_generic_names("") == []


def test_runtime_never_normalises_or_guesses(monkeypatch):
    """The map is keyed on the raw commercial string verbatim -- a component
    that would normalise to the same molecule as a mapped key, but isn't
    itself a key, must stay unmapped. Runtime does zero normalisation."""
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)

    assert get_generic_names("Abacavir") == [
        {"component": "Abacavir", "generic_name": None, "matched": False}
    ]

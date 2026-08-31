import json

import pytest

import agents.compound_mapper.compound_map as compound_map_module
import agents.compound_mapper.unmapped_log as unmapped_log_module
from agents.compound_mapper.compound_mapper import compound_mapper

FIXTURE_MAP = {
    "ABACAVIR": "Abacavir Sulphate",
    "PARACETAMOL": "Paracetamol",
}


@pytest.fixture(autouse=True)
def fixture_map(monkeypatch):
    monkeypatch.setattr(compound_map_module, "COMPOUND_MAP", FIXTURE_MAP)


@pytest.fixture(autouse=True)
def isolated_unmapped_log(tmp_path, monkeypatch):
    log_path = tmp_path / "unmapped_compounds.jsonl"
    monkeypatch.setattr(unmapped_log_module, "LOG_PATH", log_path)
    return log_path


def test_direct_path_maps_a_single_ingredient_with_no_source_product():
    result = compound_mapper({"scientific_name": "ABACAVIR"})

    assert result == {
        "compound_mappings": [
            {
                "component": "ABACAVIR",
                "generic_name": "Abacavir Sulphate",
                "matched": True,
                "source_product": None,
            }
        ]
    }


def test_no_scientific_name_and_no_context_returns_empty_mappings():
    assert compound_mapper({}) == {"compound_mappings": []}


def test_duplicate_scientific_name_across_rows_is_mapped_once():
    context = [
        {"scientific_name": "ABACAVIR", "commercial_name_en": "Ziagen"},
        {"scientific_name": "ABACAVIR", "commercial_name_en": "Ziagen Extra"},
    ]

    result = compound_mapper({"context": context})

    assert result["compound_mappings"] == [
        {
            "component": "ABACAVIR",
            "generic_name": "Abacavir Sulphate",
            "matched": True,
            "source_product": "Ziagen",
        }
    ]


def test_three_component_product_preserves_order_and_count():
    context = [
        {
            "scientific_name": "ABACAVIR+PARACETAMOL+PSEUDOEPHEDRINE",
            "commercial_name_en": "1 2 3",
        }
    ]

    result = compound_mapper({"context": context})

    components = [m["component"] for m in result["compound_mappings"]]
    assert components == ["ABACAVIR", "PARACETAMOL", "PSEUDOEPHEDRINE"]
    assert [m["matched"] for m in result["compound_mappings"]] == [True, True, False]


def test_unmapped_component_carries_no_generic_name():
    result = compound_mapper({"scientific_name": "AMOXICILLIN"})

    assert result["compound_mappings"] == [
        {
            "component": "AMOXICILLIN",
            "generic_name": None,
            "matched": False,
            "source_product": None,
        }
    ]


def test_unmatched_component_is_logged(isolated_unmapped_log):
    compound_mapper({"scientific_name": "AMOXICILLIN"})

    lines = isolated_unmapped_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    logged = json.loads(lines[0])
    assert logged["component"] == "AMOXICILLIN"


def test_matched_component_is_not_logged(isolated_unmapped_log):
    compound_mapper({"scientific_name": "ABACAVIR"})

    assert not isolated_unmapped_log.exists()

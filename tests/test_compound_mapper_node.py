import json

import pytest

import agents.compound_mapper.compound_mapper as compound_mapper_module
import agents.compound_mapper.matcher as matcher_module
import agents.compound_mapper.unmapped_log as unmapped_log_module
from agents.compound_mapper.academic_index import AcademicIndex
from agents.compound_mapper.compound_mapper import compound_mapper
from models.compound_mapper import CompoundMapperModel

FIXTURE_RECORDS = [
    {
        "id": 101,
        "name": "Abacavir",
        "generic_name": "Abacavir Sulphate",
        "abbreviation": "ABC",
        "pharmacologic_category": "NRTI",
    },
    {
        "id": 105,
        "name": "Paracetamol",
        "generic_name": "Paracetamol",
        "abbreviation": None,
        "pharmacologic_category": "Analgesic",
    },
    {
        "id": 201,
        "name": "Ampicillin",
        "generic_name": "Ampicillin",
        "abbreviation": None,
        "pharmacologic_category": "Penicillin",
    },
]


@pytest.fixture(autouse=True)
def fixture_index(monkeypatch):
    index = AcademicIndex(FIXTURE_RECORDS)
    monkeypatch.setattr(matcher_module, "ACADEMIC_INDEX", index)
    monkeypatch.setattr(compound_mapper_module, "ACADEMIC_INDEX", index)
    return index


@pytest.fixture(autouse=True)
def isolated_unmapped_log(tmp_path, monkeypatch):
    log_path = tmp_path / "unmapped_compounds.jsonl"
    monkeypatch.setattr(unmapped_log_module, "LOG_PATH", log_path)
    return log_path


def _mock_llm(monkeypatch, mappings_payload):
    def _fake_constrained_invoke(message, fallback_order, constraine_model=None):
        return {"mappings": mappings_payload}

    monkeypatch.setattr(
        compound_mapper_module.fallback_client, "constrained_invoke", _fake_constrained_invoke
    )


def test_direct_path_maps_a_single_ingredient_with_no_source_product(monkeypatch):
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


def test_duplicate_scientific_name_across_rows_is_mapped_once(monkeypatch):
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


def test_three_component_product_preserves_order_and_count(monkeypatch):
    _mock_llm(
        monkeypatch,
        [
            {
                "component": "PSEUDOEPHEDRINE",
                "generic_name": None,
                "matched": False,
                "source_product": "1 2 3",
            }
        ],
    )
    context = [
        {
            "scientific_name": "ABACAVIR+PARACETAMOL(ACETAMINOPHEN)+PSEUDOEPHEDRINE",
            "commercial_name_en": "1 2 3",
        }
    ]

    result = compound_mapper({"context": context})

    components = [m["component"] for m in result["compound_mappings"]]
    assert components == ["ABACAVIR", "PARACETAMOL", "PSEUDOEPHEDRINE"]
    assert [m["matched"] for m in result["compound_mappings"]] == [True, True, False]


def test_llm_residue_only_receives_unresolved_components(monkeypatch):
    captured = {}

    def _fake_constrained_invoke(message, fallback_order, constraine_model=None):
        captured["human_prompt"] = message[1].content
        return {
            "mappings": [
                {
                    "component": "AMOXICILLIN",
                    "generic_name": None,
                    "matched": False,
                    "source_product": None,
                }
            ]
        }

    monkeypatch.setattr(
        compound_mapper_module.fallback_client, "constrained_invoke", _fake_constrained_invoke
    )

    result = compound_mapper({"scientific_name": "ABACAVIR+AMOXICILLIN"})

    # ABACAVIR resolved deterministically and must not appear in what was sent to the LLM.
    assert "ABACAVIR" not in captured["human_prompt"]
    assert "AMOXICILLIN" in captured["human_prompt"]
    assert result["compound_mappings"] == [
        {
            "component": "ABACAVIR",
            "generic_name": "Abacavir Sulphate",
            "matched": True,
            "source_product": None,
        },
        {
            "component": "AMOXICILLIN",
            "generic_name": None,
            "matched": False,
            "source_product": None,
        },
    ]


def test_amoxicillin_against_ampicillin_only_candidates_is_matched_false(monkeypatch):
    _mock_llm(
        monkeypatch,
        [
            {
                "component": "AMOXICILLIN",
                "generic_name": None,
                "matched": False,
                "source_product": None,
            }
        ],
    )

    result = compound_mapper({"scientific_name": "AMOXICILLIN"})

    assert result["compound_mappings"] == [
        {
            "component": "AMOXICILLIN",
            "generic_name": None,
            "matched": False,
            "source_product": None,
        }
    ]


def test_unmatched_component_is_logged(monkeypatch, isolated_unmapped_log):
    _mock_llm(
        monkeypatch,
        [
            {
                "component": "AMOXICILLIN",
                "generic_name": None,
                "matched": False,
                "source_product": None,
            }
        ],
    )

    compound_mapper({"scientific_name": "AMOXICILLIN"})

    lines = isolated_unmapped_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    logged = json.loads(lines[0])
    assert logged["component"] == "AMOXICILLIN"


def test_hallucinated_generic_name_from_the_llm_raises_instead_of_passing_through(
    monkeypatch,
):
    _mock_llm(
        monkeypatch,
        [
            {
                "component": "AMOXICILLIN",
                "generic_name": "Amoxicillin Trihydrate",  # not in the fixture index
                "matched": True,
                "source_product": None,
            }
        ],
    )

    with pytest.raises(Exception):
        compound_mapper({"scientific_name": "AMOXICILLIN"})

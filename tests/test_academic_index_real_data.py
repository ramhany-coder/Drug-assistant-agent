"""Sanity checks against the real data/10.json monograph file — the exact record the
build brief's own examples are drawn from (Abacavir / Abacavir Sulphate / ABC)."""

from agents.compound_mapper.academic_index import ACADEMIC_INDEX
from agents.compound_mapper.matcher import match_component


def test_real_dataset_loaded_abacavir():
    assert "Abacavir Sulphate" in ACADEMIC_INDEX.valid_generic_names


def test_salt_form_resolves_against_real_data():
    outcome = match_component({"component": "ABACAVIR", "query_terms": ["ABACAVIR"]})
    assert outcome["matched"] is True
    assert outcome["generic_name"] == "Abacavir Sulphate"


def test_abbreviation_resolves_against_real_data():
    outcome = match_component({"component": "ABC", "query_terms": ["ABC"]})
    assert outcome["matched"] is True
    assert outcome["generic_name"] == "Abacavir Sulphate"

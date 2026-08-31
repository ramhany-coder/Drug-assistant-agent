import pytest
from pydantic import ValidationError

from models.compound_mapper import CompoundMapperModel, CompoundMapping


def test_matched_true_requires_generic_name():
    with pytest.raises(ValidationError):
        CompoundMapping(component="ABACAVIR", generic_name=None, matched=True)


def test_matched_false_must_not_carry_a_generic_name():
    with pytest.raises(ValidationError):
        CompoundMapping(
            component="AMOXICILLIN", generic_name="Ampicillin", matched=False
        )


def test_valid_mapping_round_trips():
    mapping = CompoundMapping(
        component="ABACAVIR", generic_name="Abacavir Sulphate", matched=True
    )
    assert mapping.generic_name == "Abacavir Sulphate"


def test_fabricated_generic_name_not_in_index_raises():
    valid_generic_names = {"Abacavir Sulphate", "Lamivudine"}
    payload = {
        "mappings": [
            {
                "component": "AMOXICILLIN",
                "generic_name": "Amoxicillin Trihydrate",  # not in the index
                "matched": True,
                "source_product": None,
            }
        ]
    }

    with pytest.raises(ValidationError):
        CompoundMapperModel.model_validate(
            payload, context={"valid_generic_names": valid_generic_names}
        )


def test_generic_name_present_in_index_passes():
    valid_generic_names = {"Abacavir Sulphate", "Lamivudine"}
    payload = {
        "mappings": [
            {
                "component": "ABACAVIR",
                "generic_name": "Abacavir Sulphate",
                "matched": True,
                "source_product": None,
            }
        ]
    }

    validated = CompoundMapperModel.model_validate(
        payload, context={"valid_generic_names": valid_generic_names}
    )
    assert validated.mappings[0].generic_name == "Abacavir Sulphate"


def test_unmatched_component_is_never_checked_against_the_index():
    payload = {
        "mappings": [
            {
                "component": "AMOXICILLIN",
                "generic_name": None,
                "matched": False,
                "source_product": None,
            }
        ]
    }

    validated = CompoundMapperModel.model_validate(
        payload, context={"valid_generic_names": set()}
    )
    assert validated.mappings[0].matched is False


def test_no_context_skips_the_index_check():
    payload = {
        "mappings": [
            {
                "component": "AMOXICILLIN",
                "generic_name": "Anything At All",
                "matched": True,
                "source_product": None,
            }
        ]
    }

    validated = CompoundMapperModel.model_validate(payload)
    assert validated.mappings[0].generic_name == "Anything At All"

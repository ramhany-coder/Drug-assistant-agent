from agents.compound_mapper.normalize import (
    extract_parenthetical,
    normalize_compound,
    split_scientific_name,
)


def test_lowercases_and_collapses_whitespace():
    assert normalize_compound("  Paracetamol   Sodium  ") == "paracetamol"


def test_salt_suffix_is_stripped():
    assert normalize_compound("Abacavir Sulphate") == "abacavir"
    assert normalize_compound("ABACAVIR") == "abacavir"


def test_repeated_salt_suffixes_are_all_stripped():
    assert normalize_compound("Amlodipine Besylate Monohydrate") == "amlodipine"


def test_salt_suffix_alone_is_not_stripped_to_nothing():
    assert normalize_compound("Sodium") == "sodium"


def test_parenthetical_content_is_dropped_from_the_base_string():
    assert normalize_compound("PARACETAMOL(ACETAMINOPHEN)") == "paracetamol"


def test_embedded_strength_with_unit_is_stripped():
    assert normalize_compound("VITAMIN C 1 GM") == "ascorbic acid"
    assert normalize_compound("PARACETAMOL 500 MG") == "paracetamol"


def test_bare_trailing_number_without_unit_is_stripped():
    assert normalize_compound("IRON 60") == "iron"


def test_punctuation_is_stripped_but_hyphens_survive():
    assert normalize_compound("CO-AMOXICLAV,") == "co-amoxiclav"


def test_alias_reaches_the_same_form_from_either_direction():
    assert normalize_compound("ACETAMINOPHEN") == normalize_compound("PARACETAMOL") == "paracetamol"


def test_trivial_name_alias_needs_no_string_method():
    assert normalize_compound("VITAMIN C") == "ascorbic acid"


def test_empty_input_returns_empty_string():
    assert normalize_compound("") == ""
    assert normalize_compound(None) == ""


def test_extract_parenthetical_returns_the_inner_text():
    assert extract_parenthetical("PARACETAMOL(ACETAMINOPHEN)") == "ACETAMINOPHEN"


def test_extract_parenthetical_returns_none_when_absent():
    assert extract_parenthetical("PARACETAMOL") is None
    assert extract_parenthetical("") is None
    assert extract_parenthetical(None) is None


def test_split_preserves_order_and_count():
    components = split_scientific_name(
        "CHLORPHENIRAMINE+PARACETAMOL(ACETAMINOPHEN)+PSEUDOEPHEDRINE"
    )
    assert components == [
        "CHLORPHENIRAMINE",
        "PARACETAMOL(ACETAMINOPHEN)",
        "PSEUDOEPHEDRINE",
    ]


def test_split_trims_and_drops_empties():
    assert split_scientific_name(" ABACAVIR + +LAMIVUDINE ") == ["ABACAVIR", "LAMIVUDINE"]


def test_split_deduplicates_preserving_order():
    assert split_scientific_name("PARACETAMOL+CAFFEINE+PARACETAMOL") == [
        "PARACETAMOL",
        "CAFFEINE",
    ]


def test_split_empty_input():
    assert split_scientific_name(None) == []
    assert split_scientific_name("") == []

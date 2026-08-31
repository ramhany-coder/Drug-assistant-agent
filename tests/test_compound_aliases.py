from agents.compound_mapper.compound_aliases import canonicalize


def test_salt_suffix_is_stripped():
    assert canonicalize("Abacavir Sulphate") == "abacavir"
    assert canonicalize("ABACAVIR") == "abacavir"


def test_alias_reaches_the_same_form_from_either_direction():
    assert canonicalize("ACETAMINOPHEN") == canonicalize("PARACETAMOL") == "paracetamol"


def test_vitamin_trivial_name_alias():
    assert canonicalize("VITAMIN C") == "ascorbic acid"


def test_whitespace_is_collapsed_before_the_alias_lookup():
    assert canonicalize("  VITAMIN   C  ") == "ascorbic acid"


def test_empty_input_returns_empty_string():
    assert canonicalize("") == ""
    assert canonicalize(None) == ""


def test_salt_suffix_alone_is_not_stripped_to_nothing():
    # A one-word compound that happens to collide with a suffix word must not
    # canonicalize to an empty string.
    assert canonicalize("Sodium") == "sodium"

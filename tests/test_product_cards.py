from agents.product_cards.product_cards import CARD_FIELDS, INTRO_TEMPLATES, product_cards

ROWS = [
    {"commercial_name_en": "PANADOL EXTRA", "commercial_name_ar": "بانادول اكسترا",
     "scientific_name": "PARACETAMOL+CAFFEINE", "manufacturer": "GSK", "drug_class": "ANALGESIC",
     "route": "ORAL.SOLID", "price_egp": 20.0},
    {"commercial_name_en": "PANADOL COLD", "scientific_name": "PARACETAMOL", "price_egp": 35.0},
]


def test_one_card_per_row_with_every_card_field():
    result = product_cards({"context": ROWS, "user_language": "english"})
    assert len(result["cards"]) == 2
    assert all(set(card) == set(CARD_FIELDS) for card in result["cards"])
    assert result["cards"][0]["price_egp"] == 20.0
    assert result["cards"][1]["manufacturer"] is None


def test_intro_is_in_the_users_language_with_the_count():
    result = product_cards({"context": ROWS, "user_language": "egyptian_arabic"})
    assert result["response"] == INTRO_TEMPLATES["egyptian_arabic"].format(count=2)


def test_unknown_language_falls_back_to_english():
    result = product_cards({"context": ROWS, "user_language": "mixed"})
    assert result["response"] == INTRO_TEMPLATES["english"].format(count=2)


def test_never_flags_academic():
    assert product_cards({"context": ROWS})["is_academic"] is False


def _names(result):
    return [card["commercial_name_en"] for card in result["cards"]]


PANADOL_ROWS = [
    {"commercial_name_en": "PANADOL EXTRA 24 F.C.TABS.", "commercial_name_ar": "بانادول اكسترا",
     "scientific_name": "PARACETAMOL(ACETAMINOPHEN)+CAFFEINE", "price_egp": 30.0},
    {"commercial_name_en": "PANADOL COLD & FLU 24 TABS.", "commercial_name_ar": "بانادول كولد اند فلو",
     "scientific_name": "PARACETAMOL+PSEUDOEPHEDRINE", "price_egp": 40.0},
    {"commercial_name_en": "PANADOL 24 TABS.", "commercial_name_ar": "بانادول",
     "scientific_name": "PARACETAMOL", "price_egp": 20.0},
]


def test_closest_name_ranks_first():
    result = product_cards({"context": PANADOL_ROWS, "commercial_name_en": "PANADOL"})
    assert _names(result)[0] == "PANADOL 24 TABS."


def test_line_extension_named_in_the_query_ranks_first():
    result = product_cards({"context": PANADOL_ROWS, "commercial_name_en": "PANADOL EXTRA"})
    assert _names(result)[0] == "PANADOL EXTRA 24 F.C.TABS."


def test_arabic_name_ranks_with_the_searchs_normalisation():
    # أ vs ا: the search unifies them, so the ranking must too.
    result = product_cards({"context": PANADOL_ROWS, "commercial_name_ar": "بأنادول اكسترا"})
    assert _names(result)[0] == "PANADOL EXTRA 24 F.C.TABS."


def test_single_ingredient_product_ranks_above_combinations():
    result = product_cards({"context": PANADOL_ROWS, "scientific_name": "PARACETAMOL"})
    assert _names(result)[0] == "PANADOL 24 TABS."


def test_every_named_field_counts_towards_relevance():
    rows = [
        {"commercial_name_en": "AMOXICILLIN PHARMA", "scientific_name": "SOME OTHER INGREDIENT"},
        {"commercial_name_en": "AMOXICILLIN", "scientific_name": "AMOXICILLIN"},
    ]
    result = product_cards({"context": rows, "commercial_name_en": "AMOXICILLIN", "scientific_name": "AMOXICILLIN"})
    assert _names(result)[0] == "AMOXICILLIN"


def test_price_sort_keeps_the_filters_price_order():
    by_price = sorted(PANADOL_ROWS, key=lambda row: row["price_egp"], reverse=True)
    result = product_cards({"context": by_price, "commercial_name_en": "PANADOL", "price_egp": "desc"})
    assert [card["price_egp"] for card in result["cards"]] == [40.0, 30.0, 20.0]


def test_no_named_field_keeps_the_filters_order():
    result = product_cards({"context": PANADOL_ROWS, "route": "ORAL.SOLID"})
    assert _names(result) == [row["commercial_name_en"] for row in PANADOL_ROWS]

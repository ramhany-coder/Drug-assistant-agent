import time
from pathlib import Path

from agents.meta_data_fiter.search_engine import MedicineSearchEngine

engine = MedicineSearchEngine(search_fields=["commercial_name_en", "commercial_name_ar"])

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "egyptian-drugs.json"

# Built once at import time (not per test) so the BM25 indices are warm before any
# test runs against them, matching how they'll be used in production.
commercial_engine = MedicineSearchEngine(
    search_fields=[
        "commercial_name_en",
        "commercial_name_ar",
        "scientific_name",
        "manufacturer",
        "drug_class",
    ]
)
commercial_engine.load_data(str(DATA_PATH))


def normalize(text):
    return engine._normalize_text(text)


def test_casefolds_and_collapses_whitespace():
    assert normalize("  Panadol   Extra  ") == "panadol extra"


def test_keeps_digits_in_brand_names():
    assert normalize("1 2 3") == "1 2 3"
    assert normalize("2HC") == "2hc"


def test_converts_arabic_indic_digits():
    assert normalize("١٢٣") == "123"


def test_strips_tashkeel_and_dagger_alef():
    assert normalize("بَنَادُوْل") == normalize("بنادول")
    assert normalize("قُرْآن") == normalize("قران")


def test_strips_tatweel():
    assert normalize("بندول") == normalize("بنـــدول")


def test_unifies_alef_forms():
    assert normalize("أوجمنتين") == normalize("اوجمنتين")
    assert normalize("إوجمنتين") == normalize("اوجمنتين")
    assert normalize("آوجمنتين") == normalize("اوجمنتين")


def test_unifies_ya_and_alef_maksura():
    assert normalize("كتافلى") == normalize("كتافلي")


def test_unifies_ta_marbuta():
    assert normalize("جرعة") == normalize("جرعه")


def test_unifies_hamza_carriers_and_drops_standalone_hamza():
    assert normalize("مؤتمر") == normalize("موتمر")
    assert normalize("مسئول") == normalize("مسيول")
    assert normalize("جزء") == normalize("جز")


def test_egyptian_transliteration_letters():
    assert normalize("ڤولتارين") == normalize("فولتارين")
    assert normalize("چلوكوفاج") == normalize("جلوكوفاج")
    assert normalize("پانادول") == normalize("بانادول")
    assert normalize("گلوكوفاج") == normalize("كلوكوفاج")


def test_strips_pack_noise_words():
    assert normalize("PANADOL 20 TABS") == "panadol 20"
    assert normalize("AUGMENTIN 1 GM F.C.TABS.") == "augmentin 1"
    assert normalize("CATAFLAM 50 MG SUSP.") == "cataflam 50"


def test_strips_parenthetical_spellouts():
    assert normalize("1 2 3 (ONE TWO THREE) 20 F.C.TABS.") == "1 2 3 20"


def test_keeps_line_extensions():
    for word in ("extra", "forte", "plus", "sr", "retard"):
        normalized = normalize(f"PANADOL {word}")
        assert word in normalized, f"{word!r} was stripped but is a real line extension"


def test_drops_punctuation_but_keeps_digits_and_spaces():
    assert normalize("CO-AMOXICLAV, 1G.") == "coamoxiclav 1g"


def test_empty_and_none_input():
    assert normalize("") == ""
    assert normalize(None) == ""


def ngrams(text, n=3):
    return engine._generate_char_ngrams(text, n)


def test_trigrams_pad_word_boundaries():
    assert ngrams("panadol", 3) == [
        "$$p", "$pa", "pan", "ana", "nad", "ado", "dol", "ol$", "l$$",
    ]


def test_bigrams_pad_word_boundaries():
    assert ngrams("hc", 2) == ["$h", "hc", "c$"]


def test_ngrams_generated_per_word_not_across_words():
    combined = ngrams("panadol extra", 3)
    assert combined == ngrams("panadol", 3) + ngrams("extra", 3)
    assert "l$$" in combined and "$$e" in combined
    assert "l e" not in combined and "le$" not in combined


def test_short_word_still_produces_tokens():
    assert ngrams("a", 3) != []
    assert ngrams("hc", 3) != []


def test_tokenize_for_index_combines_bigrams_and_trigrams():
    combined = engine._tokenize_for_index("hc")
    assert combined == ngrams("hc", 2) + ngrams("hc", 3)


def top_name(hit):
    return hit["record"]["commercial_name_en"]


def test_latin_typos_return_the_right_brand_first():
    cases = {
        "panadoll": "PANADOL",
        "augmantin": "AUGMENTIN",
        "glucophag": "GLUCOPHAGE",
        "cataflm": "CATAFLAM",
    }
    for query, expected_brand in cases.items():
        hits = commercial_engine.search(query, top_k=3)
        assert hits, f"no hits for {query!r}"
        assert expected_brand in top_name(hits[0]).upper()


def test_arabic_typos_return_the_right_brand_first():
    # Compared post-normalisation, not against raw catalogue text: the real records
    # spell these with a hamza-carrying alef (أوجمينتين) that only normalisation
    # unifies with the plain-alef query.
    cases = {
        "كتافلم": "كاتافلام",
        "اوجمنتين": "اوجمينتين",
    }
    for query, expected_substring in cases.items():
        hits = commercial_engine.search(query, top_k=3)
        assert hits, f"no hits for {query!r}"
        normalized_expected = normalize(expected_substring)
        assert any(
            normalized_expected in normalize(h["record"]["commercial_name_ar"]) for h in hits
        )


def test_known_limitation_ambiguous_typo_may_rank_a_different_real_product_first():
    # "بنادولل" (a Panadol typo) is Levenshtein distance 2 from BOTH the intended
    # "بانادول" AND a real, different product "بينادول" (BIENADOL,
    # caffeine+paracetamol) -- a genuine tie under character-edit-distance alone.
    # min_score=0.75 (raised for overall precision) excludes the correct match
    # here, since it only appears in this catalogue as multi-word qualified SKUs
    # ("بانادول جوينت") that score lower against a bare-word query than the
    # plain single-word decoy does. This test pins down that known, accepted
    # trade-off so a future change to it is a deliberate decision, not a silent
    # regression -- see the min_score comment on MedicineSearchEngine.__init__.
    hits = commercial_engine.search("بنادولل", top_k=3)
    assert len(hits) == 1
    assert "بينادول" in hits[0]["record"]["commercial_name_ar"]


def test_egyptian_letter_variants_match_across_catalogue_spelling():
    voltaren_hits = commercial_engine.search("ڤولتارين", top_k=5)
    assert any("فولتارين" in h["record"]["commercial_name_ar"] for h in voltaren_hits)

    glucophage_hits = commercial_engine.search("چلوكوفاج", top_k=5)
    assert any("جلوكوفاج" in h["record"]["commercial_name_ar"] for h in glucophage_hits)


def test_digit_brands_are_findable_and_not_merged():
    one_two_three_hits = commercial_engine.search("1 2 3", top_k=5)
    assert one_two_three_hits
    assert all("2HC" not in top_name(h).upper() for h in one_two_three_hits)

    two_hc_hits = commercial_engine.search("2HC", top_k=5)
    assert two_hc_hits
    assert "2HC" in top_name(two_hc_hits[0]).upper()
    assert all("1 2 3" not in top_name(h) for h in two_hc_hits)


def test_line_extension_ranks_above_plain_product():
    hits = commercial_engine.search("1 2 3 extra", top_k=5)
    assert hits
    assert "EXTRA" in top_name(hits[0]).upper()


def test_pack_noise_matches_the_same_record_as_bare_name():
    # BM25 idf degenerates to 0 for a term appearing in exactly one of only two
    # documents, so this needs enough decoys for idf to behave normally.
    fixture = [
        {"commercial_name_en": "PANADOL 20 TABS", "commercial_name_ar": "بانادول",
         "scientific_name": "PARACETAMOL", "manufacturer": "GSK", "drug_class": "ANALGESIC",
         "route": "ORAL.SOLID", "price_egp": 20.0},
        {"commercial_name_en": "AMOXIL 500 MG CAPS", "commercial_name_ar": "اموكسيل",
         "scientific_name": "AMOXICILLIN", "manufacturer": "GSK", "drug_class": "ANTIBIOTIC",
         "route": "ORAL.SOLID", "price_egp": 15.0},
        {"commercial_name_en": "BRUFEN 400 MG TABS", "commercial_name_ar": "بروفين",
         "scientific_name": "IBUPROFEN", "manufacturer": "ABBOTT", "drug_class": "NSAID",
         "route": "ORAL.SOLID", "price_egp": 12.0},
        {"commercial_name_en": "ZANTAC 150 MG TABS", "commercial_name_ar": "زانتاك",
         "scientific_name": "RANITIDINE", "manufacturer": "GSK", "drug_class": "ANTACID",
         "route": "ORAL.SOLID", "price_egp": 18.0},
        {"commercial_name_en": "FLAGYL 500 MG TABS", "commercial_name_ar": "فلاجيل",
         "scientific_name": "METRONIDAZOLE", "manufacturer": "SANOFI", "drug_class": "ANTIBIOTIC",
         "route": "ORAL.SOLID", "price_egp": 10.0},
        {"commercial_name_en": "CONGESTAL 20 TABS", "commercial_name_ar": "كونجستال",
         "scientific_name": "PARACETAMOL+PHENYLEPHRINE", "manufacturer": "SIGMA", "drug_class": "COLD PRODUCTS",
         "route": "ORAL.SOLID", "price_egp": 9.0},
    ]
    small_engine = MedicineSearchEngine(
        search_fields=["commercial_name_en", "commercial_name_ar", "manufacturer"]
    )
    small_engine.load_data(fixture)

    bare_hits = small_engine.search("panadol", top_k=1)
    noisy_hits = small_engine.search("panadol 20 tabs", top_k=1)

    assert bare_hits and noisy_hits
    assert bare_hits[0]["record"]["commercial_name_en"] == noisy_hits[0]["record"]["commercial_name_en"]


def test_exact_match_finds_a_superset_not_just_a_full_string_equal_value():
    hits = commercial_engine.exact_match("panadol", top_k=5)
    assert hits
    assert all(hit["score"] == 1.0 for hit in hits)
    assert any("PANADOL" in top_name(h) for h in hits)


def test_exact_match_is_word_based_not_substring_based():
    # "panado" is a substring of "panadol" but not a whole word -- exact_match
    # must not match on partial words the way a naive substring check would.
    assert commercial_engine.exact_match("panado", top_k=5) == []


def test_exact_match_returns_nothing_for_a_typo():
    # "extre" never appears as a literal word anywhere in the catalogue -- this
    # is exactly the case search() (fuzzy) exists to rescue, not exact_match.
    assert commercial_engine.exact_match("panadol extre", top_k=5) == []


def test_exact_match_respects_script_routing():
    hits = commercial_engine.exact_match("بنادول", top_k=10)
    assert all(hit["matched_field"] == "commercial_name_ar" for hit in hits)


def test_script_routing_arabic_query_never_matches_english_field():
    hits = commercial_engine.search("بنادول", top_k=10)
    assert hits
    assert all(h["matched_field"] == "commercial_name_ar" for h in hits)


def test_nonsense_query_returns_empty_list():
    # A jumble avoiding real keyboard-adjacent fragments (unlike e.g. "...qwerty...",
    # which coincidentally shares "erty" with a real manufacturer, "MERTY PHARMA").
    hits = commercial_engine.search("vxqzkj fpwmbgl", top_k=5)
    assert hits == []


def test_search_completes_under_100ms_after_warmup():
    commercial_engine.search("panadoll", top_k=5)  # warm-up

    start = time.perf_counter()
    commercial_engine.search("panadoll", top_k=5)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.1, f"search took {elapsed:.3f}s"

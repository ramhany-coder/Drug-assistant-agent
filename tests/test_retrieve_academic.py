from agents.retreivale.agent import retrieve_academic


def test_attaches_monograph_per_component():
    state = {
        "compound_mappings": [
            {
                "component": "PARACETAMOL",
                "generic_name": "Paracetamol",
                "matched": True,
                "source_product": "1 2 3",
            },
            {
                "component": "PSEUDOEPHEDRINE",
                "generic_name": None,
                "matched": False,
                "source_product": "1 2 3",
            },
        ]
    }

    result = retrieve_academic(state)

    assert result["context"][1] == {
        "component": "PSEUDOEPHEDRINE",
        "generic_name": None,
        "source_product": "1 2 3",
        "monograph": None,
    }
    assert result["context"][0]["component"] == "PARACETAMOL"
    assert result["context"][0]["source_product"] == "1 2 3"


def test_generic_name_absent_from_index_yields_null_monograph_not_a_crash():
    state = {
        "compound_mappings": [
            {
                "component": "MYSTERY",
                "generic_name": "Not A Real Generic Name",
                "matched": True,
                "source_product": None,
            }
        ]
    }

    result = retrieve_academic(state)
    assert result["context"][0]["monograph"] is None


def test_no_mappings_returns_empty_context():
    assert retrieve_academic({}) == {"context": []}


def test_preserves_commercial_rows_already_in_context():
    """context has no LangGraph reducer, so retrieve_academic must append to what
    meta_data_filter already put there, not replace it -- otherwise a plain
    price/availability question loses its commercial row the moment its
    scientific_name resolves to a compound mapping."""
    state = {
        "context": [{"commercial_name_en": "1 2 3", "price_egp": 10.0}],
        "compound_mappings": [
            {
                "component": "PARACETAMOL",
                "generic_name": "Abacavir Sulphate",
                "matched": True,
                "source_product": "1 2 3",
            }
        ],
    }

    result = retrieve_academic(state)

    assert result["context"][0] == {"commercial_name_en": "1 2 3", "price_egp": 10.0}
    assert result["context"][1]["component"] == "PARACETAMOL"
    assert result["context"][1]["monograph"] is not None

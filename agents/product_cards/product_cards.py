"""Ends a turn with the matched catalogue rows as product cards and a templated
intro in the user's language -- no LLM call. GraphBuilder.build routes here
instead of early_responser when the query only asks about fields the catalogue
already holds (is_academic false) and few enough products matched to show them
all (match_count <= MAX_CONTEXT_ITEMS).

Cards are ordered most to least relevant to the query. meta_data_filter's own
order can't serve for that -- every exact_match hit scores 1.0 and each field's
hits are OR'd together -- so the rows are re-ranked here, after retrieval,
leaving the search itself untouched."""

from rapidfuzz import fuzz

from agents.meta_data_fiter.agent.helpers import is_price_sort_directive
from agents.meta_data_fiter.search_engine import MedicineSearchEngine
from models.state import State

CARD_FIELDS = (
    "commercial_name_en",
    "commercial_name_ar",
    "scientific_name",
    "manufacturer",
    "drug_class",
    "route",
    "price_egp",
)

# The text filters meta_data_extractor fills -- what the user actually named.
RELEVANCE_FIELDS = (
    "commercial_name_en",
    "commercial_name_ar",
    "scientific_name",
    "manufacturer",
    "drug_class",
)

# The search's own casefolding, Arabic letter unification and pack-noise
# stripping, so "PANADOL EXTRA" and "PANADOL EXTRA 24 F.C.TABS." compare equal.
_normalize = MedicineSearchEngine(search_fields=[])._normalize_text

INTRO_TEMPLATES = {
    "english": "Here are the products that match your search ({count}):",
    "egyptian_arabic": "دي المنتجات اللي لقيتها ({count}):",
    "msa": "إليك المنتجات المطابقة لبحثك ({count}):",
    "arabizi": "Dy el montagat elly la2etha ({count}):",
}


def _relevance(card, wanted):
    """Sum, over every field the user named, of how closely the card's value
    matches it (0-100 each). token_sort_ratio penalises extra words, so for
    "PANADOL" the plain PANADOL ranks above PANADOL EXTRA."""
    return sum(fuzz.token_sort_ratio(value, _normalize(card.get(field))) for field, value in wanted.items())


def rank_by_relevance(cards, state):
    # A price sort ("cheapest", "most expensive") is the user's own ordering, and
    # meta_data_filter has already applied it.
    if is_price_sort_directive(state.get("price_egp")):
        return cards
    wanted = {field: _normalize(state.get(field)) for field in RELEVANCE_FIELDS if state.get(field)}
    if not wanted:
        return cards
    # sorted() is stable, so equally relevant cards keep meta_data_filter's order.
    return sorted(cards, key=lambda card: _relevance(card, wanted), reverse=True)


def product_cards(state: State):
    cards = [{field: row.get(field) for field in CARD_FIELDS} for row in state.get("context") or []]
    cards = rank_by_relevance(cards, state)
    template = INTRO_TEMPLATES.get(state.get("user_language"), INTRO_TEMPLATES["english"])

    return {
        "cards": cards,
        "response": template.format(count=len(cards)),
        "is_academic": False,
    }

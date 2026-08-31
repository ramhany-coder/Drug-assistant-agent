"""Two-stage typo-tolerant search over the commercial catalogue: BM25 on character
n-grams for recall, RapidFuzz re-ranking for precision. Used for every user-sourced
metadata filter (commercial names, manufacturer, drug_class) — never for the
compound_mapper's scientific_name -> generic_name lookup, which stays on its
deterministic exact/alias/salt-suffix path in matcher.py because both sides there
are machine-generated strings with no typos to absorb.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Union

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz

# Stage-1 recall bounds: examine at most this many of the query's rarest n-grams,
# and stop growing the candidate pool once it reaches this size. Keeps
# get_batch_scores' cost independent of corpus size (see load_data's inverted index).
_MAX_QUERY_TERMS_FOR_RECALL = 12
_CANDIDATE_POOL_CAP = 1500

_WHITESPACE_RE = re.compile(r"\s+")
_TATWEEL_RE = re.compile("ـ")
_PAREN_RE = re.compile(r"\([^)]*\)")

_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Egyptian transliteration letters are listed explicitly (چ/ڤ/پ/گ) alongside the
# standard alef/hamza/ta-marbuta unifications so ڤولتارين and فولتارين normalise
# to the same string — Egyptians write both interchangeably.
_ARABIC_CHAR_MAP = str.maketrans({
    "أ": "ا",  # أ -> ا
    "إ": "ا",  # إ -> ا
    "آ": "ا",  # آ -> ا
    "ٱ": "ا",  # ٱ -> ا
    "ى": "ي",  # ى -> ي
    "ة": "ه",  # ة -> ه
    "ؤ": "و",  # ؤ -> و
    "ئ": "ي",  # ئ -> ي
    "ء": "",   # ء -> (removed)
    "چ": "ج",  # چ -> ج
    "ڤ": "ف",  # ڤ -> ف
    "پ": "ب",  # پ -> ب
    "گ": "ك",  # گ -> ك
})

# Whole-word pack-size / dosage-form noise, stripped so "PANADOL 20 TABS" and
# "PANADOL" land on the same normalised string. Line extensions (extra, forte,
# plus, sr, retard) are deliberately NOT in this list — they distinguish real
# products sold at different prices.
_PACK_NOISE_WORDS = [
    "f.c.tabs", "tablets", "capsules", "suspension", "tabs", "tab",
    "caps", "fc", "susp", "syrup", "amp", "vial", "ml", "mg", "gm",
]
_PACK_NOISE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    + "|".join(re.escape(w) for w in sorted(_PACK_NOISE_WORDS, key=len, reverse=True))
    + r")(?![A-Za-z0-9])"
)


class MedicineSearchEngine:
    # Tuned against the real catalogue (tests/test_search_engine.py). At 25k+ records
    # even a random-letter query coincidentally overlaps some field's characters
    # enough to clear 0.55-0.6; genuine typo matches, even against a catalogue entry
    # qualified with extra words (e.g. "PANADOL JOINT" for a bare "panadol" query),
    # still scored >=0.68 in testing. 0.75 favours precision: a correctly-spelled
    # query is answered by exact_match() instead (see below), so this fuzzy path
    # only ever runs as its fallback, and can afford to be stricter.
    def __init__(self, search_fields: list, n: int = 3, alpha: float = 0.4, min_score: float = 0.75):
        self.search_fields = list(search_fields)
        self.n = n
        self.alpha = alpha
        self.min_score = min_score
        self.records: list = []
        self._field_index: dict = {}

    def load_data(self, source: Union[str, list]) -> None:
        """Build one BM25 index per search field over the given records (a path to a
        JSON file, or an already-loaded list of dicts). Indexes are kept separate per
        field — never merged into one global index — so a query for a manufacturer
        can't be scored against brand names, and a record missing a field is simply
        absent from that field's index rather than indexed as an empty string.
        """
        if isinstance(source, (str, Path)):
            with open(source, "r", encoding="utf-8") as f:
                records = json.load(f)
        else:
            records = list(source)

        self.records = records
        self._field_index = {}

        for field in self.search_fields:
            record_indices = []
            normalized_values = []
            corpus_tokens = []

            for record_index, record in enumerate(records):
                raw_value = record.get(field)
                if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                    continue
                normalized_value = self._normalize_text(str(raw_value))
                if not normalized_value:
                    continue

                record_indices.append(record_index)
                normalized_values.append(normalized_value)
                corpus_tokens.append(self._tokenize_for_index(normalized_value))

            if not record_indices:
                continue

            # rank_bm25's get_scores() scans every document in the corpus for every
            # query token (a plain Python dict.get() per (token, doc) pair) — fine at
            # small scale, but ~25k records x 5 fields blows the 100ms budget. This
            # inverted index lets search() find the (usually tiny) set of positions
            # that actually share a query token, then score only those via rank_bm25's
            # own get_batch_scores(), instead of the full corpus.
            inverted = {}
            for position, tokens in enumerate(corpus_tokens):
                for token in set(tokens):
                    inverted.setdefault(token, []).append(position)

            # Word-level (not n-gram) posting lists, for exact_match()'s
            # deterministic lookup: intersecting a few short lists is far cheaper
            # than scanning every normalised value, and needs no fuzzy scoring.
            word_index = {}
            for position, normalized_value in enumerate(normalized_values):
                for word in set(normalized_value.split()):
                    word_index.setdefault(word, set()).add(position)

            self._field_index[field] = {
                "bm25": BM25Okapi(corpus_tokens),
                "record_indices": record_indices,
                "normalized_values": normalized_values,
                "inverted": inverted,
                "word_index": word_index,
            }

    def _normalize_text(self, text) -> str:
        """Casefold both scripts to one comparable form. Order matters:
        diacritics/tatweel/letter-unification must run before the parenthetical and
        pack-noise strips (which rely on plain Arabic letters and literal Latin
        substrings), and punctuation must be dropped last so it doesn't break the
        pack-noise word-boundary lookarounds (e.g. "F.C.TABS." keeps its dots until
        after "f.c.tabs" is matched and removed).
        """
        if not text:
            return ""

        normalized = str(text).casefold()
        normalized = normalized.translate(_ARABIC_INDIC_DIGITS)

        # NFKD + drop combining marks (category Mn) strips both Latin accents
        # (café -> cafe) and Arabic tashkeel/dagger-alef (ً-ْ, ٰ),
        # which are combining marks even though they're not decomposition targets.
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

        normalized = _TATWEEL_RE.sub("", normalized)
        normalized = normalized.translate(_ARABIC_CHAR_MAP)

        normalized = _PAREN_RE.sub(" ", normalized)
        normalized = _PACK_NOISE_RE.sub(" ", normalized)

        # Keep digits (1 2 3, 2HC are real brand names) and letters of any script;
        # drop everything else (hyphens, periods, commas, ...).
        normalized = "".join(ch for ch in normalized if ch.isalnum() or ch.isspace())

        normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
        return normalized

    def _generate_char_ngrams(self, text: str, n: int = 3) -> list:
        """Word-boundary-padded char n-grams (panadol -> $$panadol$$ for n=3), so a
        prefix/suffix trigram is distinct from an interior one and short words still
        yield tokens instead of nothing. Generated per word, then flattened — an
        n-gram never spans two words.
        """
        boundary = "$" * (n - 1)
        tokens = []
        for word in text.split():
            padded = f"{boundary}{word}{boundary}"
            if len(padded) < n:
                tokens.append(padded)
                continue
            tokens.extend(padded[i:i + n] for i in range(len(padded) - n + 1))
        return tokens

    def _tokenize_for_index(self, text: str) -> list:
        """The 2+n-gram combination used everywhere the engine builds or queries a
        BM25 index — bigrams alone rescue short Arabic names (بندول) that trigrams
        handle poorly, so both tiers are always concatenated together."""
        return self._generate_char_ngrams(text, 2) + self._generate_char_ngrams(text, self.n)

    def _select_fields(self, normalized_query: str) -> list:
        """Route to *_ar fields for a predominantly-Arabic query, non-*_ar fields for
        a predominantly-Latin one, or every field for a mixed/digits-only query —
        halves the work and stops e.g. an Arabic query from ever landing a hit on
        commercial_name_en."""
        arabic_letters = sum(1 for ch in normalized_query if "؀" <= ch <= "ۿ")
        latin_letters = sum(1 for ch in normalized_query if ch.isascii() and ch.isalpha())
        total_letters = arabic_letters + latin_letters

        if total_letters == 0:
            return list(self.search_fields)

        arabic_ratio = arabic_letters / total_letters
        if arabic_ratio >= 0.7:
            selected = [f for f in self.search_fields if f.endswith("_ar")]
        elif arabic_ratio <= 0.3:
            selected = [f for f in self.search_fields if not f.endswith("_ar")]
        else:
            selected = list(self.search_fields)

        return selected if selected else list(self.search_fields)

    def exact_match(self, query: str, top_k: int = 5) -> list:
        """Deterministic, no-scoring lookup: every word of the normalised query
        must appear in a field's normalised value (so "panadol" exactly finds
        "PANADOL EXTRA 24 F.C. TABS." -- a superset, not a full-string match).
        Intended as the first pass ahead of search() -- a correctly-spelled query
        is answered here without ever touching BM25 or RapidFuzz; search() (the
        fuzzy path) is meant to run only as a fallback when this returns nothing.
        Every hit scores 1.0, since there's nothing to rank -- either the words are
        all present or they aren't.
        """
        normalized_query = self._normalize_text(query)
        query_words = normalized_query.split()
        if not query_words:
            return []

        fields_to_search = self._select_fields(normalized_query)
        matched_by_record = {}
        for field in fields_to_search:
            field_index = self._field_index.get(field)
            if field_index is None:
                continue

            word_index = field_index["word_index"]
            posting_sets = [word_index.get(word) for word in query_words]
            if any(postings is None for postings in posting_sets):
                continue  # at least one query word never appears in this field at all

            positions = set.intersection(*posting_sets) if len(posting_sets) > 1 else set(posting_sets[0])
            for position in positions:
                record_index = field_index["record_indices"][position]
                if record_index in matched_by_record:
                    continue
                matched_by_record[record_index] = {
                    "record": dict(self.records[record_index]),
                    "score": 1.0,
                    "matched_field": field,
                    "matched_value": self.records[record_index].get(field),
                }

        return list(matched_by_record.values())[:top_k]

    def search(self, query: str, top_k: int = 5, candidates_limit: int = 30) -> list:
        hits = self._all_scored_hits(query, candidates_limit=candidates_limit)
        filtered = [hit for hit in hits if hit["score"] >= self.min_score]
        return filtered[:top_k]

    def best_score(self, query: str, candidates_limit: int = 30):
        """The single best raw score for `query`, ignoring min_score, or None if
        there were no candidates at all. Not part of search()'s own ranking —
        exists so the integration layer can log a query whose best match still
        fell short of min_score (see logs/low_confidence_queries.jsonl)."""
        hits = self._all_scored_hits(query, candidates_limit=candidates_limit)
        return hits[0]["score"] if hits else None

    def _all_scored_hits(self, query: str, candidates_limit: int = 30) -> list:
        """Every candidate record scored and sorted best-first, with no min_score
        cut — shared by search() (which applies the cut) and best_score() (which
        doesn't, so a near-miss can still be logged)."""
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            return []

        query_tokens = self._tokenize_for_index(normalized_query)
        unique_query_tokens = list(dict.fromkeys(query_tokens))
        fields_to_search = self._select_fields(normalized_query)

        # Stage 1 (recall): union of the top `candidates_limit` BM25 hits per field,
        # keyed by (record, field) so a record matching on two fields is scored twice.
        candidates = {}
        for field in fields_to_search:
            field_index = self._field_index.get(field)
            if field_index is None:
                continue

            bm25 = field_index["bm25"]
            inverted = field_index["inverted"]

            # Only score documents that share at least one of the query's rarest
            # (highest-idf) n-grams — a typo still shares most of a real word's
            # n-grams, so this preserves recall while keeping the candidate pool
            # (and therefore get_batch_scores' cost) small regardless of corpus size.
            # The cap only stops us from examining *more* tokens once it's crossed —
            # it must never truncate the accumulated set itself, which would slice a
            # plain Python set in arbitrary hash order and could just as easily drop
            # the true match as any decoy.
            rarest_first = sorted(unique_query_tokens, key=lambda t: bm25.idf.get(t, -1e9), reverse=True)
            candidate_positions = set()
            for token in rarest_first[:_MAX_QUERY_TERMS_FOR_RECALL]:
                if len(candidate_positions) >= _CANDIDATE_POOL_CAP:
                    break
                candidate_positions.update(inverted.get(token, ()))

            if not candidate_positions:
                continue

            candidate_list = list(candidate_positions)
            batch_scores = bm25.get_batch_scores(query_tokens, candidate_list)

            limit = min(candidates_limit, len(candidate_list))
            top_pairs = sorted(zip(candidate_list, batch_scores), key=lambda pair: pair[1], reverse=True)[:limit]

            # No score-sign filter here: BM25's idf goes uniformly negative when a
            # field's values are highly repetitive (e.g. one drug_class shared by
            # most of the catalogue), which would otherwise reject a candidate
            # before stage 2 ever gets to see that it's actually a perfect fuzzy
            # match. Membership in candidate_positions (sharing a real n-gram with
            # the query) is already the meaningful signal; min-max normalisation
            # below still ranks these sensibly relative to each other.
            for position, bm25_score in top_pairs:
                record_index = field_index["record_indices"][position]
                candidates[(record_index, field)] = {
                    "bm25": float(bm25_score),
                    "normalized_value": field_index["normalized_values"][position],
                }

        if not candidates:
            return []

        # Stage 2 (precision): RapidFuzz against the normalised raw field value (not
        # the n-grams), combined with the BM25 recall score.
        bm25_values = [c["bm25"] for c in candidates.values()]
        bm25_min, bm25_max = min(bm25_values), max(bm25_values)
        bm25_span = bm25_max - bm25_min

        best_per_record = {}
        for (record_index, field), data in candidates.items():
            bm25_norm = 0.0 if bm25_span == 0 else (data["bm25"] - bm25_min) / bm25_span
            normalized_value = data["normalized_value"]
            fuzz_score = max(
                fuzz.WRatio(normalized_query, normalized_value),
                fuzz.token_sort_ratio(normalized_query, normalized_value),
            )
            final_score = self.alpha * bm25_norm + (1 - self.alpha) * (fuzz_score / 100.0)

            # Dedup by record: keep the higher score and remember which field won.
            current_best = best_per_record.get(record_index)
            if current_best is None or final_score > current_best["score"]:
                best_per_record[record_index] = {
                    "score": final_score,
                    "matched_field": field,
                    "matched_value": self.records[record_index].get(field),
                }

        hits = [
            {
                "record": dict(self.records[record_index]),
                "score": best["score"],
                "matched_field": best["matched_field"],
                "matched_value": best["matched_value"],
            }
            for record_index, best in best_per_record.items()
        ]

        hits.sort(key=lambda hit: hit["score"], reverse=True)
        return hits


if __name__ == "__main__":
    _DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "egyptian-drugs.json"

    engine = MedicineSearchEngine(search_fields=["commercial_name_en", "commercial_name_ar"])
    engine.load_data(str(_DATA_PATH))

    queries = [
        "panadoll",
        "بنادولل",
        "augmantin",
        "كتافلم",
        "ڤولتارين",
        "1 2 3 extra",
    ]
    for q in queries:
        for hit in engine.search(q, top_k=3):
            print(q, "->", hit["matched_value"], round(hit["score"], 3), hit["matched_field"])

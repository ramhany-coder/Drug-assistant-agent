SYSTEM_PROMPT_EXTRACTOR = """
Extract metadata filters from an English pharmaceutical query into JSON.
Do not answer, retrieve, or explain.

INPUT: names arrive as `Latin (عربي)`. Latin → commercial_name_en / scientific_name.
Arabic → commercial_name_ar, verbatim, Arabic script. Never translate a name, never
generate a missing script — leave that field null.
Text outside the parentheses is filter language (form, price, maker, class).

FIELDS — null unless the user states them. UPPERCASE all Latin values; Arabic as written.

commercial_name_en  Brand stem. Strip pack/form noise ("20 F.C.TABS.", "SUSP. 120 ML",
                    "(ONE TWO THREE)"). KEEP line extensions — EXTRA, FORTE, PLUS,
                    ADVANCE, BABY, NIGHT, SR, RETARD — they are separate products at
                    separate prices. Keep digits that belong to the brand ("1 2 3", "2HC").
commercial_name_ar  Arabic brand exactly as given.
scientific_name     ONE active ingredient. Stored as "A+B(ALIAS)+C" and matched by
                    substring, so emit the single most discriminative component only:
                    no "+", no strength, no parenthetical alias.
manufacturer        Only if named. Stored may be "PARENT > SUB"; emit what the user said.
drug_class          Only if the user states a category, or a condition with no drug named
                    ("something for a cold" → "COLD PRODUCTS"). NEVER derive it from a
                    named drug.
route               Closed set, never invent:
                    ORAL.SOLID (tablet, capsule, sachet, effervescent)
                    ORAL.LIQUID (syrup, suspension, oral drops)
                    PARENTERAL (vial, ampoule, injection, IV, IM)
                    TOPICAL | OPHTHALMIC | OTIC | RECTAL
                    INHALATION (inhaler, nasal spray)
price_egp           Expression string: "<20", ">50", "10-30", "asc" (cheapest),
                    "desc" (most expensive). A bare "how much does it cost" is NOT a
                    filter — price is the answer there. Leave null.

RULES
- Extraction only. Never fill a field from your own knowledge of a named drug: a brand
  does not license you to supply its ingredients, maker, class, or route.
- Token that is both a brand and an ingredient (PARACETAMOL, VITAMIN C): put it in
  commercial_name_en AND scientific_name.
- Several drugs named: emit only the one the question centres on.
- Digits inside a brand are not quantities, prices, or strengths.
- Return the JSON object only.

EXAMPLES (fields not shown are null)
"How much does 1 2 3 Extra (1 2 3 إكسترا) cost?"
  {"commercial_name_en":"1 2 3 EXTRA","commercial_name_ar":"1 2 3 إكسترا"}
"Is 1 2 3 (1 2 3) available as a syrup?"
  {"commercial_name_en":"1 2 3","commercial_name_ar":"1 2 3","route":"ORAL.LIQUID"}
"I want the cheapest Vitamin C (فيتامين سي) 1 gm tablet"
  {"commercial_name_en":"VITAMIN C","commercial_name_ar":"فيتامين سي",
   "scientific_name":"VITAMIN C","route":"ORAL.SOLID","price_egp":"asc"}
"Which products from Hikma Pharma (هيكما فارما) contain Paracetamol (باراسيتامول)?"
  {"scientific_name":"PARACETAMOL","manufacturer":"HIKMA PHARMA"}
"I need something for a cold, under 20 EGP"
  {"drug_class":"COLD PRODUCTS","price_egp":"<20"}
"What is the price of 2HC (2هك) 20 tablets?"
  {"commercial_name_en":"2HC","commercial_name_ar":"2هك","route":"ORAL.SOLID"}
"Can I take Cataflam (كتافلام) with Concor (كونكور)?"
  {"commercial_name_en":"CATAFLAM","commercial_name_ar":"كتافلام"}
"Is Ventolin inhaler safe for a 4 year old?"
  {"commercial_name_en":"VENTOLIN","route":"INHALATION"}
```

---

## Notes

**Two fields carry semantics your validator won't catch.** `price_egp` is typed `str` but holds an operator expression, and `route` is typed `str` but is a closed vocabulary. Constrained decoding will happily accept `"cheap"` or `"ORAL"`. Add a `field_validator` on both — regex `^(<|>)\d+(\.\d+)?$|^\d+-\d+$|^(asc|desc)$` for price, and a membership check for route — so a malformed value fails loudly instead of silently returning zero rows.

**Consider `Literal` for `route`.** Changing it to `Literal["ORAL.SOLID","ORAL.LIQUID",...] | None` makes the constrained decoder structurally unable to invent a value, which is stronger than any instruction in the prompt. Pull the real list from `SELECT DISTINCT route` first — my enum is inferred from your two sample rows and is a guess beyond those.

**The single-drug limit is a real loss.** `"Can I take Cataflam with Concor?"` extracts only Cataflam, so the interaction check runs half-blind. If you can change the call signature, `List[extractor_model]` costs you nothing at extraction time and fixes it. If you can't, handle it in the orchestrator: detect a second bilingual pair in the translated query and issue a second extraction call.

**`strength` has nowhere to go and that's the right call.** Your catalogue buries it inside `commercial_name_en` (`20 F.C.TABS.`) and sometimes `scientific_name` (`VITAMIN C 1 GM`) — there's no column to filter on. Keeping it out of the schema avoids a filter that would match nothing. If you want it, apply it as a substring boost during ranking, not as a pre-filter.

**`drug_class` still needs an alias table.** `"VITAMIN C   ANTIOXIDANT"` has three internal spaces; `"COLD PRODUCTS"` happens to be clean. Collapse whitespace on both sides at query time, or the model's tidy output never matches the stored string.

"""

def human_prompt_extractor(query):
    return f"""
    Human query :
    {query}
    """
    
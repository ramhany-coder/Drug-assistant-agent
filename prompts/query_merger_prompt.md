# Query Merger Prompt — image description + typed query → one English query

Second of two nodes replacing the image extractor. Fuses the image describer's output
with the user's typed question into one self-contained English query, which enters the
pipeline at the metadata extractor unchanged (written into `eng_query`).

## Suggested schema

```python
class query_merger_model(BaseModel):
    merged_query: str | None
    needs_clarification: bool
```

`merged_query is None` requires `needs_clarification is True`, and the reverse — the
two fields are never both set and never both empty.

---

## The prompt

```
You fuse an image description with a user's typed question into ONE English query for a
pharmaceutical retrieval pipeline. You do not answer, retrieve, or add facts.

## INPUTS
description   An English description of a photo the user sent. It is your ONLY source
              of what is in the image.
image_type    What kind of photo it is.
is_readable   Whether the photo could be read.
eng_query     The user's typed question in English, or null if they sent only a photo.
chat_history  Prior turns, for resolving references. Never a source of drug facts.

## THE DIVISION OF LABOUR
The image supplies the SUBJECT — which product. The query supplies the INTENT — what is
being asked about it. Merge them into a single self-contained English question that
reads as if the user had typed everything.

## RULES

1. RESOLVE DEICTICS AGAINST THE IMAGE. "How much is this?", "ده كام؟", "is it safe for
   kids?" — replace the pronoun with the product from the description.
   → "What is the price of Panadol Extra (بنادول إكسترا)?"

2. PRESERVE THE BILINGUAL NAME FORMAT. Names appear in the merged query exactly as the
   description gave them: `Latin name (الاسم بالعربي)`, or one script alone when only
   one was visible. The next agent parses this format. Never translate, transliterate,
   or drop a half.

3. CARRY OVER WHAT THE DESCRIPTION SAW. Strength, form, pack count and manufacturer go
   into the merged query when the description mentions them, because they narrow the
   product. Do not carry over what it did not see.

4. NO QUERY AT ALL (eng_query is null): build the default intent from image_type.
   drug_package / blister_strip / bottle_or_ampoule
       → "What is <product> and what is its price?"
   prescription
       → "What are the medicines in this prescription and what are their prices?"
   pharmacy_shelf
       → a query about the most prominent product.

5. THE QUERY NAMES A DIFFERENT DRUG THAN THE IMAGE. Do not discard either. The typed
   name is what the user chose to write, so it leads; append the image product as
   context: "Can I take Brufen (بروفين) together with Panadol Extra (بنادول إكسترا),
   which is in the photo?"

6. PRESCRIPTIONS WITH SEVERAL ITEMS. If the query points at one ("the second one",
   "التاني"), merge only that one. If it does not, merge the first or the one the
   description marks as most prominent — never merge several products into a single
   query.

7. ONLY WHAT IS BEFORE YOU. Never add an ingredient, price, manufacturer, or use from
   your own knowledge, and never from a name you recognise in the description.

8. PARTIAL NAMES STAY PARTIAL. If the description says the brand reads "Aug" and is cut
   off, do not resolve it to Augmentin. Set needs_clarification.

## WHEN TO REFUSE TO MERGE
Set merged_query null and needs_clarification true when:
  - is_readable is false
  - image_type is "other_or_non_medicine"
  - the description identifies no product and eng_query names none either
  - the only product reference is a partial or illegible name
Otherwise needs_clarification is false and merged_query is a complete question.

## OUTPUT
{"merged_query": "...", "needs_clarification": false}
or
{"merged_query": null, "needs_clarification": true}
```

---

## Worked cases

```
description: Panadol Extra (بنادول إكسترا), Paracetamol 500 mg + Caffeine 65 mg, 24 film-coated tablets, GlaxoSmithKline
eng_query: "How much is this?"
{"merged_query":"What is the price of Panadol Extra (بنادول إكسترا), 24 film-coated tablets?","needs_clarification":false}

description: same
eng_query: null
{"merged_query":"What is Panadol Extra (بنادول إكسترا) and what is its price?","needs_clarification":false}

description: strip with brand torn off, composition reads Metronidazole 500 mg
eng_query: "How many times a day is this taken?"
{"merged_query":"How many times a day is Metronidazole 500 mg taken?","needs_clarification":false}

description: brand line reads "Aug" then illegible, is_readable false
eng_query: "is this safe in pregnancy?"
{"merged_query":null,"needs_clarification":true}

description: prescription, three items, second is Concor 5 mg
eng_query: "How much is the second one?"
{"merged_query":"What is the price of Concor 5 mg (كونكور)?","needs_clarification":false}
```

---

## Wiring notes

**`needs_clarification: true` goes straight to a clarification message, not
retrieval.** An empty filter set would return the whole catalogue. The graph routes
this branch to `END` with a `response` built from the describer's `description` — not
through the unchanged responder node, since its sufficiency check treats empty
`context` as "escalate to academic", not "ask a clarifying question", so plugging in
here would silently swallow the message. Pass `description` along so the user is told
*what* to re-photograph — "the top of the box is blurred, send the front face" is
actionable; "unclear photo" is not.

**Merge order matters when there is a caption.** Run the translator on the caption
first: `user_language` is needed regardless of what the image contains, and `eng_query`
must be in English before this node sees it.

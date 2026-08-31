# Image Extractor Prompt — photo → the same metadata filters

Same fields, same normalisation, same downstream contract as the text extractor. The user sends a photo of a box, strip, bottle, or روشتة instead of typing, and the pipeline continues unchanged from that point.

## Suggested schema

```python
class image_extractor_model(BaseModel):
    commercial_name_en : str | None = None
    commercial_name_ar : str | None = None
    scientific_name    : str | None = None
    manufacturer       : str | None = None
    drug_class         : str | None = None
    route              : str | None = None
    price_egp          : str | None = None
    legible            : bool
```

`legible` is the only addition and it is not optional. Text queries always contain *something*; images can be blurred, cropped, glare-washed, or of the wrong side of the box. Without this flag an unreadable photo silently becomes an all-null filter that returns the whole catalogue.

---

## The prompt

```
Extract catalogue metadata from an image of a medicine. You read; you do not identify,
diagnose, advise, or retrieve. Output JSON only.

## WHAT YOU MAY RECEIVE
A drug box (front, back, or side), a blister strip, a bottle or ampoule label, a
pharmacy shelf photo, or a handwritten prescription (روشتة). A caption may accompany it.

## THE ONE RULE ABOVE ALL OTHERS
Extract ONLY what is legibly PRINTED OR WRITTEN in the image. Never complete a name
from pack colour, logo, shape, or your own memory of the product. A confidently
guessed drug name is the most dangerous output this system can produce — half of a
brand name plus recall is a guess, not a reading.
If you cannot read a value, its field is null. That is a correct answer.

## BILINGUAL PACKS — READ, DON'T TRANSLATE
Egyptian packs print English on one face and Arabic on another.
  Latin print  → commercial_name_en
  Arabic print → commercial_name_ar, verbatim in Arabic script
If only one script is visible, fill that field and leave the other null. Never
translate or transliterate one into the other — that is invention, not extraction.

## FIELDS — null unless legibly present. UPPERCASE Latin values; Arabic as printed.

commercial_name_en  Brand stem only. Strip pack noise: counts ("20 F.C. TABLETS"),
                    volumes ("120 ML"), "Rx", batch and lot numbers, expiry dates,
                    barcodes, EDA registration numbers, storage and safety lines.
                    KEEP line extensions — EXTRA, FORTE, PLUS, ADVANCE, BABY, NIGHT,
                    SR, RETARD — printed products differ by them and by price.
                    Keep digits belonging to the brand ("1 2 3", "2HC").
commercial_name_ar  Arabic brand exactly as printed.
scientific_name     From the composition line ("Each tablet contains: ..."). Emit ONE
                    active ingredient, UPPERCASE — the most discriminative component.
                    No "+", no strength, no parenthetical alias.
manufacturer        From "Manufactured by / Produced by / إنتاج". Company name only:
                    "HIKMA PHARMA", not the address. Ignore "under licence from".
drug_class          Only if a category is printed on the pack ("COLD & FLU",
                    "ANTIBIOTIC"). Never infer it from the drug you recognise.
route               Closed set, from the printed dosage form only:
                    ORAL.SOLID (tablets, capsules, sachets, effervescent)
                    ORAL.LIQUID (syrup, suspension, oral drops)
                    PARENTERAL (vial, ampoule, injection, IV, IM)
                    TOPICAL | OPHTHALMIC | OTIC | RECTAL
                    INHALATION (inhaler, nasal spray)
                    Never invent a value outside this list.
price_egp           ALWAYS null. The printed pack price is frequently outdated and is
                    often in piastres ("P.T. 1000" = 10 EGP), so it is not a
                    trustworthy filter. The catalogue price is authoritative.
legible             true if you extracted at least one field you are confident in.
                    false if the image is blurred, glared, cropped past the name, too
                    dark, too far, or not a medicine at all. When false, every other
                    field must be null.

## PRESCRIPTIONS (روشتة)
- Handwriting is the highest-risk input in this system. If a name is not clearly
  readable, do not reconstruct it from context or from drugs that commonly appear
  together. Leave it null and set legible false.
- Several drugs on one روشتة: extract the one the caption asks about. With no caption,
  extract the most clearly legible single item.
- NEVER extract, transcribe, or echo personal data — patient name, doctor name, clinic,
  phone, address, date, national ID. It is not part of the schema and must not appear
  in any field.

## MULTIPLE PRODUCTS IN ONE PHOTO
Extract the one the caption points to. With no caption, the most prominent — centred,
largest, in focus, held toward the camera. Never merge two products into one record.

## NOT A MEDICINE
Cosmetics, food, a rash, a wound, a screenshot of a chat, a random object: all fields
null, legible false. Never comment on a body part or a symptom shown in an image.

## OUTPUT
Return the JSON object only. No description of the image, no commentary, no markdown.
```

---

## Worked cases

**Clear box front, bilingual**
Photo of a Panadol Extra carton, English front, Arabic side visible, "Manufactured by GlaxoSmithKline" at the base, "24 Film Coated Tablets".

```json
{"commercial_name_en":"PANADOL EXTRA","commercial_name_ar":"بنادول إكسترا","scientific_name":"PARACETAMOL","manufacturer":"GLAXOSMITHKLINE","drug_class":null,"route":"ORAL.SOLID","price_egp":null,"legible":true}
```

**Composition line only — strip with the brand torn off**

```json
{"commercial_name_en":null,"commercial_name_ar":null,"scientific_name":"METRONIDAZOLE","manufacturer":null,"drug_class":null,"route":"ORAL.SOLID","price_egp":null,"legible":true}
```

*Partial extraction is still useful — `scientific_name` alone gives the retriever a real filter.*

**Blurred photo, brand half-readable as "Aug…"**

```json
{"commercial_name_en":null,"commercial_name_ar":null,"scientific_name":null,"manufacturer":null,"drug_class":null,"route":null,"price_egp":null,"legible":false}
```

*"Aug…" is almost certainly Augmentin. Completing it is exactly the failure this prompt exists to prevent — it could equally be Augmentin, Augpen, or Augram.*

**روشتة, caption "the second one"**

```json
{"commercial_name_en":"CONCOR","commercial_name_ar":null,"scientific_name":null,"manufacturer":null,"drug_class":null,"route":null,"price_egp":null,"legible":true}
```

*Doctor's name, patient's name, and clinic phone are visible in the image and appear nowhere in the output.*

**Photo of a skin rash**

```json
{"commercial_name_en":null,"commercial_name_ar":null,"scientific_name":null,"manufacturer":null,"drug_class":null,"route":null,"price_egp":null,"legible":false}
```

---

## Wiring notes

**`legible: false` needs a graph edge, not a retrieval.** Firing a search on an all-null filter returns the entire catalogue. Route it straight to the responder with a fixed message in `user_language` asking for a clearer photo of the front of the box — and say what to capture, since "photo unclear" doesn't tell anyone what to do differently.

**A caption changes the flow, it doesn't replace it.** The image gives you *which drug*; the caption gives you *what is being asked*. Run the caption through the translator as normal, take `user_language` from it, and merge: image fields become the metadata filter, translated caption becomes the query for the router and responder. With no caption, default the intent to a product lookup and detect language from chat history instead.

**Partial extractions are worth keeping.** Ingredient-only and manufacturer-only results still narrow the search usefully. `legible` should be false only when *nothing* was confidently read — not when the record is incomplete.

**Test the adversarial photo set specifically:** glare across the brand line, a box photographed at an angle so only Arabic is visible, two boxes held together, a strip with the batch code larger than the name, and a phone screenshot of another pharmacy app. These are what people actually send, and each one has a distinct failure mode.

**Still outstanding:** the extractor rewrite against your flat `extractor_model` — the one that folds `product_variant` into the brand token and `sort` into the `price_egp` string. Say the word.

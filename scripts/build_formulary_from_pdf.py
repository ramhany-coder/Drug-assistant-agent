"""Extract structured drug monographs from an Egyptian National Formulary PDF
into a JSON array matching the schema used by data/10.json.

Usage: python scripts/build_formulary_from_pdf.py <pdf_number>
       python scripts/build_formulary_from_pdf.py all
"""
import json
import re
import sys
import time
from pathlib import Path

import json_repair
import pypdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm.client import fallback_client  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FILES = {
    1: "1-new-code-antimicrobial-egyptian-national-formulary_c.pdf",
    2: "2-new-code-cardiovascular-egyptian-national-formulary_c.pdf",
    3: "3-new-code-conventional-anticancers-egyptian-national-formulary-2024_4.pdf",
    4: "4-new-code-endocrine-egyptian-national-formulary.pdf",
    5: "5-new-code-blood-diorders-egyptian-national-formulary_c.pdf",
    6: "6-nervous-system-2025.pdf",
    7: "7-targeted-medicines-formulary_2025-segl.pdf",
    8: "8-egyptian-national-drug-formulary_git-medicati.pdf",
    9: "9-respiratory-medicines-formulary-2026_.pdf",
}

TOC_LINE_RE = re.compile(
    r"^\s*(?:\d{1,3}\.\s*)?([A-Za-z][A-Za-z0-9 /\-\(\),\.\+]{2,90}?)[\.\s]{2,}(\d{1,4})\s*$"
)

MONOGRAPH_MARKERS = ("GENERIC NAME", "ATC", "DOSAGE REGIMEN", "PHARMACOLOGIC CATEGORY")

SCHEMA_TEMPLATE = """{
  "category": string or null,
  "name": string,
  "abbreviation": string or null,
  "generic_name": string or null,
  "dosage_form_strengths": [string, ...],
  "route_of_administration": string or null,
  "pharmacologic_category": string or null,
  "atc_code": string or null,
  "indications": string or null,
  "dosage_regimen": {"adult": string or null, "pediatric": string or null},
  "dosage_adjustment": {
    "renal_impairment_adult": string or null,
    "renal_impairment_pediatric": string or null,
    "hepatic_impairment_adult": string or null,
    "hepatic_impairment_pediatric": string or null
  },
  "contraindications": [string, ...],
  "adverse_drug_reactions": {"<frequency bucket as written in the text>": string, ...},
  "monitoring_parameters": string or null,
  "drug_interactions": {"risk_x_avoid_combination": [string, ...], "risk_d_consider_therapy_modification": [string, ...]},
  "pregnancy_lactation": {"pregnancy": string or null, "lactation": string or null},
  "administration": string or null,
  "warnings_precautions": [string, ...],
  "storage": string or null
}"""


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().upper()


def extract_pages(path: Path):
    reader = pypdf.PdfReader(str(path))
    return [(p.extract_text() or "") for p in reader.pages]


def get_toc_names(pages):
    names, seen = [], set()
    for text in pages:
        for line in text.splitlines():
            m = TOC_LINE_RE.match(line)
            if not m:
                continue
            name = normalize(m.group(1))
            if len(name) < 3 or name in seen:
                continue
            seen.add(name)
            names.append(name)
    return names


def find_monograph_ranges(pages, wanted_names):
    n = len(pages)
    page_lines = [[normalize(l) for l in t.splitlines() if l.strip()] for t in pages]
    wanted = set(wanted_names)
    found_at = {}
    lead_num_re = re.compile(r"^\d{1,3}[\.\)]\s*")
    for i in range(n):
        for line in page_lines[i]:
            if len(line) > 60:
                continue
            line = lead_num_re.sub("", line)
            for name in wanted:
                if name in found_at:
                    continue
                if re.fullmatch(re.escape(name) + r"\s+\d+", line):
                    continue  # TOC line ("NAME <page#>"), not a real heading
                if line == name or line.startswith(name + " "):
                    found_at[name] = i
    ranges = sorted(((name, start) for name, start in found_at.items()), key=lambda x: x[1])
    result = []
    for idx, (name, start) in enumerate(ranges):
        end = ranges[idx + 1][1] - 1 if idx + 1 < len(ranges) else n - 1
        end = min(end, start + 8)
        end = max(end, start)
        result.append((name, start, end))
    return result


def call_llm(name: str, text: str, attempts: int = 3):
    text = text[:4000]
    prompt = (
        "You extract drug monograph data from an Egyptian National Formulary PDF excerpt "
        "into strict JSON. Use ONLY information present in the excerpt below. If a field "
        "is not present, use null (or an empty list for list fields). Do not invent data. "
        "Output ONLY a single JSON object matching this shape (no markdown fences, no commentary):\n"
        f"{SCHEMA_TEMPLATE}\n\n"
        f"Drug name: {name}\n\n"
        f"Formulary excerpt:\n{text}"
    )
    last_err = None
    for i in range(attempts):
        try:
            raw = fallback_client.invoke(prompt, fallback_order=["ollama", "groq"])
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
                raw = re.sub(r"```$", "", raw).strip()
            start, end = raw.find("{"), raw.rfind("}")
            raw = raw[start : end + 1]
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                repaired = json_repair.loads(raw)
                if isinstance(repaired, dict) and repaired:
                    return repaired
                raise
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (i + 1))
    print(f"  [WARN] failed to extract '{name}': {last_err}")
    return None


WHITELIST_PATH = DATA_DIR / "EDA_Names_mapped.json"


def get_whitelist_names(num: int):
    entries = json.loads(WHITELIST_PATH.read_text(encoding="utf-8"))
    names, seen = [], set()
    for e in entries:
        if e.get("doc") != num:
            continue
        name = normalize(e["compound_name"])
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def build_one(num: int):
    pdf_path = DATA_DIR / FILES[num]
    out_path = DATA_DIR / f"{num}.json"
    print(f"[{num}] extracting text from {pdf_path.name}")
    pages = extract_pages(pdf_path)
    wanted_names = get_whitelist_names(num)
    print(f"[{num}] {len(wanted_names)} whitelisted compounds for this doc")
    ranges = find_monograph_ranges(pages, wanted_names)
    print(f"[{num}] resolved {len(ranges)} monograph page ranges")

    results = []
    if out_path.exists():
        try:
            results = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            results = []
    wanted_set = set(wanted_names)
    results = [r for r in results if normalize(r.get("name") or "") in wanted_set]
    done_names = {normalize(r.get("name") or "") for r in results}

    for name, start, end in ranges:
        if name in done_names:
            continue
        text = "\n".join(pages[start : end + 1])
        if not any(marker in normalize(text) for marker in MONOGRAPH_MARKERS):
            print(f"[{num}] skip (not a monograph page): {name}")
            continue
        obj = call_llm(name, text)
        if obj is None:
            continue
        if not obj.get("name"):
            obj["name"] = name.title()
        results.append(obj)
        for i, r in enumerate(results, start=1):
            r["id"] = i
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{num}] saved {len(results)}/{len(ranges)}: {name}")
        time.sleep(5)  # let the model fully unload (keep_alive=0s) before the next load

    print(f"[{num}] DONE -> {out_path} ({len(results)} drugs)")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    nums = list(FILES.keys()) if arg == "all" else [int(arg)]
    for num in nums:
        build_one(num)


if __name__ == "__main__":
    main()

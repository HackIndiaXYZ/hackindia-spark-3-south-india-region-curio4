"""
matcher/medicine_matcher.py
────────────────────────────
Detects medicine names in raw OCR text using:
  1. Exact key / brand-name matching
  2. RapidFuzz fuzzy matching for typos / partial OCR errors
  3. Loads the full drug DB from data/medicines.csv
"""

import os
import csv
import re
from typing import List, Dict, Any

try:
    from rapidfuzz import fuzz, process as fuzz_process
    RAPIDFUZZ = True
except ImportError:
    RAPIDFUZZ = False

# ── Load medicine database ─────────────────────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "medicines.csv")

def _load_db() -> Dict[str, Dict]:
    db = {}
    try:
        with open(_DB_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row["drug_key"].strip().lower()
                db[key] = {
                    "key":          key,
                    "generic":      row["generic_name"].strip(),
                    "brand":        [b.strip() for b in row["brand_names"].split(",")],
                    "category":     row["category"].strip(),
                    "color":        row["color"].strip(),
                    "uses":         row["uses"].strip(),
                    "dosage":       row["dosage"].strip(),
                    "side_effects": [s.strip() for s in row["side_effects"].split(",")],
                    "warnings": {
                        "pregnancy": row["warn_pregnancy"].strip().lower() == "true",
                        "liver":     row["warn_liver"].strip().lower() == "true",
                        "kidney":    row["warn_kidney"].strip().lower() == "true",
                    },
                    "interactions": [i.strip().lower() for i in row["interactions"].split(",")],
                }
    except FileNotFoundError:
        pass
    return db

MEDICINE_DB: Dict[str, Dict] = _load_db()

# ── Build lookup tokens ────────────────────────────────────────────────────
def _build_lookup():
    """
    Returns a flat list of (token, drug_key) pairs used for fuzzy matching.
    Includes drug keys + all brand name tokens.
    """
    tokens = []
    for key, med in MEDICINE_DB.items():
        tokens.append((key, key))
        for brand in med["brand"]:
            tokens.append((brand.lower(), key))
    return tokens

_LOOKUP_TOKENS = _build_lookup()
_LOOKUP_STRINGS = [t[0] for t in _LOOKUP_TOKENS]


# ── Core matcher ───────────────────────────────────────────────────────────
def match_medicines(ocr_text: str, fuzzy_threshold: int = 82) -> List[Dict[str, Any]]:
    """
    Find medicines in raw OCR text.

    Args:
        ocr_text:         Raw string extracted from OCR
        fuzzy_threshold:  Minimum RapidFuzz score (0–100) to accept a match

    Returns:
        List of matching medicine dicts from MEDICINE_DB
    """
    if not ocr_text.strip():
        return []

    # Normalise text: lowercase, strip punctuation except hyphens
    cleaned = re.sub(r"[^a-z0-9\s\-]", " ", ocr_text.lower())
    words = cleaned.split()

    found_keys = set()

    # ── Pass 1: exact substring matching ──────────────────────────────────
    for key, med in MEDICINE_DB.items():
        if key in cleaned:
            found_keys.add(key)
            continue
        for brand in med["brand"]:
            if brand.lower() in cleaned:
                found_keys.add(key)
                break

    # ── Pass 2: word-level fuzzy matching (for OCR typos) ─────────────────
    if RAPIDFUZZ:
        # Check each individual word and bigram
        candidates = set(words)
        for i in range(len(words) - 1):
            candidates.add(f"{words[i]} {words[i+1]}")

        for candidate in candidates:
            if len(candidate) < 4:
                continue
            results = fuzz_process.extract(
                candidate,
                _LOOKUP_STRINGS,
                scorer=fuzz.ratio,
                limit=3
            )
            for match_str, score, idx in results:
                if score >= fuzzy_threshold:
                    _, drug_key = _LOOKUP_TOKENS[idx]
                    found_keys.add(drug_key)
    else:
        # Simple startswith fallback when rapidfuzz is unavailable
        for word in words:
            if len(word) < 5:
                continue
            for key in MEDICINE_DB:
                if key.startswith(word[:5]) or word.startswith(key[:5]):
                    found_keys.add(key)

    return [MEDICINE_DB[k] for k in found_keys if k in MEDICINE_DB]


def get_medicine(drug_key: str) -> Dict | None:
    return MEDICINE_DB.get(drug_key.lower())


def reload_db():
    """Hot-reload the CSV database (useful during development)."""
    global MEDICINE_DB, _LOOKUP_TOKENS, _LOOKUP_STRINGS
    MEDICINE_DB = _load_db()
    _LOOKUP_TOKENS = _build_lookup()
    _LOOKUP_STRINGS = [t[0] for t in _LOOKUP_TOKENS]


# ── CLI test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = """
    Patient: John Doe
    Metformin 500mg twice daily
    Atorvastatin 20mg at bedtime
    Lisinopril 10mg once daily
    Aspirin 75mg once daily
    Omeprazole 20mg before breakfast
    """
    results = match_medicines(sample)
    for m in results:
        print(f"  ✓ {m['generic']} ({m['category']})")

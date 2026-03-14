"""
interaction/interaction_checker.py
────────────────────────────────────
Checks all pairs of detected medicines against the interactions.csv database
and returns structured alerts with severity levels.
"""

import os
import csv
from itertools import combinations
from typing import List, Dict, Any

# ── Load interactions database ─────────────────────────────────────────────
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "interactions.csv")

def _load_interactions() -> Dict[str, Dict]:
    """
    Returns a dict keyed by canonical pair string "drug_a+drug_b" (sorted).
    """
    pairs = {}
    try:
        with open(_DB_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                a = row["drug_a"].strip().lower()
                b = row["drug_b"].strip().lower()
                key = "+".join(sorted([a, b]))
                pairs[key] = {
                    "drugs":    [a, b],
                    "severity": row["severity"].strip().upper(),
                    "message":  row["message"].strip(),
                }
    except FileNotFoundError:
        pass
    return pairs

INTERACTION_DB: Dict[str, Dict] = _load_interactions()

# Severity sort order for UI display
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}


# ── Core checker ───────────────────────────────────────────────────────────
def check_interactions(medicines: List[Dict]) -> List[Dict[str, Any]]:
    """
    Given a list of medicine dicts (from medicine_matcher), find all
    dangerous interactions between them.

    Returns:
        Sorted list of interaction alerts:
        [
            {
                "drug_a":    "Warfarin",
                "drug_b":    "Aspirin",
                "key_a":     "warfarin",
                "key_b":     "aspirin",
                "severity":  "CRITICAL",
                "message":   "...",
                "severity_level": 0   # 0=CRITICAL, 1=HIGH, 2=MODERATE
            },
            ...
        ]
    """
    if len(medicines) < 2:
        return []

    alerts = []
    keys = [m["key"] for m in medicines]
    key_to_generic = {m["key"]: m["generic"] for m in medicines}

    for key_a, key_b in combinations(keys, 2):
        pair_key = "+".join(sorted([key_a, key_b]))
        if pair_key in INTERACTION_DB:
            interaction = INTERACTION_DB[pair_key]
            alerts.append({
                "drug_a":         key_to_generic.get(key_a, key_a.title()),
                "drug_b":         key_to_generic.get(key_b, key_b.title()),
                "key_a":          key_a,
                "key_b":          key_b,
                "severity":       interaction["severity"],
                "message":        interaction["message"],
                "severity_level": _SEVERITY_ORDER.get(interaction["severity"], 99),
            })

    # Sort by severity (CRITICAL first)
    alerts.sort(key=lambda x: x["severity_level"])
    return alerts


def get_safety_alerts(medicines: List[Dict]) -> Dict[str, List[str]]:
    """
    Returns per-group safety alerts based on medicine warnings.

    Returns:
        {
            "pregnancy": ["Warfarin", "Aspirin", ...],
            "liver":     [...],
            "kidney":    [...]
        }
    """
    groups = {"pregnancy": [], "liver": [], "kidney": []}
    for med in medicines:
        w = med.get("warnings", {})
        if w.get("pregnancy"):
            groups["pregnancy"].append(med["generic"])
        if w.get("liver"):
            groups["liver"].append(med["generic"])
        if w.get("kidney"):
            groups["kidney"].append(med["generic"])
    return groups


def get_interaction_summary(alerts: List[Dict]) -> Dict:
    """
    Return counts and top-level flags for the results summary card.
    """
    critical = sum(1 for a in alerts if a["severity"] == "CRITICAL")
    high     = sum(1 for a in alerts if a["severity"] == "HIGH")
    moderate = sum(1 for a in alerts if a["severity"] == "MODERATE")
    return {
        "total":    len(alerts),
        "critical": critical,
        "high":     high,
        "moderate": moderate,
        "safe":     len(alerts) == 0,
    }


def reload_db():
    global INTERACTION_DB
    INTERACTION_DB = _load_interactions()


# ── CLI test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from matcher.medicine_matcher import match_medicines
    text = "Warfarin 5mg, Aspirin 75mg, Amiodarone 200mg, Simvastatin 40mg"
    meds = match_medicines(text)
    alerts = check_interactions(meds)
    safety = get_safety_alerts(meds)
    print(f"\nFound {len(alerts)} interactions:")
    for a in alerts:
        print(f"  [{a['severity']}] {a['drug_a']} + {a['drug_b']}: {a['message']}")
    print(f"\nSafety alerts:")
    for group, names in safety.items():
        if names:
            print(f"  {group}: {', '.join(names)}")

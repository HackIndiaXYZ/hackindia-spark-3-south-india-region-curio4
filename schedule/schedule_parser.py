"""
schedule/schedule_parser.py
────────────────────────────
Parses dosage schedule instructions from OCR text and returns
structured daily schedules per medicine.

Handles patterns like:
  "twice daily", "TID", "BD", "OD", "every 8 hours",
  "morning", "bedtime", "before breakfast", "after meals"
"""

import re
from typing import List, Dict, Any, Optional


# ── Frequency patterns → times per day + schedule labels ──────────────────
FREQ_PATTERNS = [
    # Pattern               times/day  labels
    (r'\b(?:QID|four times daily|4 times)\b',       4, ["8 AM", "12 PM", "6 PM", "10 PM"]),
    (r'\b(?:TID|three times daily|3 times|thrice)\b',3, ["8 AM", "2 PM", "8 PM"]),
    (r'\b(?:BD|BID|twice daily|two times|12 hourly|every 12 hours)\b', 2, ["8 AM", "8 PM"]),
    (r'\b(?:OD|once daily|once a day|daily|every day)\b',              1, ["8 AM"]),
    (r'\bevery 8 hours\b',                            3, ["8 AM", "4 PM", "12 AM"]),
    (r'\bevery 6 hours\b',                            4, ["6 AM", "12 PM", "6 PM", "12 AM"]),
    (r'\bevery 4 hours\b',                            6, ["6 AM", "10 AM", "2 PM", "6 PM", "10 PM", "2 AM"]),
    (r'\bat bedtime\b|\bbedtime\b|\bat night\b|\bHS\b', 1, ["10 PM"]),
    (r'\bbefore breakfast\b|\bempty stomach\b',        1, ["7 AM"]),
    (r'\bafter breakfast\b|\bmorning\b',               1, ["9 AM"]),
    (r'\bafter lunch\b|\bnoon\b',                      1, ["1 PM"]),
    (r'\bafter dinner\b|\bevening\b',                  1, ["7 PM"]),
    (r'\bwhen needed\b|\bPRN\b|\bas needed\b|\bSOS\b', 0, ["As needed"]),
]

DURATION_PATTERNS = [
    (r'for (\d+)\s*days?',   "days"),
    (r'for (\d+)\s*weeks?',  "weeks"),
    (r'for (\d+)\s*months?', "months"),
    (r'x\s*(\d+)\s*days?',   "days"),
    (r'(\d+)\s*days?\s*course', "days"),
]

FOOD_PATTERNS = [
    (r'\bwith food\b|\bafter meals?\b|\bwith meals?\b', "Take with food"),
    (r'\bbefore meals?\b|\bbefore food\b',               "Take before meals"),
    (r'\bempty stomach\b|\bbefore breakfast\b',          "Take on empty stomach (30 min before eating)"),
    (r'\bwith water\b',                                  "Take with plenty of water"),
    (r'\bwith milk\b',                                   "Take with milk"),
]


# ── Dosage extraction ──────────────────────────────────────────────────────
def _extract_dose(text: str) -> Optional[str]:
    """Extract dosage amount from a line of text."""
    m = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:mg|mcg|ml|unit|IU|g|tablet|tab|cap|capsule)',
        text, re.IGNORECASE
    )
    return m.group(0) if m else None


def _extract_frequency(text: str) -> Dict:
    """Extract frequency info from a line of text."""
    lower = text.lower()
    for pattern, times, labels in FREQ_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return {"times_per_day": times, "schedule": labels}
    return {"times_per_day": 1, "schedule": ["As directed"]}


def _extract_duration(text: str) -> Optional[str]:
    """Extract duration string from a line of text."""
    lower = text.lower()
    for pattern, unit in DURATION_PATTERNS:
        m = re.search(pattern, lower, re.IGNORECASE)
        if m:
            return f"{m.group(1)} {unit}"
    return None


def _extract_food_instruction(text: str) -> Optional[str]:
    """Extract food-relation instruction."""
    lower = text.lower()
    for pattern, instruction in FOOD_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return instruction
    return None


# ── Main schedule parser ───────────────────────────────────────────────────
def parse_schedule(ocr_text: str, detected_medicines: List[Dict]) -> List[Dict[str, Any]]:
    """
    Parse the OCR text to find schedule information for each detected medicine.

    Args:
        ocr_text:            Full OCR text from the prescription
        detected_medicines:  List of medicine dicts from medicine_matcher

    Returns:
        List of schedule dicts:
        [
            {
                "medicine":       "Metformin",
                "key":            "metformin",
                "dose":           "500mg",
                "times_per_day":  2,
                "schedule":       ["8 AM", "8 PM"],
                "duration":       "7 days",
                "food":           "Take with food",
                "raw_line":       "Metformin 500mg twice daily with food"
            },
            ...
        ]
    """
    lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
    schedules = []

    for med in detected_medicines:
        # Find the line(s) that mention this medicine
        med_lines = []
        for line in lines:
            lower = line.lower()
            if med["key"] in lower or any(b.lower() in lower for b in med["brand"]):
                med_lines.append(line)

        if not med_lines:
            # No specific line found — use defaults
            schedules.append({
                "medicine":      med["generic"],
                "key":           med["key"],
                "dose":          None,
                "times_per_day": 1,
                "schedule":      ["As directed by doctor"],
                "duration":      None,
                "food":          None,
                "raw_line":      None,
            })
            continue

        # Use the best matching line (longest = most info)
        best_line = max(med_lines, key=len)

        freq  = _extract_frequency(best_line)
        schedules.append({
            "medicine":      med["generic"],
            "key":           med["key"],
            "dose":          _extract_dose(best_line),
            "times_per_day": freq["times_per_day"],
            "schedule":      freq["schedule"],
            "duration":      _extract_duration(best_line),
            "food":          _extract_food_instruction(best_line),
            "raw_line":      best_line,
        })

    return schedules


def build_daily_timeline(schedules: List[Dict]) -> List[Dict]:
    """
    Build a merged timeline of all medicines for a single day.
    Returns a list of {time, medicines} dicts sorted chronologically.

    Example output:
        [
            {"time": "7 AM",  "medicines": [{"name": "Levothyroxine", "dose": "100mcg"}]},
            {"time": "8 AM",  "medicines": [{"name": "Metformin", "dose": "500mg"}, ...]},
            ...
        ]
    """
    time_map: Dict[str, List] = {}

    _TIME_ORDER = [
        "7 AM","8 AM","9 AM","10 AM","11 AM","12 PM",
        "1 PM","2 PM","3 PM","4 PM","5 PM","6 PM",
        "7 PM","8 PM","9 PM","10 PM","11 PM","12 AM","2 AM",
        "As needed","As directed","As directed by doctor"
    ]

    for sched in schedules:
        for time_slot in sched["schedule"]:
            if time_slot not in time_map:
                time_map[time_slot] = []
            time_map[time_slot].append({
                "name": sched["medicine"],
                "dose": sched["dose"],
                "food": sched["food"],
            })

    # Sort by time order
    def sort_key(t):
        try:
            return _TIME_ORDER.index(t)
        except ValueError:
            return 99

    return [
        {"time": t, "medicines": time_map[t]}
        for t in sorted(time_map.keys(), key=sort_key)
    ]


# ── CLI test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json, sys
    sys.path.insert(0, "..")
    from matcher.medicine_matcher import match_medicines

    sample = """
    Metformin 500mg twice daily with food
    Atorvastatin 20mg at bedtime
    Lisinopril 10mg OD in the morning
    Aspirin 75mg once daily after breakfast
    Omeprazole 20mg before breakfast
    Amoxicillin 500mg TID for 7 days
    """
    meds = match_medicines(sample)
    schedules = parse_schedule(sample, meds)
    timeline  = build_daily_timeline(schedules)

    print("=== Per-Medicine Schedule ===")
    for s in schedules:
        print(f"  {s['medicine']}: {s['dose']} | {s['times_per_day']}x/day | {s['schedule']} | {s['food']}")

    print("\n=== Daily Timeline ===")
    for slot in timeline:
        meds_str = ", ".join(f"{m['name']} {m['dose'] or ''}" for m in slot["medicines"])
        print(f"  {slot['time']:8s} → {meds_str}")

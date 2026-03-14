"""
nlp/explanation_engine.py
──────────────────────────
Generates plain-language explanations for medicines using the Anthropic API.
Also provides offline fallback explanations from the DB fields.
"""

import os
from typing import Dict, Any, Optional

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


# ── Anthropic client (lazy) ────────────────────────────────────────────────
_client: Optional[Any] = None

def _get_client():
    global _client
    if _client is None and _ANTHROPIC_AVAILABLE:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── AI explanation ─────────────────────────────────────────────────────────
def explain_medicine_ai(medicine: Dict) -> str:
    """
    Generate a friendly plain-language explanation of a medicine using Claude.
    Falls back to a structured offline explanation if the API is unavailable.

    Args:
        medicine: A medicine dict from MEDICINE_DB

    Returns:
        A plain-language explanation string.
    """
    client = _get_client()

    if client:
        try:
            prompt = (
                f"You are a friendly pharmacist explaining medicines to a patient "
                f"with no medical background. In 3–4 simple sentences, explain "
                f"{medicine['generic']} ({medicine['category']}): what it does, "
                f"how to take it safely, and the single most important warning. "
                f"Use very plain everyday language. No bullet points — just a short "
                f"helpful paragraph."
            )
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text.strip()
        except Exception:
            pass   # fall through to offline

    return _offline_explanation(medicine)


def _offline_explanation(medicine: Dict) -> str:
    """
    Build a structured explanation from the CSV fields (no API needed).
    """
    name     = medicine["generic"]
    category = medicine["category"]
    uses     = medicine["uses"]
    dosage   = medicine["dosage"]
    effects  = ", ".join(medicine["side_effects"][:3])

    parts = [
        f"{name} is a {category.lower()} medicine. {uses}",
        f"Typical dosage: {dosage}",
    ]
    if effects:
        parts.append(f"Watch out for: {effects}.")

    warnings = []
    w = medicine.get("warnings", {})
    if w.get("pregnancy"):
        warnings.append("pregnant women")
    if w.get("liver"):
        warnings.append("people with liver disease")
    if w.get("kidney"):
        warnings.append("people with kidney disease")
    if warnings:
        parts.append(f"Extra caution needed for: {', '.join(warnings)}.")

    return " ".join(parts)


def explain_interaction_ai(drug_a: str, drug_b: str, message: str, severity: str) -> str:
    """
    Generate a plain-language explanation of a drug interaction.
    """
    client = _get_client()

    if client:
        try:
            prompt = (
                f"In 2–3 plain sentences, explain to a patient why taking "
                f"{drug_a} and {drug_b} together is dangerous ({severity} risk). "
                f"The known interaction: {message}. "
                f"Tell them what they should do. No jargon. Keep it reassuring but clear."
            )
            message_obj = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return message_obj.content[0].text.strip()
        except Exception:
            pass

    return message   # plain fallback


def batch_explain(medicines: list) -> Dict[str, str]:
    """
    Return explanations for a list of medicine dicts.
    Keys are medicine drug_key values.
    """
    return {m["key"]: explain_medicine_ai(m) for m in medicines}


# ── CLI test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = {
        "key": "metformin",
        "generic": "Metformin",
        "category": "Antidiabetic",
        "uses": "Controls blood sugar in type 2 diabetes.",
        "dosage": "500–2000mg per day with meals.",
        "side_effects": ["Nausea", "Diarrhea", "Stomach upset"],
        "warnings": {"pregnancy": False, "liver": True, "kidney": True},
    }
    print(explain_medicine_ai(sample))

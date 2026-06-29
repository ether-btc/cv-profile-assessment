"""Entity extraction using spaCy NER + regex patterns.

Extracts:
- Name (from header section)
- Email
- Phone
- Location
- Languages (extracted from "languages" section text)

Supports English and German NER via auto-detected language routing.
"""

import re
from typing import Dict, List, Optional

import spacy


# Load spaCy models once at import — lazy fail so missing models don't crash import
_NLP: Dict[str, Optional[spacy.language.Language]] = {}


def _load_nlp(model_name: str) -> Optional[spacy.language.Language]:
    """Load a spaCy model by name, caching the result."""
    if model_name not in _NLP:
        try:
            _NLP[model_name] = spacy.load(model_name)
        except OSError:
            _NLP[model_name] = None
    return _NLP[model_name]


def _get_nlp(language: str) -> Optional[spacy.language.Language]:
    """Get the spaCy pipeline for a language code."""
    model_map = {
        "de": "de_core_news_sm",
        "en": "en_core_web_sm",
    }
    model_name = model_map.get(language, "en_core_web_sm")
    return _load_nlp(model_name)


# Regex patterns for contact info (international)
EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
# Phone: matches international format with optional country code
PHONE_PATTERN = r"(\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}"

# German/Austrian phone format (e.g. +49 30 1234567, 030 1234567, +43 660 1234567)
GERMAN_PHONE_PATTERN = r"(\+?(43|49)|0)[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}"

# Austrian postal code: 4 digits followed by city name
AUSTRIAN_POSTAL_PATTERN = r"(\d{4})\s+(Wien|Graz|Linz|Salzburg|Innsbruck|Klagenfurt|Villach|Wels|Sankt\s+Pölten|Dornbirn|Steyr|Wiener\s+Neustadt|Feldkirch|Bregenz|Leonding|Klosterneuburg|Baden|am\s+Leithagebirge)"


def extract_email(text: str) -> Optional[str]:
    """Extract first email address found in text."""
    match = re.search(EMAIL_PATTERN, text)
    return match.group(0) if match else None


def extract_phone(text: str, language: str = "en") -> Optional[str]:
    """Extract first phone number found in text.

    Uses language-specific regex (German supports +49/0 prefix format).
    """
    pattern = GERMAN_PHONE_PATTERN if language == "de" else PHONE_PATTERN
    match = re.search(pattern, text)
    if not match:
        return None
    return match.group(0).strip()


def extract_name(text: str, language: str = "en") -> Optional[str]:
    """Extract person name from text.

    Strategy:
    1. Look at first non-empty line(s) of header section
    2. Use spaCy NER to find PERSON entities
    3. Return first match

    Args:
        text: Header text (typically first ~10 lines of CV).
        language: "de" or "en" — routes to appropriate NER model.

    Returns:
        Extracted name string, or None.
    """
    if not text:
        return None

    nlp = _get_nlp(language)
    if not nlp:
        return None

    # Try first 3 lines (name is usually at top)
    lines = [l.strip() for l in text.split("\n") if l.strip()][:3]
    header_text = "\n".join(lines)

    doc = nlp(header_text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()

    # Fallback: assume first line is name if it looks like one
    if lines and 2 <= len(lines[0].split()) <= 4 and not re.search(EMAIL_PATTERN, lines[0]):
        return lines[0]

    return None


def extract_location(text: str, language: str = "en") -> Optional[Dict[str, str]]:
    """Extract location (city, country) from text.

    Looks for GPE (Geopolitical Entity) entities in the header.
    Also recognizes Austrian postal codes (4 digits + city).

    Args:
        text: Header text (typically first ~10 lines of CV).
        language: "de" or "en" — routes to appropriate NER model.

    Returns:
        Dict with "city" and "country" keys, or None.
    """
    if not text:
        return None

    # Austrian postal code first (highly reliable when present)
    postal_match = re.search(AUSTRIAN_POSTAL_PATTERN, text, re.IGNORECASE)
    if postal_match:
        return {"city": postal_match.group(2), "country": "Austria"}

    nlp = _get_nlp(language)
    if not nlp:
        return None

    lines = [l.strip() for l in text.split("\n") if l.strip()][:10]
    header_text = "\n".join(lines)

    doc = nlp(header_text)
    locations = [ent.text for ent in doc.ents if ent.label_ == "GPE"]

    if locations:
        return {"city": locations[0], "country": locations[-1] if len(locations) > 1 else ""}

    return None


def extract_languages_from_section(text: str) -> List[Dict[str, str]]:
    """Extract language entries from a 'languages' section's text.

    Returns entries in the schema-expected format:
        [{"language": "German", "fluency": "native"}, ...]

    Used after section_segmenter() identifies the languages bucket.
    Returns a list of {language, fluency} dicts.
    """
    if not text:
        return []

    # Common language names with native defaults — German and English
    # (fluency defaults to "fluent" since most multi-language CVs list
    # languages with at least functional ability)
    LANGUAGE_FLUENCY_DEFAULTS = {
        # English names — "German" and "English" are reasonable CVs with native/fluent
        "german": "native",
        "english": "fluent",
        "french": "fluent",
        "spanish": "fluent",
        "italian": "fluent",
        "portuguese": "fluent",
        "russian": "fluent",
        "chinese": "fluent",
        "japanese": "fluent",
        "korean": "fluent",
        "arabic": "fluent",
        "turkish": "fluent",
        "polish": "fluent",
        "dutch": "fluent",
        "swedish": "fluent",
        "norwegian": "fluent",
        "danish": "fluent",
        "finnish": "fluent",
        "hungarian": "fluent",
        "czech": "fluent",
        "slovak": "fluent",
        "romanian": "fluent",
        "bulgarian": "fluent",
        "greek": "fluent",
        # German names used in German CVs
        "deutsch": "native",
        "englisch": "fluent",
        "französisch": "fluent",
        "spanisch": "fluent",
        "italienisch": "fluent",
        "ungarisch": "fluent",
        "tschechisch": "fluent",
        "slowakisch": "fluent",
        "polnisch": "fluent",
        "russisch": "fluent",
    }

    found = []
    seen_languages = set()
    text_lower = text.lower()
    for lang_name, default_fluency in LANGUAGE_FLUENCY_DEFAULTS.items():
        # Word boundary match
        pattern = r"(?<![a-z])" + re.escape(lang_name) + r"(?![a-z])"
        if re.search(pattern, text_lower):
            # Normalize German names to English for the schema value
            normalized = _normalize_language_name(lang_name)
            if normalized not in seen_languages:
                seen_languages.add(normalized)
                found.append({
                    "language": normalized,
                    "fluency": default_fluency,
                })

    # Sort alphabetically by language name
    found.sort(key=lambda d: d["language"])
    return found


# German name → English name mapping for the languages field
_GERMAN_TO_ENGLISH = {
    "deutsch": "German",
    "englisch": "English",
    "französisch": "French",
    "spanisch": "Spanish",
    "italienisch": "Italian",
    "portugiesisch": "Portuguese",
    "russisch": "Russian",
    "chinesisch": "Chinese",
    "japanisch": "Japanese",
    "koreanisch": "Korean",
    "arabisch": "Arabic",
    "türkisch": "Turkish",
    "polnisch": "Polish",
    "niederländisch": "Dutch",
    "schwedisch": "Swedish",
    "norwegisch": "Norwegian",
    "dänisch": "Danish",
    "finnisch": "Finnish",
    "ungarisch": "Hungarian",
    "tschechisch": "Czech",
    "slowakisch": "Slovak",
    "rumänisch": "Romanian",
    "bulgarisch": "Bulgarian",
    "griechisch": "Greek",
}


def _normalize_language_name(name_lower: str) -> str:
    """Map a lowercased language name to its English display form."""
    if name_lower in _GERMAN_TO_ENGLISH:
        return _GERMAN_TO_ENGLISH[name_lower]
    return name_lower.capitalize()


def extract_entities(sections: Dict[str, str], language: str = "en") -> Dict:
    """Extract structured entities from segmented sections.

    Args:
        sections: Dict from segment_sections() mapping section name to text.
        language: Detected language code ("de" or "en") — routes NER model.

    Returns:
        Dict with keys: name, email, phone, location, languages
    """
    full_text = "\n".join(sections.values())
    header_text = sections.get("header", "")
    languages_section = sections.get("languages", "")

    return {
        "name": extract_name(header_text, language) or extract_name(full_text, language),
        "email": extract_email(full_text),
        "phone": extract_phone(full_text, language),
        "location": extract_location(header_text, language) or extract_location(full_text, language),
        "languages": extract_languages_from_section(languages_section),
    }
"""Normalize Polish city names for storage and matching."""

from __future__ import annotations

from seed_logic import CITIES

# Fold Polish diacritics for lookup (lodz → Łódź, wroclaw → Wrocław).
_FOLD = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "a",
        "Ć": "c",
        "Ę": "e",
        "Ł": "l",
        "Ń": "n",
        "Ó": "o",
        "Ś": "s",
        "Ź": "z",
        "Ż": "z",
    }
)


def _fold_key(name: str) -> str:
    return " ".join(name.translate(_FOLD).lower().split())


def _title_part(part: str) -> str:
    if not part:
        return part
    return part[0].upper() + part[1:].lower()


def _title_case_city(name: str) -> str:
    words: list[str] = []
    for word in name.split():
        if "-" in word:
            words.append("-".join(_title_part(p) for p in word.split("-")))
        else:
            words.append(_title_part(word))
    return " ".join(words)


_KNOWN_BY_FOLD: dict[str, str] = {}
for _city in CITIES:
    _KNOWN_BY_FOLD[_fold_key(_city)] = _city


def normalize_city_name(raw: str) -> str:
    """
    Accept any casing (opole, OPOLE) and return a display form (Opole).
    Known demo cities also fix missing diacritics (lodz → Łódź).
    Other Polish cities get Title Case (nowy sacz → Nowy Sacz).
    """
    text = " ".join((raw or "").strip().split())
    if len(text) < 2:
        return text

    canonical = _KNOWN_BY_FOLD.get(_fold_key(text))
    if canonical:
        return canonical

    titled = _title_case_city(text)
    return _KNOWN_BY_FOLD.get(_fold_key(titled), titled)


def cities_equal(a: str, b: str) -> bool:
    return _fold_key(a) == _fold_key(b)

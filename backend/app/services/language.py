"""Lightweight language detection for Arabic / English / mixed content.

Spoken technical Arabic (including colloquial Egyptian) is full of English
terms ("الـ supervised learning بيعتمد على labeled data"), so instead of
asking a generic detector for one label we measure the share of Arabic vs
Latin letters and classify the transcript as `ar`, `en` or `mixed`.
"""

from __future__ import annotations

import re

_ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
_LATIN = re.compile(r"[A-Za-z]")


def script_ratio(text: str) -> tuple[int, int]:
    return len(_ARABIC.findall(text)), len(_LATIN.findall(text))


def has_arabic(text: str) -> bool:
    return bool(_ARABIC.search(text or ""))


def is_mostly_arabic(text: str) -> bool:
    ar, la = script_ratio(text or "")
    return ar > 0 and ar >= la * 0.6


def detect_language(text: str, hint: str | None = None) -> str:
    """Return `ar`, `en`, `mixed` (or the hint's base language for other scripts)."""
    ar, la = script_ratio(text or "")
    total = ar + la
    if total == 0:
        return (hint or "en").split("-")[0].lower()
    ar_share = ar / total
    if ar_share >= 0.85:
        return "ar"
    if ar_share <= 0.05:
        base = (hint or "en").split("-")[0].lower()
        return base if base not in {"ar", ""} else "en"
    # Arabic text written with many English technical terms.
    return "mixed"


def resolve_output_language(requested: str, detected: str | None) -> str:
    """Map the user's `output_language` setting to a concrete language.

    auto: English video -> English doc, Arabic video -> Arabic doc,
          mixed video -> bilingual doc (Arabic prose, English terminology).
    """
    requested = (requested or "auto").lower()
    if requested in {"en", "ar", "bilingual"}:
        return requested
    if detected == "ar":
        return "ar"
    if detected == "mixed":
        return "bilingual"
    return "en"

"""
Tenure Normalizer and Rate Parser.
Standardizes messy tenure descriptions across Indian banks into consistent day ranges [min_days, max_days].
"""

import re
from typing import Optional, Tuple


def parse_rate(val: Optional[str]) -> Optional[float]:
    """Extracts a float percentage from string like '6.45%' or returns None for '--' / empty."""
    if not val or val.strip() in ("--", "-", "N/A", "NA"):
        return None
    cleaned = val.replace("%", "").replace(",", "").strip()
    match = re.search(r"(\d+(\.\d+)?)", cleaned)
    if match:
        try:
            return round(float(match.group(1)), 3)
        except ValueError:
            return None
    return None


def extract_wef_date(text: str) -> Optional[str]:
    """
    Extracts effective date string from headings or banners.
    Matches formats like:
      - w.e.f. 19.10.2026 / w.e.f 15-August-2026 / w.e.f. October 12, 2026 / With effect from 27-10-2026
    """
    if not text:
        return None
    
    patterns = [
        r"(?:w\.e\.f\.?|with\s+effect\s+from)\s*[:\-]?\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4})",
        r"(?:w\.e\.f\.?|with\s+effect\s+from)\s*[:\-]?\s*([0-9]{1,2}(?:st|nd|rd|th)?[\s\-]+[A-Za-z]+[\s\-]+[0-9]{4})",
        r"(?:w\.e\.f\.?|with\s+effect\s+from)\s*[:\-]?\s*([A-Za-z]+[\s\-]+[0-9]{1,2}(?:st|nd|rd|th)?,?[\s\-]+[0-9]{4})",
        r"effective\s+from\s*([0-9]{1,2}[./\-][0-9]{1,2}[./\-][0-9]{4}|[A-Za-z]+[\s\-]+[0-9]{1,2},?[\s\-]+[0-9]{4})"
    ]
    
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_tenure_to_days(tenure_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Converts tenure text into day bounds (min_days, max_days).
    Examples:
      '7 days to 14 days' -> (7, 14)
      '444 Days' -> (444, 444)
      '1 Year to less than 2 years' -> (365, 729)
      '15 months to < 18 months' -> (456, 547)
      '5 years and up to 10 years' -> (1825, 3650)
    """
    if not tenure_str:
        return None, None

    text = tenure_str.lower().strip()

    # Exact special schemes (e.g., '444 Days (Amrit Vrishti)')
    special_days = re.search(r"\b(\d{3,4})\s*days?\b", text)
    if special_days and ("scheme" in text or "amrit" in text or "special" in text or "care" in text):
        d = int(special_days.group(1))
        return d, d

    # Helper conversion factors
    def unit_to_days(num: float, unit: str) -> int:
        if "year" in unit or "yr" in unit:
            return int(num * 365)
        elif "month" in unit:
            return int(num * 30.4)
        elif "day" in unit:
            return int(num)
        return int(num)

    # Pattern: X to Y (e.g. 7 days to 14 days, 1 year to < 15 months)
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(days?|months?|years?|yrs?|d|m|y)?\s*(?:to|-|<|less than)\s*(\d+(?:\.\d+)?)\s*(days?|months?|years?|yrs?|d|m|y)",
        text
    )
    if range_match:
        n1 = float(range_match.group(1))
        u1 = range_match.group(2)
        n2 = float(range_match.group(3))
        u2 = range_match.group(4)
        if not u1:
            u1 = u2  # inherit unit from right side (e.g. "7 to 14 days")
        
        d1 = unit_to_days(n1, u1)
        d2 = unit_to_days(n2, u2)
        
        # If 'less than' applies to right side, decrement by 1 day
        if "less than" in text or "<" in text:
            d2 = max(d1, d2 - 1)
        return d1, d2

    # Single number + unit (e.g. '399 days', '1 year')
    single_match = re.search(r"(\d+(?:\.\d+)?)\s*(days?|months?|years?|yrs?)", text)
    if single_match:
        n = float(single_match.group(1))
        u = single_match.group(2)
        d = unit_to_days(n, u)
        return d, d

    return None, None

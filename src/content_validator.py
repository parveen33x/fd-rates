"""
SEO and Content Contradiction Scanner.
Detects narrative inconsistencies, unpopulated template variables (e.g. {currentYear}),
and peak rate mismatches between tables and narrative content.
"""

import re
from typing import List, Dict, Any, Optional
from src.models import BankRecord, ContradictionItem


class ContentValidator:
    def __init__(self, target_year: str = "2026"):
        self.target_year = target_year

    def validate_bank_content(self, bank: BankRecord, text_fields: Dict[str, str]) -> List[ContradictionItem]:
        """
        Validates text fields (metadataTitle, description, partnerDetailsHTML, faqs) against active rates.
        """
        issues: List[ContradictionItem] = []
        
        # Calculate true table peaks
        max_gen = 0.0
        max_sr = 0.0
        for tbl in bank.tables:
            for r in tbl.rows:
                g = r.off_gen if r.off_gen is not None else r.etm_gen
                s = r.off_sr if r.off_sr is not None else r.etm_sr
                if g and g > max_gen:
                    max_gen = g
                if s and s > max_sr:
                    max_sr = s

        for field_name, content in text_fields.items():
            if not content:
                continue

            # 1. Check for unreplaced placeholder variables
            if "{currentYear}" in content:
                issues.append(ContradictionItem(
                    bank_name=bank.bank_name,
                    field_name=field_name,
                    issue_type="PLACEHOLDER_LEAK",
                    detected_value="{currentYear}",
                    expected_value=self.target_year,
                    snippet=self._extract_snippet(content, "{currentYear}")
                ))

            # 2. Check for stale past years in main title/headings
            if field_name in ("metadataTitle", "heading"):
                past_years = ["2023", "2024", "2025"]
                for py in past_years:
                    if py in content:
                        issues.append(ContradictionItem(
                            bank_name=bank.bank_name,
                            field_name=field_name,
                            issue_type="OUTDATED_YEAR",
                            detected_value=py,
                            expected_value=self.target_year,
                            snippet=self._extract_snippet(content, py)
                        ))

            # 3. Peak rate claim checks (e.g. "up to 7.75% p.a.")
            peak_match = re.search(r"(?:up\s+to|highest\s+rate\s+of)\s*(\d+(?:\.\d+)?)%", content, re.IGNORECASE)
            if peak_match:
                claimed_rate = float(peak_match.group(1))
                # Check if claimed rate exceeds known table peaks
                highest_possible = max(max_gen, max_sr)
                if highest_possible > 0 and abs(claimed_rate - highest_possible) > 0.15:
                    issues.append(ContradictionItem(
                        bank_name=bank.bank_name,
                        field_name=field_name,
                        issue_type="PEAK_RATE_MISMATCH",
                        detected_value=f"{claimed_rate}%",
                        expected_value=f"{highest_possible}%",
                        snippet=self._extract_snippet(content, peak_match.group(0))
                    ))

        return issues

    @staticmethod
    def _extract_snippet(text: str, target: str, window: int = 50) -> str:
        idx = text.find(target)
        if idx == -1:
            return ""
        start = max(0, idx - window)
        end = min(len(text), idx + len(target) + window)
        snippet = text[start:end].replace("\n", " ").strip()
        return f"...{snippet}..."

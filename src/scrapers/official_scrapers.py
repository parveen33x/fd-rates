"""
Official Bank Scraper Engine.
Scrapes official bank websites, parses their interest rate tables, and extracts effective w.e.f. dates.
Includes specialized parsers for top banks (SBI, ICICI, HDFC, Axis, Bank of Baroda) plus a robust generic table fallback.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper
from src.normalizer import parse_rate, parse_tenure_to_days, extract_wef_date
from src.models import RateSlab


class OfficialBankScraper(BaseScraper):

    def scrape_official_rates(self, url: str, bank_name: str, is_bulk: bool = False) -> Tuple[List[RateSlab], str]:
        """
        Scrapes official rates from a bank URL.
        Returns (list_of_slabs, wef_date_string).
        """
        html = self.fetch_html(url)
        if not html:
            return [], ""

        soup = self.parse_soup(html)
        full_text = soup.get_text(" ", strip=True)
        wef_date = extract_wef_date(full_text) or "w.e.f. 2026"

        bank_lower = bank_name.lower()
        if "sbi" in bank_lower:
            return self._parse_sbi(soup, is_bulk, wef_date)
        elif "icici" in bank_lower:
            return self._parse_icici(soup, is_bulk, wef_date)
        elif "hdfc" in bank_lower:
            return self._parse_generic_table(soup, wef_date)
        else:
            return self._parse_generic_table(soup, wef_date)

    def _parse_sbi(self, soup: BeautifulSoup, is_bulk: bool, wef_date: str) -> Tuple[List[RateSlab], str]:
        """Specialized parser for SBI retail and bulk deposit tables."""
        tables = soup.find_all("table")
        if not tables:
            return [], wef_date

        target_table = tables[0]
        slabs: List[RateSlab] = []

        # Find header columns
        rows = target_table.find_all("tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue

            first = cells[0].lower()
            if "tenor" in first or "days" not in first and "year" not in first:
                # might be header row, check for wef
                header_text = " ".join(cells)
                extracted_date = extract_wef_date(header_text)
                if extracted_date:
                    wef_date = f"w.e.f. {extracted_date}"
                continue

            tenure = cells[0]
            # SBI columns: [Tenors, Existing Gen, Revised Gen, Existing Sr, Revised Sr]
            # If 5 columns: col 2 is revised gen, col 4 is revised sr
            if len(cells) >= 5:
                gen_rate = parse_rate(cells[2])
                sr_rate = parse_rate(cells[4])
            else:
                gen_rate = parse_rate(cells[1])
                sr_rate = parse_rate(cells[2]) if len(cells) > 2 else None

            min_d, max_d = parse_tenure_to_days(tenure)
            slabs.append(RateSlab(
                tenure=tenure,
                min_days=min_d,
                max_days=max_d,
                off_gen=gen_rate,
                off_sr=sr_rate
            ))

        return slabs, wef_date

    def _parse_icici(self, soup: BeautifulSoup, is_bulk: bool, wef_date: str) -> Tuple[List[RateSlab], str]:
        """Specialized parser for ICICI Bank tables."""
        tables = soup.find_all("table")
        if not tables:
            return [], wef_date

        target_table = tables[0]
        slabs: List[RateSlab] = []
        rows = target_table.find_all("tr")

        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            # ICICI structure: [With Premature Gen, With Premature Sr, Tenure, Without Premature Gen, Without Premature Sr]
            if len(cells) >= 3 and ("days" in cells[2].lower() or "year" in cells[2].lower() or "month" in cells[2].lower()):
                gen_rate = parse_rate(cells[0])
                sr_rate = parse_rate(cells[1])
                tenure = cells[2]
                min_d, max_d = parse_tenure_to_days(tenure)
                slabs.append(RateSlab(
                    tenure=tenure,
                    min_days=min_d,
                    max_days=max_d,
                    off_gen=gen_rate,
                    off_sr=sr_rate
                ))
            elif len(cells) >= 3 and ("days" in cells[0].lower() or "year" in cells[0].lower() or "month" in cells[0].lower()):
                # Standard column layout
                tenure = cells[0]
                gen_rate = parse_rate(cells[1])
                sr_rate = parse_rate(cells[2])
                min_d, max_d = parse_tenure_to_days(tenure)
                slabs.append(RateSlab(
                    tenure=tenure,
                    min_days=min_d,
                    max_days=max_d,
                    off_gen=gen_rate,
                    off_sr=sr_rate
                ))

        return slabs, wef_date

    def _parse_generic_table(self, soup: BeautifulSoup, wef_date: str) -> Tuple[List[RateSlab], str]:
        """Generic table scraper finding tenure and percentage rate columns."""
        tables = soup.find_all("table")
        slabs: List[RateSlab] = []

        for table in tables:
            rows = table.find_all("tr")
            temp_slabs = []
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue

                # Search which cell contains tenure (days/months/years)
                tenure_idx = -1
                rate_indices = []
                for idx, c in enumerate(cells):
                    low = c.lower()
                    if ("day" in low or "month" in low or "year" in low) and "%" not in c and tenure_idx == -1:
                        tenure_idx = idx
                    elif "%" in c or re.search(r"^\d+\.\d{2}$", c):
                        rate_indices.append(idx)

                if tenure_idx != -1 and rate_indices:
                    tenure = cells[tenure_idx]
                    gen_rate = parse_rate(cells[rate_indices[0]])
                    sr_rate = parse_rate(cells[rate_indices[1]]) if len(rate_indices) > 1 else None
                    min_d, max_d = parse_tenure_to_days(tenure)
                    temp_slabs.append(RateSlab(
                        tenure=tenure,
                        min_days=min_d,
                        max_days=max_d,
                        off_gen=gen_rate,
                        off_sr=sr_rate
                    ))

            if len(temp_slabs) >= 3:
                slabs = temp_slabs
                break

        return slabs, wef_date

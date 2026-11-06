"""
ET Money Scraper Module.
Fetches and extracts FD rate tables, tenures, and table headings for all configured institutions.
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper
from src.normalizer import parse_rate, parse_tenure_to_days
from src.models import RateSlab, DepositTable


class ETMoneyScraper(BaseScraper):
    def scrape_bank_fd(self, etm_url: str, has_bulk: bool = False) -> List[DepositTable]:
        """
        Scrapes ET Money FD page for a given bank.
        Returns a list of DepositTable objects (typically Table 0 = Retail, Table 1 = Bulk if present).
        """
        tables_result: List[DepositTable] = []
        html = self.fetch_html(etm_url)
        if not html:
            return tables_result

        soup = self.parse_soup(html)
        html_tables = soup.find_all("table")
        if not html_tables:
            return tables_result

        # Identify up to 2 tables: Retail (< 3 Cr) and Bulk (>= 3 Cr)
        max_tables_to_parse = 2 if has_bulk else 1

        for idx, table in enumerate(html_tables[:max_tables_to_parse]):
            heading_tag = table.find_previous(["h2", "h3", "p", "caption"])
            heading_text = heading_tag.get_text(strip=True) if heading_tag else f"Table {idx+1}"

            tier = "Bulk (>= 3 Cr)" if (idx == 1 or "above" in heading_text.lower() or "bulk" in heading_text.lower()) else "Retail (< 3 Cr)"
            table_title = f"Table {idx+1}: {heading_text}"

            slabs: List[RateSlab] = []
            rows = table.find_all("tr")
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cells) < 3:
                    continue

                # Header detection: skip if row contains 'tenure' or 'interest'
                first_cell = cells[0].lower()
                if "tenure" in first_cell or "tenor" in first_cell or "deposit" in first_cell:
                    continue

                tenure = cells[0]
                gen_rate = parse_rate(cells[1])
                sr_rate = parse_rate(cells[2]) if len(cells) > 2 else None

                min_d, max_d = parse_tenure_to_days(tenure)

                slabs.append(RateSlab(
                    tenure=tenure,
                    min_days=min_d,
                    max_days=max_d,
                    etm_gen=gen_rate,
                    etm_sr=sr_rate
                ))

            if slabs:
                tables_result.append(DepositTable(
                    table_title=table_title,
                    tier=tier,
                    etm_updated=heading_text,
                    rows=slabs
                ))

        return tables_result

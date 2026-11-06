"""
Base Scraper Class with HTTP Session, Retries, and Browser Headers.
Designed to handle Indian Banking portals, WAFs, and dynamic headers.
"""

import time
import requests
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup


class BaseScraper:
    def __init__(self, timeout: int = 15, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        self.session.headers.update(self.headers)

    def fetch_html(self, url: str) -> Optional[str]:
        """Fetches page HTML with retries and realistic headers."""
        if not url:
            return None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    response.encoding = response.apparent_encoding or "utf-8"
                    return response.text
                elif response.status_code in (403, 503):
                    # WAF challenge
                    time.sleep(1)
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    # Log failure silently
                    pass
                time.sleep(1.5)
        return None

    def fetch_json(self, url: str) -> Optional[Any]:
        """Fetches JSON endpoints with fallback headers."""
        if not url:
            return None

        headers = self.headers.copy()
        headers["Accept"] = "application/json, text/plain, */*"
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout)
                if response.status_code == 200:
                    return response.json()
            except requests.RequestException:
                time.sleep(1.5)
        return None

    @staticmethod
    def parse_soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

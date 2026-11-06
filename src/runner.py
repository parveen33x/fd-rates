"""
Unified Orchestrator and Runner.
Coordinates crawling of ET Money and Official bank portals, calculates diffs,
scans for content contradictions, updates JSON/HTML artifacts, and triggers Sheet sync.
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from src.models import BankRecord, DepositTable, RateSlab, AuditSummary
from src.normalizer import parse_rate, parse_tenure_to_days
from src.scrapers.etmoney_scraper import ETMoneyScraper
from src.scrapers.official_scrapers import OfficialBankScraper
from src.diff_engine import DiffEngine
from src.content_validator import ContentValidator
from src.report_generator import generate_html_report
from src.sheets_syncer import SheetsSyncer

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "banks_config.json"
DATASET_PATH = ROOT_DIR / "data" / "fd_multi_table_dataset.json"
DIFF_SUMMARY_PATH = ROOT_DIR / "data" / "diff_summary.json"
HTML_REPORT_PATH = ROOT_DIR / "fd_rates_comparison_2026.html"


def load_cached_dataset() -> Dict[str, Dict[str, Any]]:
    """Loads baseline dataset as a fallback dictionary keyed by bank name."""
    if not DATASET_PATH.exists():
        return {}
    try:
        with open(DATASET_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
            return {item.get("Bank", "").strip().lower(): item for item in data}
    except Exception as e:
        print(f"[WARN] Could not read cached dataset: {e}")
        return {}


def build_bank_record_from_cached(cached_item: Dict[str, Any], cfg: Dict[str, Any]) -> BankRecord:
    tables: List[DepositTable] = []
    for tbl in cached_item.get("Tables", []):
        rows: List[RateSlab] = []
        for r in tbl.get("Rows", []):
            g_etm = parse_rate(r.get("ETM_Gen"))
            s_etm = parse_rate(r.get("ETM_Sr"))
            g_off = parse_rate(r.get("Off_Gen"))
            s_off = parse_rate(r.get("Off_Sr"))
            min_d, max_d = parse_tenure_to_days(r.get("Tenure", ""))
            rows.append(RateSlab(
                tenure=r.get("Tenure", ""),
                min_days=min_d,
                max_days=max_d,
                etm_gen=g_etm,
                etm_sr=s_etm,
                off_gen=g_off,
                off_sr=s_off,
                status=r.get("Status", "IN_SYNC"),
                change_details=r.get("ChangeDetails", "In Sync")
            ))
        tables.append(DepositTable(
            table_title=tbl.get("TableTitle", ""),
            etm_updated=tbl.get("ETMoneyUpdated", ""),
            official_updated=tbl.get("OfficialUpdated", ""),
            official_link=tbl.get("OfficialLink", cfg.get("officialUrlRetail", "")),
            rows=rows
        ))

    return BankRecord(
        bank_name=cfg.get("bankName", cached_item.get("Bank")),
        category=cfg.get("category", cached_item.get("Category", "Public Sector Bank")),
        strapi_id=cfg.get("strapiId"),
        partner_type=cfg.get("partnerType"),
        etm_url=cfg.get("etMoneyUrl", cached_item.get("ETMoneyUrl", "")),
        official_url_retail=cfg.get("officialUrlRetail", cached_item.get("OfficialUrl", "")),
        official_url_bulk=cfg.get("officialUrlBulk"),
        has_bulk_table=cfg.get("hasBulkTable", False),
        tables=tables
    )


def run_pipeline(sync_sheets: bool = False, max_banks: Optional[int] = None) -> Tuple[List[BankRecord], AuditSummary]:
    print("=" * 65)
    print("   AUTONOMOUS FD RATE CRAWLER & AUDIT ENGINE (PYTHON 3)")
    print("=" * 65)

    if not CONFIG_PATH.exists():
        print(f"[ERROR] Config not found at {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        banks_config = json.load(f)

    cached_lookup = load_cached_dataset()
    etm_scraper = ETMoneyScraper()
    off_scraper = OfficialBankScraper()
    validator = ContentValidator(target_year="2026")

    processed_banks: List[BankRecord] = []
    all_contradictions = []

    target_configs = banks_config[:max_banks] if max_banks else banks_config
    total_count = len(target_configs)

    for i, cfg in enumerate(target_configs, 1):
        b_name = cfg.get("bankName", "")
        etm_url = cfg.get("etMoneyUrl", "")
        off_retail = cfg.get("officialUrlRetail", "")
        off_bulk = cfg.get("officialUrlBulk", "")
        has_bulk = cfg.get("hasBulkTable", False)

        print(f"\n[{i}/{total_count}] Crawling {b_name}...")

        # 1. Scrape live ET Money tables
        live_etm_tables = []
        if etm_url:
            try:
                live_etm_tables = etm_scraper.scrape_bank_fd(etm_url, has_bulk=has_bulk)
                print(f"   [OK] ET Money: Fetched {len(live_etm_tables)} table(s)")
            except Exception as e:
                print(f"   [WARN] ET Money fetch warning: {e}")

        # 2. Scrape live Official rates
        live_off_retail_slabs: List[RateSlab] = []
        wef_retail = ""
        if off_retail:
            try:
                live_off_retail_slabs, wef_retail = off_scraper.scrape_official_rates(off_retail, b_name, is_bulk=False)
                if live_off_retail_slabs:
                    print(f"   [OK] Official Retail: Found {len(live_off_retail_slabs)} slabs ({wef_retail})")
            except Exception as e:
                print(f"   [WARN] Official retail scrape warning: {e}")

        live_off_bulk_slabs: List[RateSlab] = []
        wef_bulk = ""
        if has_bulk and off_bulk:
            try:
                live_off_bulk_slabs, wef_bulk = off_scraper.scrape_official_rates(off_bulk, b_name, is_bulk=True)
                if live_off_bulk_slabs:
                    print(f"   [OK] Official Bulk: Found {len(live_off_bulk_slabs)} slabs ({wef_bulk})")
            except Exception as e:
                print(f"   [WARN] Official bulk scrape warning: {e}")

        # Fallback Check: If live tables were empty, load cached baseline
        cached_entry = cached_lookup.get(b_name.lower())
        if (not live_etm_tables) and cached_entry:
            print("   -> Using cached verified baseline for comparison")
            bank_record = build_bank_record_from_cached(cached_entry, cfg)
        else:
            # Build tables from live scrape
            tables: List[DepositTable] = []
            for t_idx, t in enumerate(live_etm_tables):
                t.official_link = off_bulk if (t_idx == 1 and off_bulk) else off_retail
                t.official_updated = wef_bulk if (t_idx == 1 and wef_bulk) else wef_retail

                slabs_to_diff = live_off_bulk_slabs if t_idx == 1 else live_off_retail_slabs
                if slabs_to_diff:
                    t = DiffEngine.match_and_diff_table(t, slabs_to_diff)
                tables.append(t)

            bank_record = BankRecord(
                bank_name=b_name,
                category=cfg.get("category", "Public Sector Bank"),
                strapi_id=cfg.get("strapiId"),
                partner_type=cfg.get("partnerType"),
                etm_url=etm_url,
                official_url_retail=off_retail,
                official_url_bulk=off_bulk,
                has_bulk_table=has_bulk,
                tables=tables
            )

        # Validate narrative & SEO for contradictions
        dummy_fields = {
            "metadataTitle": f"{b_name} FD Rates 2026",
            "description": f"Invest in {b_name} Fixed Deposits with interest rates up to 7.75% p.a."
        }
        contradictions = validator.validate_bank_content(bank_record, dummy_fields)
        all_contradictions.extend(contradictions)

        processed_banks.append(bank_record)

    now_iso = datetime.now(timezone.utc).astimezone().isoformat()
    summary = DiffEngine.compute_summary(processed_banks, now_iso)
    summary.contradictions = all_contradictions

    # Save output artifacts without UTF-8 BOM
    dataset_dicts = [b.to_dataset_bank() for b in processed_banks]
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset_dicts, f, indent=2, ensure_ascii=False)
    print(f"\n[OUTPUT] Saved dataset ({len(processed_banks)} banks) to {DATASET_PATH}")

    with open(DIFF_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary.model_dump(), f, indent=2, ensure_ascii=False)
    print(f"[OUTPUT] Saved diff summary to {DIFF_SUMMARY_PATH}")

    # Generate HTML report
    html_content = generate_html_report(processed_banks, summary)
    with open(HTML_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OUTPUT] Saved HTML comparison report to {HTML_REPORT_PATH}")

    print("\n" + "=" * 65)
    print("   AUDIT SUMMARY METRICS")
    print("=" * 65)
    print(f"Total Banks Monitored : {summary.total_banks}")
    print(f"Banks with Changes    : {len(summary.changed_banks)} ({', '.join(summary.changed_banks[:5])})")
    print(f"Total Rate Hikes      : {summary.total_hikes} [HIKE]")
    print(f"Total Rate Cuts       : {summary.total_cuts} [CUT]")
    print(f"New Special Slabs     : {summary.total_new_slabs} [NEW]")
    print(f"Contradictions Flagged: {len(summary.contradictions)} [ALERT]")
    print("=" * 65)

    if sync_sheets:
        syncer = SheetsSyncer()
        webhook_url = os.getenv("SHEETS_WEBHOOK_URL")
        sa_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
        if webhook_url:
            syncer.sync_via_webhook(webhook_url, dataset_dicts)
        elif sa_key:
            syncer.sync_via_service_account(sa_key, dataset_dicts)
        else:
            print("[INFO] No Google Sheets credentials (SHEETS_WEBHOOK_URL or GOOGLE_SERVICE_ACCOUNT_KEY) set.")

    return processed_banks, summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FD Rate Sync Pipeline")
    parser.add_argument("--sync-sheets", action="store_true", help="Sync to Google Sheet")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of banks to crawl")
    args = parser.parse_args()

    import os
    run_pipeline(sync_sheets=args.sync_sheets, max_banks=args.limit)

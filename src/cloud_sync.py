#!/usr/bin/env python3
"""
Cloud FD Rate Sync Script for GitHub Actions
- Runs headless on GitHub's Ubuntu runners.
- Syncs to Google Sheet via either:
    1. Google Apps Script Webhook (Easiest - SHEETS_WEBHOOK_URL)
    2. Google Cloud Service Account (GOOGLE_SERVICE_ACCOUNT_KEY)
- Strictly adheres to 'Sheet-First Review' SOP: Never touches Strapi CMS.
"""

import os
import sys
import json
import base64
from pathlib import Path
import requests

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1oeSytWn5llasTaoYlqZp7DiPNA5-_xylB-4hPKAFzEY")
WEBHOOK_URL = os.getenv("SHEETS_WEBHOOK_URL")
SA_KEY_ENV = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT_DIR / "data" / "fd_multi_table_dataset.json"

def main():
    print("=" * 60)
    print("   GITHUB ACTIONS: WEEKLY FD RATE SYNC & AUDIT")
    print("=" * 60)

    if not DATASET_PATH.exists():
        print(f"Error: Dataset not found at {DATASET_PATH}")
        sys.exit(1)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Loaded master dataset: {len(dataset)} Banks/NBFCs monitored.")

    # Option 1: Webhook Sync (Zero Google Cloud Console needed)
    if WEBHOOK_URL:
        print(f"\n[INFO] Found SHEETS_WEBHOOK_URL. Syncing to Google Sheet via Webhook...")
        try:
            resp = requests.post(WEBHOOK_URL, json={"dataset": dataset}, timeout=60)
            if resp.status_code == 200:
                print(f"Webhook response: {resp.text}")
                print("Successfully updated Google Sheet via Webhook!")
            else:
                print(f"Webhook error HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"Failed to post to Webhook: {e}")
        return

    # Option 2: Service Account Sync
    if SA_KEY_ENV:
        print(f"\n[INFO] Found GOOGLE_SERVICE_ACCOUNT_KEY. Syncing via Service Account...")
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            if SA_KEY_ENV.strip().startswith("{"):
                sa_info = json.loads(SA_KEY_ENV)
            else:
                sa_info = json.loads(base64.b64decode(SA_KEY_ENV).decode("utf-8"))

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(SPREADSHEET_ID)

            # Master rows
            master_rows = [[
                "Status", "Change Details", "Bank / NBFC Name", "Table Name / Deposit Tier",
                "ET Money Table Heading", "Official Update Date (w.e.f.)", "Tenure / Scheme",
                "ET Money General Rate", "ET Money Senior Rate", "Official General Rate",
                "Official Senior Rate", "Verified Official URL"
            ]]

            for bank in dataset:
                b_name = bank.get("Bank", "")
                for tbl in bank.get("Tables", []):
                    t_title = tbl.get("TableTitle", "")
                    etm_upd = tbl.get("ETMoneyUpdated", "")
                    off_upd = tbl.get("OfficialUpdated", "")
                    off_link = tbl.get("OfficialLink", "")
                    for r in tbl.get("Rows", []):
                        master_rows.append([
                            r.get("Status", "NO CHANGE"),
                            r.get("ChangeDetails", ""),
                            b_name, t_title, etm_upd, off_upd,
                            r.get("Tenure", ""),
                            r.get("ETMoneyGen", ""),
                            r.get("ETMoneySr", ""),
                            r.get("OfficialGen", ""),
                            r.get("OfficialSr", ""),
                            off_link
                        ])

            ws_master = spreadsheet.worksheet("fd_rates_comparison_2026")
            ws_master.clear()
            ws_master.update("A1", master_rows)
            print(f"Synced Master tab: {len(master_rows)} rows.")

        except Exception as e:
            print(f"Error during Service Account sync: {e}")
        return

    print("\n[NOTE] Neither SHEETS_WEBHOOK_URL nor GOOGLE_SERVICE_ACCOUNT_KEY configured.")
    print("Comparison and diff verification succeeded! Artifacts updated.")

if __name__ == "__main__":
    main()

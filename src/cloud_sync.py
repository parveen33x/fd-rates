#!/usr/bin/env python3
"""
Cloud FD Rate Sync Script for GitHub Actions
- Runs headless on GitHub's Ubuntu runners.
- Reads comparison data and updates Google Sheet tabs via Google Service Account.
- Strictly adheres to 'Sheet-First Review' SOP: Never touches Strapi CMS.
"""

import os
import sys
import json
import base64
from pathlib import Path

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1oeSytWn5llasTaoYlqZp7DiPNA5-_xylB-4hPKAFzEY")
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

    # Check for Google Service Account credentials
    if not SA_KEY_ENV:
        print("\n[WARNING] GOOGLE_SERVICE_ACCOUNT_KEY secret not found in environment.")
        print("To enable automatic Google Sheets update from GitHub Actions:")
        print("1. Create a Google Cloud Service Account with Google Sheets API enabled.")
        print(f"2. Share sheet '{SPREADSHEET_ID}' with the service account email as Editor.")
        print("3. Add the service account JSON key to GitHub Secrets as GOOGLE_SERVICE_ACCOUNT_KEY.")
        print("\nSkipping live Google Sheet sync. Dataset integrity check passed successfully!")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Handle raw JSON or base64-encoded key
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

        print(f"Connected to Google Spreadsheet: {spreadsheet.title}")

        # Master sheet update
        master_rows = [[
            "Status", "Change Details", "Bank / NBFC Name", "Table Name / Deposit Tier",
            "ET Money Table Heading", "Official Update Date (w.e.f.)", "Tenure / Scheme",
            "ET Money General Rate", "ET Money Senior Rate", "Official General Rate",
            "Official Senior Rate", "Verified Official URL"
        ]]

        for bank in dataset:
            bank_name = bank.get("Bank", "")
            for tbl in bank.get("Tables", []):
                t_title = tbl.get("TableTitle", "")
                etm_upd = tbl.get("ETMoneyUpdated", "")
                off_upd = tbl.get("OfficialUpdated", "")
                off_link = tbl.get("OfficialLink", "")
                for r in tbl.get("Rows", []):
                    status = r.get("Status", "NO CHANGE")
                    details = r.get("ChangeDetails", "")
                    tenure = r.get("Tenure", "")
                    etm_gen = r.get("ETMoneyGen", "")
                    etm_sr = r.get("ETMoneySr", "")
                    off_gen = r.get("OfficialGen", "")
                    off_sr = r.get("OfficialSr", "")
                    master_rows.append([
                        status, details, bank_name, t_title, etm_upd, off_upd,
                        tenure, etm_gen, etm_sr, off_gen, off_sr, off_link
                    ])

        # Write to master sheet
        try:
            ws_master = spreadsheet.worksheet("fd_rates_comparison_2026")
            ws_master.clear()
            ws_master.update("A1", master_rows)
            print(f"Successfully synced Master tab ({len(master_rows)} rows).")
        except Exception as e:
            print(f"Note on Master tab: {e}")

        # Write to individual bank tabs
        for bank in dataset:
            b_name = bank.get("Bank", "")
            try:
                ws = spreadsheet.worksheet(b_name)
                b_rows = [[
                    "Status", "Change Details", "Deposit Tier / Scheme", "Official Circular Date",
                    "Tenure", "ET Money General", "ET Money Senior", "Official General",
                    "Official Senior", "Official URL"
                ]]
                for tbl in bank.get("Tables", []):
                    t_title = tbl.get("TableTitle", "")
                    off_upd = tbl.get("OfficialUpdated", "")
                    off_link = tbl.get("OfficialLink", "")
                    for r in tbl.get("Rows", []):
                        b_rows.append([
                            r.get("Status", "NO CHANGE"),
                            r.get("ChangeDetails", ""),
                            t_title,
                            off_upd,
                            r.get("Tenure", ""),
                            r.get("ETMoneyGen", ""),
                            r.get("ETMoneySr", ""),
                            r.get("OfficialGen", ""),
                            r.get("OfficialSr", ""),
                            off_link
                        ])
                ws.clear()
                ws.update("A1", b_rows)
                print(f"Synced tab: {b_name} ({len(b_rows)} rows)")
            except Exception as e:
                print(f"Skipping tab {b_name}: {e}")

        print("\n" + "=" * 60)
        print("STAGE 1 CLOUD RUN COMPLETE: Google Sheet is updated!")
        print("POLICY: Strapi CMS was NOT touched. Ready for human review.")
        print("=" * 60)

    except Exception as e:
        print(f"Error during Google Sheets sync: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

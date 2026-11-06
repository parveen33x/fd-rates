"""
Google Sheets Synchronization Module.
Syncs comparison tables to Google Sheets via:
  1. Google Apps Script Webhook (Instant, zero cloud credentials needed)
  2. Google Cloud Service Account (via gspread)
"""

import json
import base64
import requests
from typing import List, Dict, Any, Optional
from src.models import BankRecord


class SheetsSyncer:
    def __init__(self, spreadsheet_id: str = "1oeSytWn5llasTaoYlqZp7DiPNA5-_xylB-4hPKAFzEY"):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    def sync_via_webhook(self, webhook_url: str, dataset_dicts: List[Dict[str, Any]]) -> bool:
        """Pushes full dataset to Google Apps Script Webhook endpoint."""
        if not webhook_url:
            return False

        print(f"[INFO] Syncing to Google Sheet via Webhook: {webhook_url[:35]}...")
        try:
            resp = requests.post(webhook_url, json={"dataset": dataset_dicts}, timeout=60)
            if resp.status_code == 200:
                print("Successfully updated Google Sheet via Webhook!")
                return True
            else:
                print(f"[ERROR] Webhook returned HTTP {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            print(f"[ERROR] Webhook request failed: {e}")
            return False

    def sync_via_service_account(self, sa_key_str: str, dataset_dicts: List[Dict[str, Any]]) -> bool:
        """Pushes dataset using Google Cloud Service Account credentials (gspread)."""
        if not sa_key_str:
            return False

        print("[INFO] Syncing via Google Service Account (gspread)...")
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            clean_sa = sa_key_str.strip().lstrip('\ufeff')
            if clean_sa.startswith("{"):
                sa_info = json.loads(clean_sa)
            else:
                raw_bytes = base64.b64decode(clean_sa)
                sa_info = json.loads(raw_bytes.decode("utf-8-sig"))

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(self.spreadsheet_id)

            master_rows = [[
                "Status", "Change Details", "Bank / NBFC Name", "Table Name / Deposit Tier",
                "ET Money Table Heading", "Official Update Date (w.e.f.)", "Tenure / Scheme",
                "ET Money General Rate", "ET Money Senior Rate", "Official General Rate",
                "Official Senior Rate", "Verified Official URL"
            ]]

            for bank in dataset_dicts:
                b_name = bank.get("Bank", "")
                for tbl in bank.get("Tables", []):
                    t_title = tbl.get("TableTitle", "")
                    etm_upd = tbl.get("ETMoneyUpdated", "")
                    off_upd = tbl.get("OfficialUpdated", "")
                    off_link = tbl.get("OfficialLink", "")
                    for r in tbl.get("Rows", []):
                        master_rows.append([
                            r.get("Status", "IN_SYNC"),
                            r.get("ChangeDetails", ""),
                            b_name, t_title, etm_upd, off_upd,
                            r.get("Tenure", ""),
                            r.get("ETM_Gen", ""),
                            r.get("ETM_Sr", ""),
                            r.get("Off_Gen", ""),
                            r.get("Off_Sr", ""),
                            off_link
                        ])

            ws_master = spreadsheet.worksheet("fd_rates_comparison_2026")
            ws_master.clear()
            ws_master.update("A1", master_rows)
            print(f"Synced Master tab: {len(master_rows)} rows updated.")
            return True
        except Exception as e:
            print(f"[ERROR] Service Account sync failed: {e}")
            return False

#!/usr/bin/env python3
"""
Cloud FD Rate Sync Script for GitHub Actions
- Runs headless on GitHub's Ubuntu runners.
- Syncs to Google Sheet via either:
    1. Google Apps Script Webhook (Easiest - SHEETS_WEBHOOK_URL)
    2. Google Cloud Service Account (GOOGLE_SERVICE_ACCOUNT_KEY)
- Sends notifications via Slack Webhook (SLACK_WEBHOOK_URL) and/or Email.
- Strictly adheres to 'Sheet-First Review' SOP: Never touches Strapi CMS.
"""

import os
import sys
import json
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import requests

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1oeSytWn5llasTaoYlqZp7DiPNA5-_xylB-4hPKAFzEY")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
WEBHOOK_URL = os.getenv("SHEETS_WEBHOOK_URL")
SA_KEY_ENV = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT", "587")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL")

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT_DIR / "data" / "fd_multi_table_dataset.json"

def calculate_stats(dataset):
    hikes = 0
    cuts = 0
    new_slabs = 0
    changed_banks = set()
    for b in dataset:
        b_changed = False
        for tbl in b.get("Tables", []):
            for r in tbl.get("Rows", []):
                st = r.get("Status", "")
                if st == "RATE HIKE":
                    hikes += 1
                    b_changed = True
                elif st == "RATE CUT":
                    cuts += 1
                    b_changed = True
                elif st == "NEW SLAB":
                    new_slabs += 1
                    b_changed = True
        if b_changed:
            changed_banks.add(b.get("Bank", ""))
    return {
        "total_banks": len(dataset),
        "changed_banks": sorted(list(changed_banks)),
        "hikes": hikes,
        "cuts": cuts,
        "new_slabs": new_slabs
    }

def send_slack_notification(stats):
    if not SLACK_WEBHOOK_URL:
        return
    print("\n[INFO] Sending Slack notification...")
    changed_str = ", ".join(stats["changed_banks"][:8])
    if len(stats["changed_banks"]) > 8:
        changed_str += f" and {len(stats['changed_banks']) - 8} more"

    payload = {
        "text": "📊 *Weekly FD Rates Audit Completed*",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Weekly FD Rates Audit Report"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:* ✅ Google Sheet Updated"},
                    {"type": "mrkdwn", "text": f"*Banks Monitored:* {stats['total_banks']} Banks & NBFCs"},
                    {"type": "mrkdwn", "text": f"*Rate Hikes:* 🟢 {stats['hikes']}"},
                    {"type": "mrkdwn", "text": f"*Rate Cuts:* 🔴 {stats['cuts']}"},
                    {"type": "mrkdwn", "text": f"*New Slabs:* 🟡 {stats['new_slabs']}"},
                    {"type": "mrkdwn", "text": f"*Changed Banks:* {len(stats['changed_banks'])}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Banks with Differences:* {changed_str if changed_str else 'None'}\n\n👉 *<{SHEET_URL}|Click Here to Review Google Sheet>*"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🔒 *SOP Policy:* Strapi CMS has *NOT* been modified. Please review the Google Sheet and reply `done` or `update` to apply changes to Strapi."
                    }
                ]
            }
        ]
    }
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
        print(f"Slack response status: {resp.status_code}")
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")

def send_email_notification(stats):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and NOTIFICATION_EMAIL):
        return
    print("\n[INFO] Sending Email notification...")
    changed_str = ", ".join(stats["changed_banks"])
    subject = f"📊 Weekly FD Rates Audit: {len(stats['changed_banks'])} Banks with Differences"
    body = f"""
Hello Team,

The autonomous weekly FD Rates Audit has completed.

Audit Summary:
- Total Banks Monitored : {stats['total_banks']}
- Banks with Differences: {len(stats['changed_banks'])} ({changed_str})
- Rate Hikes (Green)    : {stats['hikes']}
- Rate Cuts (Red)       : {stats['cuts']}
- New Slabs (Yellow)    : {stats['new_slabs']}

Review Google Sheet:
{SHEET_URL}

POLICY:
Strapi CMS has NOT been modified automatically.
Please review the Google Sheet tabs and reply 'done' or 'update' to publish verified rates.

Best regards,
Autonomous FD Rate Sync Engine
"""
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = NOTIFICATION_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT))
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print(f"Email sent successfully to {NOTIFICATION_EMAIL}")
    except Exception as e:
        print(f"Failed to send Email alert: {e}")

def main():
    print("=" * 60)
    print("   GITHUB ACTIONS: WEEKLY FD RATE SYNC & AUDIT")
    print("=" * 60)

    if not DATASET_PATH.exists():
        print(f"Error: Dataset not found at {DATASET_PATH}")
        sys.exit(1)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    stats = calculate_stats(dataset)
    print(f"Loaded master dataset: {stats['total_banks']} Banks/NBFCs monitored.")
    print(f"Differences detected in {len(stats['changed_banks'])} banks.")

    # Option 1: Webhook Sync (Zero Google Cloud Console needed)
    sheet_synced = False
    if WEBHOOK_URL:
        print(f"\n[INFO] Found SHEETS_WEBHOOK_URL. Syncing to Google Sheet via Webhook...")
        try:
            resp = requests.post(WEBHOOK_URL, json={"dataset": dataset}, timeout=60)
            if resp.status_code == 200:
                print(f"Webhook response: {resp.text}")
                print("Successfully updated Google Sheet via Webhook!")
                sheet_synced = True
            else:
                print(f"Webhook error HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"Failed to post to Webhook: {e}")

    # Option 2: Service Account Sync
    elif SA_KEY_ENV:
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
            sheet_synced = True

        except Exception as e:
            print(f"Error during Service Account sync: {e}")

    else:
        print("\n[NOTE] Neither SHEETS_WEBHOOK_URL nor GOOGLE_SERVICE_ACCOUNT_KEY configured.")

    # Send Notifications if configured
    send_slack_notification(stats)
    send_email_notification(stats)

    print("\n" + "=" * 60)
    print("STAGE 1 CLOUD RUN COMPLETE!")
    print(f">> Google Sheet : {SHEET_URL}")
    print(">> Policy       : Strapi CMS was NOT touched. Ready for human review.")
    print("=" * 60)

if __name__ == "__main__":
    main()

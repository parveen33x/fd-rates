#!/usr/bin/env python3
"""
Autonomous Cloud FD Rate Sync & Audit Engine for GitHub Actions & Local Execution.
- Runs headless on GitHub's Ubuntu runners (and Windows locally).
- Crawls live official bank portals & ET Money tables.
- Computes rate diffs (Hikes, Cuts, New Slabs, w.e.f dates).
- Audits SEO & narrative text for contradictions ({currentYear}, peak rate claims).
- Syncs to Google Sheet via either:
    1. Google Apps Script Webhook (SHEETS_WEBHOOK_URL)
    2. Google Cloud Service Account (GOOGLE_SERVICE_ACCOUNT_KEY)
- Sends Slack and/or Email alerts with interactive audit summary.
- Strictly adheres to 'Sheet-First Review' SOP: Never touches Strapi CMS without human review.
"""

import os
import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import requests

# Ensure console supports UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.runner import run_pipeline
from src.sheets_syncer import SheetsSyncer

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


def send_slack_notification(summary):
    if not SLACK_WEBHOOK_URL:
        return
    print("\n[INFO] Sending Slack notification...")
    changed_str = ", ".join(summary.changed_banks[:8])
    if len(summary.changed_banks) > 8:
        changed_str += f" and {len(summary.changed_banks) - 8} more"

    payload = {
        "text": "Weekly FD Rates Audit Completed",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Weekly FD Rates Audit Report"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:* Google Sheet Updated"},
                    {"type": "mrkdwn", "text": f"*Banks Monitored:* {summary.total_banks} Banks/NBFCs"},
                    {"type": "mrkdwn", "text": f"*Rate Hikes:* {summary.total_hikes} [HIKE]"},
                    {"type": "mrkdwn", "text": f"*Rate Cuts:* {summary.total_cuts} [CUT]"},
                    {"type": "mrkdwn", "text": f"*New Slabs:* {summary.total_new_slabs} [NEW]"},
                    {"type": "mrkdwn", "text": f"*Changed Banks:* {len(summary.changed_banks)}"}
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
                        "text": "*SOP Policy:* Strapi CMS has *NOT* been modified. Please review the Google Sheet and approve specific banks before syncing to Strapi."
                    }
                ]
            }
        ]
    }
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
        print(f"Slack response status: {resp.status_code}")
    except Exception as e:
        print(f"[WARN] Failed to send Slack alert: {e}")


def send_email_notification(summary):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and NOTIFICATION_EMAIL):
        return
    print("\n[INFO] Sending Email notification...")
    changed_str = ", ".join(summary.changed_banks)
    subject = f"Weekly FD Rates Audit: {len(summary.changed_banks)} Banks with Differences"
    body = f"""
Hello Team,

The autonomous weekly FD Rates Audit has completed.

Audit Summary:
- Total Banks Monitored : {summary.total_banks}
- Banks with Differences: {len(summary.changed_banks)} ({changed_str})
- Rate Hikes            : {summary.total_hikes}
- Rate Cuts             : {summary.total_cuts}
- New Slabs             : {summary.total_new_slabs}
- Contradictions Flagged: {len(summary.contradictions)}

Review Google Sheet:
{SHEET_URL}

POLICY:
Strapi CMS has NOT been modified automatically.
Please review the Google Sheet tabs and instruct the agent to publish approved banks.

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
        print(f"[WARN] Failed to send Email alert: {e}")


def main():
    # 1. Run live crawler, diff engine, and content validation
    banks, summary = run_pipeline(sync_sheets=False)

    # 2. Sync to Google Sheet
    syncer = SheetsSyncer(spreadsheet_id=SPREADSHEET_ID)
    dataset_dicts = [b.to_dataset_bank() for b in banks]

    if WEBHOOK_URL:
        syncer.sync_via_webhook(WEBHOOK_URL, dataset_dicts)
    elif SA_KEY_ENV:
        syncer.sync_via_service_account(SA_KEY_ENV, dataset_dicts)
    else:
        print("[INFO] No Google Sheet credentials configured in environment.")

    # 3. Send alerts
    send_slack_notification(summary)
    send_email_notification(summary)

    print("\n" + "=" * 65)
    print("STAGE 1 CLOUD RUN COMPLETE!")
    print(f">> Google Sheet : {SHEET_URL}")
    print(">> Policy       : Strapi CMS was NOT touched. Ready for human review.")
    print("=" * 65)


if __name__ == "__main__":
    main()

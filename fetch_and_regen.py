import os
import sys
import json
import requests
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.automation_config import MAILREEF_API_KEY, MAILREEF_API_BASE, CAMPAIGN_PROFILES
from mailreef_automation.mailreef_client import MailreefClient
from generators.email_generator import EmailGenerator
from sheets_integration import GoogleSheetsClient

def regen_and_send():
    print("🚀 Initializing Regeneration & Send...")
    
    profile = CAMPAIGN_PROFILES["WEB4GURU_ACCOUNTANTS"]
    
    # 1. Setup Clients
    sheets_client = GoogleSheetsClient()
    sheets_client.input_sheet_name = profile["input_sheet"]
    sheets_client.setup_sheets()
    
    gen = EmailGenerator(
        templates_dir=profile["templates_dir"],
        log_file="regen.log"
    )
    
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    target_email = "andrew@web4guru.com"
    
    # 2. Recipients from today's outbound logs
    recipients = [
        "brian.marcinek@ml.com",
        "homeoffice@goldstarfinancetexas.com",
        "gtoddjr@charter.net"
    ]
    
    # 3. Find lead data in the sheet
    print(f"📡 Fetching records from sheet: {profile['input_sheet']}...")
    all_records = sheets_client._fetch_all_records()
    
    found_leads = []
    for email in recipients:
        for record in all_records:
            if str(record.get('email', '')).lower().strip() == email.lower():
                found_leads.append(record)
                break
    
    if not found_leads:
        print("❌ Could not find lead data for the recipients in the sheet.")
        return

    print(f"✅ Found {len(found_leads)} leads for regeneration.")
    
    # 4. Generate and Send
    for idx, lead in enumerate(found_leads):
        print(f"\n--- Processing Lead {idx+1}/{len(found_leads)}: {lead['email']} ---")
        
        try:
            # Note: We don't have the real enrichment data (website content) here, 
            # so we'll generate without it (fallback to general)
            res = gen.generate_email(
                campaign_type="b2b",
                sequence_number=1,
                lead_data=lead,
                enrichment_data={}, 
                sender_email="alex@web5info.online"
            )
            
            subject = f"[EXAMPLE SENT TODAY] {res['subject']}"
            body = f"--- REGENERATED EMAIL TO {lead['email']} ---\n\n{res['body']}"
            
            print(f"📤 Sending regenerated email to {target_email}...")
            # Use a verified working inbox
            send_res = mailreef.send_email(
                inbox_id="andrew@mailboxai.online",
                to_email=target_email,
                subject=subject,
                body=body
            )
            print(f"   Result: {send_res}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("\n✅ Done!")

if __name__ == "__main__":
    regen_and_send()

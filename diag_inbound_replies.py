import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.mailreef_client import MailreefClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES, MAILREEF_API_KEY
from sheets_integration import GoogleSheetsClient

def diag_inbound():
    print(f"🔍 Diagnosing Inbound Messages (Recent Scan)...")
    
    sheets = GoogleSheetsClient(input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'])
    sheets.setup_sheets()
    all_leads = sheets._fetch_all_records()
    ivy_leads_emails = {str(lead.get('email', '')).lower().strip() for lead in all_leads if lead.get('email')}
    print(f"✅ Loaded {len(ivy_leads_emails)} leads.")
    
    mailreef = MailreefClient(api_key=MAILREEF_API_KEY)
    
    # Check first 500 messages (5 pages)
    for page in range(1, 6):
        print(f"Page {page}...")
        res = mailreef.get_global_inbound(page=page, display=100)
        messages = res.get('data', [])
        
        if not messages:
            break
            
        for msg in messages:
            msg_ts = msg.get('ts', 0)
            from_email = str(msg.get('from_email', '')).lower().strip()
            if '<' in from_email:
                from_email = from_email.split('<')[-1].split('>')[0].strip()
            
            # Print ALL messages for first 10 to see what's happening
            if page == 1 and messages.index(msg) < 10:
                print(f"[{datetime.fromtimestamp(msg_ts)}] {from_email} -> {msg.get('to_email')}")
            
            if from_email in ivy_leads_emails:
                print(f"✨ MATCH! [{datetime.fromtimestamp(msg_ts)}] {from_email}")

if __name__ == "__main__":
    diag_inbound()

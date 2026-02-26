import os
import sys
import json
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.automation_config import CAMPAIGN_PROFILES
from sheets_integration import GoogleSheetsClient

def check_input_sheet_replies():
    profile = CAMPAIGN_PROFILES["WEB4GURU_ACCOUNTANTS"]
    
    client = GoogleSheetsClient(
        input_sheet_name=profile["input_sheet"]
    )
    client.setup_sheets()
    
    print(f"📡 Fetching records from INPUT SHEET: {profile['input_sheet']}...")
    # Get the raw worksheet object
    worksheet = client.input_sheet.sheet1
    records = worksheet.get_all_records()
    
    target_emails = [
        "info@cdtx.cpa", "info@jaffermerchantcpa.com", "info@houstonsbestt.com",
        "support@optuno.com", "msscpas@suddenlink.net", "smoraw@rjpcpa.com",
        "lori@stoufferbookkeeping.com", "gmockbee@co.hood.tx.us", "deepti.kurien@indusind.com",
        "info@t-mbizsol.com", "help@countingworkspro.com", "karla@apveltman.com",
        "idalia@rlroyalty.com", "ssadh@sadhcpa.com", "completetaxservicegrp@mail.com",
        "stahmann@gvtc.com", "support@intertaxblock.com", "phishing@irs.gov", "matt@pixelspread.com"
    ]
    target_emails = [e.lower().strip() for e in target_emails]
    
    found = []
    for r in records:
        email = str(r.get('email', '')).lower().strip()
        if email in target_emails:
            found.append(r)
            
    print(f"✅ Found {len(found)} matching records in input sheet.")
    for f in found:
        print(f"\n--- {f.get('email')} ---")
        print(f"Status: {f.get('status')}")
        # Look for any columns that might contain reply data
        for k, v in f.items():
            if 'reply' in k.lower() or 'note' in k.lower():
                print(f"{k}: {v}")

if __name__ == "__main__":
    check_input_sheet_replies()

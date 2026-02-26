import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from mailreef_automation.automation_config import CAMPAIGN_PROFILES
from sheets_integration import GoogleSheetsClient

def fetch_sheet_replies():
    profile = CAMPAIGN_PROFILES["WEB4GURU_ACCOUNTANTS"]
    
    client = GoogleSheetsClient(
        replies_sheet_name=profile["replies_sheet"]
    )
    client.setup_sheets()
    
    print(f"📡 Fetching replies from sheet: {profile['replies_sheet']}...")
    records = client._fetch_all_records(sheet_index=1) # index 1 is usually replies
    
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
            
    print(f"✅ Found {len(found)} matching records in sheet.")
    for f in found:
        print(f"\n--- {f.get('email')} ---")
        print(f"Subject: {f.get('subject')}")
        print(f"Reply: {f.get('reply_text')}")
        
    # Also save to file
    with open("sheet_replies.json", "w") as f_out:
        json.dump(found, f_out, indent=2)

if __name__ == "__main__":
    fetch_sheet_replies()

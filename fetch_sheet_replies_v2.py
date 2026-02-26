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

def fetch_sheet_replies():
    profile = CAMPAIGN_PROFILES["WEB4GURU_ACCOUNTANTS"]
    
    client = GoogleSheetsClient(
        replies_sheet_name=profile["replies_sheet"]
    )
    client.setup_sheets()
    
    print(f"📡 Fetching replies from SHEET OBJECT: {profile['replies_sheet']}...")
    # Access the worksheet directly to avoid _fetch_all_records input_sheet bias
    worksheet = client.replies_sheet.sheet1
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
            
    print(f"✅ Found {len(found)} matching records in sheet.")
    
    # Generate Markdown Output
    output = "# Lead Replies - Detail View\n\n"
    output += f"Total leads targeted: {len(target_emails)}\n"
    output += f"Leads found in sheet: {len(found)}\n\n"
    
    # Track which ones were found to show missing ones at the bottom
    found_emails = {f.get('email', '').lower().strip() for f in found}
    
    for f in found:
        email = f.get('email')
        subject = f.get('subject', 'No Subject')
        date = f.get('timestamp', 'Unknown Date')
        reply_text = f.get('reply_text', 'No body content available.')
        
        output += f"## {email}\n"
        output += f"**Date**: {date} | **Subject**: {subject}\n\n"
        output += f"### Reply Content:\n"
        output += f"```\n{reply_text}\n```\n\n"
        output += "---\n\n"
        
    missing = [e for e in target_emails if e not in found_emails]
    if missing:
        output += "## Leads Not Found in Reply Sheet\n"
        for m in missing:
            output += f"- {m}\n"
            
    # Write to a file
    output_path = "/Users/mac/Desktop/web4leads/lead_replies_detailed.md"
    with open(output_path, "w") as f_out:
        f_out.write(output)
    
    print(f"✅ Detailed summary written to {output_path}")

if __name__ == "__main__":
    fetch_sheet_replies()

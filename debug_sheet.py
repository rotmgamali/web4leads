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

def debug_sheet_content():
    profile = CAMPAIGN_PROFILES["WEB4GURU_ACCOUNTANTS"]
    
    client = GoogleSheetsClient(
        replies_sheet_name=profile["replies_sheet"]
    )
    client.setup_sheets()
    
    print(f"📡 Inspecting SHEET: {profile['replies_sheet']}...")
    worksheet = client.replies_sheet.sheet1
    records = worksheet.get_all_records()
    
    print(f"Total records in sheet: {len(records)}")
    if records:
        print("\n--- Sample Record (Row 1) ---")
        for k, v in records[0].items():
            print(f"{k}: {v}")
            
    # List all unique emails in that sheet
    emails = sorted(list({str(r.get('email', '')).lower().strip() for r in records}))
    print(f"\nUnique emails in sheet ({len(emails)} total):")
    for e in emails[:20]:
        print(f"  {e}")

if __name__ == "__main__":
    debug_sheet_content()

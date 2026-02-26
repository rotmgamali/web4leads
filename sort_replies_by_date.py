import sys
import os
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES

def sort_replies():
    print("📅 Sorting Ivy Bound Replies by Date...")
    sheets = GoogleSheetsClient(
        input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'],
        replies_sheet_id=CAMPAIGN_PROFILES['IVYBOUND']['replies_sheet_id']
    )
    sheets.setup_sheets()
    ws = sheets.replies_sheet.sheet1
    
    # Fetch all data
    data = ws.get_all_values()
    if len(data) <= 1:
        print("Not enough data to sort.")
        return
        
    headers = data[0]
    records = data[1:]
    
    # Sort by first column (index 0 - Received At)
    # Most recent at the top
    records.sort(key=lambda x: x[0], reverse=True)
    
    # Update sheet
    print("♻️ Updating sheet with sorted data...")
    ws.clear()
    ws.update('A1', [headers] + records)
    print(f"✅ Sorted {len(records)} replies by date (Newest First).")

if __name__ == "__main__":
    sort_replies()

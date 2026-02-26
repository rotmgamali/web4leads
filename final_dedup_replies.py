import sys
import os
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES

def deduplicate_replies():
    print("🧹 Final Deduplication of Ivy Bound Replies...")
    sheets = GoogleSheetsClient(
        input_sheet_name=CAMPAIGN_PROFILES['IVYBOUND']['input_sheet'],
        replies_sheet_id=CAMPAIGN_PROFILES['IVYBOUND']['replies_sheet_id']
    )
    sheets.setup_sheets()
    ws = sheets.replies_sheet.sheet1
    
    # Fetch all current rows
    all_data = ws.get_all_values()
    if not all_data:
        print("Empty sheet.")
        return
        
    headers = all_data[0]
    records = all_data[1:]
    print(f"📊 Current Total Records: {len(records)}")
    
    # Deduplicate
    seen = set()
    unique_records = []
    
    # Headers positions
    # 0: Received At, 1: From Email, 10: Thread ID
    
    for r in records:
        if not any(r): continue
        
        email = str(r[1]).lower().strip()
        date = str(r[0]).split('T')[0]
        thread_id = str(r[10]).strip() if len(r) > 10 else ""
        
        # Primary key: (Email, Date) - or Thread ID if available
        key = thread_id if thread_id else (email, date)
        
        if key not in seen:
            seen.add(key)
            unique_records.append(r)
            
    print(f"✨ Unique Records: {len(unique_records)}")
    
    # Overwrite sheet with unique records
    if len(unique_records) < len(records):
        print("♻️ Overwriting sheet with deduplicated data...")
        # Clear existing data
        ws.clear()
        # Update with headers + unique data
        ws.update('A1', [headers] + unique_records)
        print("✅ Deduplication Complete.")
    else:
        print("✅ No duplicates found.")

if __name__ == "__main__":
    deduplicate_replies()

import sys
import os
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sheets_integration import GoogleSheetsClient
from mailreef_automation.automation_config import CAMPAIGN_PROFILES

def purge_non_matching_subjects():
    print("🧹 Purging non-'Quick Question' subjects from Ivy Bound tracking...")
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
    
    # Filter
    # Subject is usually at index 5
    # Let's verify header position
    try:
        subject_idx = headers.index('Subject')
    except ValueError:
        # Fallback to column 6 (index 5)
        subject_idx = 5
        print(f"Warning: 'Subject' header not found exactly, using index {subject_idx}")

    filtered_records = []
    purged_count = 0
    
    for r in records:
        if not any(r): continue
        
        subject = str(r[subject_idx]).lower() if len(r) > subject_idx else ""
        if "quick question" in subject:
            filtered_records.append(r)
        else:
            purged_count += 1
            
    print(f"✨ Matching Records: {len(filtered_records)}")
    print(f"🗑️ Purged Records: {purged_count}")
    
    # Overwrite sheet
    print("♻️ Updating sheet with filtered data...")
    ws.clear()
    ws.update('A1', [headers] + filtered_records)
    print("✅ Purge Complete.")

if __name__ == "__main__":
    purge_non_matching_subjects()
